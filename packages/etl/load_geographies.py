"""
Upsert geographies from a shapefile, adding only what the database is missing.

The geography side of this project has only ever had an all-or-nothing path:
create_national.py regenerates every shapefile and CSV, and load_data_to_db.py
then upserts ~900,000 geography rows and re-upserts ~39 million result rows.
Adding one year of one geography level does not warrant any of that, and on an
unreliable connection it is unlikely to finish at all.

This is the geographic counterpart to load_saipe.py: it reads one shapefile,
compares it against what is already stored, and by default writes only the rows
that are absent. Geometry travels with the row rather than in a second pass.

    python3 load_geographies.py --shapefile "../../ECHO REVAMP/legdistgeos/leg_dist_2023.shp"
    python3 load_geographies.py --shapefile FILE --year 2023 --dry-run
    python3 load_geographies.py --shapefile FILE --all      # also refresh existing rows

Nothing outside the (geo_id, geo_level, year) keys present in the file is ever
touched, so a file covering one year cannot disturb any other.
"""
import argparse
import csv
import io
import logging
import sys
import time

import fiona
from shapely.geometry import MultiPolygon, shape
from sqlalchemy import create_engine, text

from db_target import confirm_target

logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')

# Identifier width identifies the level for GEOID-keyed files. sldu/sldl are
# absent: both are 5 wide and are told apart by the file's 'house' column.
GEOID_WIDTH_TO_LEVEL = {4: 'congressional_district', 5: 'county',
                        7: 'school_district', 11: 'tract'}

STAGING_TABLE = '_geographies_staging'
STAGING_COLUMNS = ['geo_id', 'geo_name', 'geo_level', 'year', 'state_fips', 'geom_wkt']

# Far smaller than the tabular loader's chunks: a single district boundary can
# run to tens of kilobytes of WKT, so rows are big even when few.
CHUNK_ROWS = 250
MAX_ATTEMPTS = 4


def read_shapefile(path, year_filter, level_override):
    """Read an ECHO-format shapefile into rows ready for the geographies table."""
    rows = []
    skipped_year = 0
    with fiona.open(str(path)) as src:
        available = set(src.schema['properties'])
        missing = {'GEOID', 'Year', 'Name'} - available
        if missing:
            logging.error(f"{path}: missing column(s) {sorted(missing)}")
            logging.error("Expected an ECHO-format shapefile: Year, State, GEOID, Name"
                          " (+ house for legislative).")
            logging.error("Raw Census files need prepare_legislative_boundaries.py first.")
            sys.exit(1)

        has_house = 'house' in available
        for feature in src:
            props = feature['properties']
            year = str(props['Year']).strip()
            if year_filter and year != str(year_filter):
                skipped_year += 1
                continue

            geo_id = str(props['GEOID']).strip()

            if level_override:
                level = level_override
            elif has_house and props.get('house'):
                # 'upper' is the state senate; anything else is the lower chamber.
                level = 'sldu' if str(props['house']).strip().lower() == 'upper' else 'sldl'
            else:
                level = GEOID_WIDTH_TO_LEVEL.get(len(geo_id))
                if not level:
                    logging.error(f"Cannot tell which level a {len(geo_id)}-character "
                                  f"GEOID belongs to ({geo_id!r}).")
                    logging.error("Pass --level explicitly.")
                    sys.exit(1)

            geom = shape(feature['geometry'])
            if geom.is_empty:
                continue
            # The column is declared MultiPolygon; a bare Polygon fails on insert.
            if geom.geom_type == 'Polygon':
                geom = MultiPolygon([geom])

            rows.append({
                'geo_id': geo_id,
                'geo_name': str(props['Name']).strip(),
                'geo_level': level,
                'year': int(year),
                'state_fips': geo_id[:2],
                'geom_wkt': geom.wkt,
            })

    if skipped_year:
        logging.info(f"  ignored {skipped_year:,} row(s) from other years")
    return rows


def split_new_and_existing(engine, rows):
    """Ask the database which of these keys it already holds."""
    levels = sorted({r['geo_level'] for r in rows})
    years = sorted({r['year'] for r in rows})
    with engine.connect() as conn:
        present = conn.execute(text(
            "SELECT geo_id, geo_level::text, year FROM geographies "
            "WHERE geo_level::text = ANY(:levels) AND year = ANY(:years)"),
            {"levels": levels, "years": years}).fetchall()
    known = {(g, l, y) for g, l, y in present}

    new, existing = [], []
    for row in rows:
        key = (row['geo_id'], row['geo_level'], row['year'])
        (existing if key in known else new).append(row)
    return new, existing


def stage_rows(engine, rows):
    """Stream rows into a staging table, a chunk per connection, with retries."""
    with engine.begin() as conn:
        conn.execute(text(f"DROP TABLE IF EXISTS {STAGING_TABLE}"))
        conn.execute(text(
            f"CREATE TABLE {STAGING_TABLE} ("
            "geo_id VARCHAR(20), geo_name TEXT, geo_level VARCHAR(50), "
            "year INTEGER, state_fips VARCHAR(2), geom_wkt TEXT)"))

    total = len(rows)
    done = 0
    for start in range(0, total, CHUNK_ROWS):
        chunk = rows[start:start + CHUNK_ROWS]
        buf = io.StringIO()
        writer = csv.writer(buf)
        for row in chunk:
            writer.writerow([row[c] for c in STAGING_COLUMNS])

        for attempt in range(1, MAX_ATTEMPTS + 1):
            try:
                buf.seek(0)
                with engine.begin() as conn:
                    cur = conn.connection.cursor()
                    cur.copy_expert(
                        f"COPY {STAGING_TABLE} ({', '.join(STAGING_COLUMNS)}) "
                        "FROM STDIN WITH (FORMAT csv)", buf)
                break
            except Exception as exc:
                if attempt == MAX_ATTEMPTS:
                    raise
                wait = 2 ** attempt
                logging.warning(f"  chunk at row {start:,} failed "
                                f"({type(exc).__name__}); retrying in {wait}s")
                time.sleep(wait)
                engine.dispose()   # do not reuse a socket that just died

        done += len(chunk)
        logging.info(f"  staged {done:,}/{total:,} rows")

    with engine.connect() as conn:
        staged = conn.execute(text(f"SELECT COUNT(*) FROM {STAGING_TABLE}")).scalar()
    if staged != total:
        raise RuntimeError(f"staging holds {staged:,} rows, expected {total:,}")
    return staged


def apply_staged(engine):
    """Move staged rows into geographies, then drop the staging table.

    ON CONFLICT keys on (geo_id, geo_level, year), the table's unique
    constraint, so only the keys present in the file are affected. Everything
    happens inside the database; no rows cross the network at this point.
    """
    with engine.begin() as conn:
        before = conn.execute(text("SELECT COUNT(*) FROM geographies")).scalar()
        conn.execute(text(f"""
            INSERT INTO geographies
                (geo_id, geo_name, geo_level, year, state_fips, geometry)
            SELECT geo_id, geo_name, geo_level, year, state_fips,
                   ST_GeomFromText(geom_wkt, 4326)
            FROM {STAGING_TABLE}
            ON CONFLICT (geo_id, geo_level, year) DO UPDATE
                SET geo_name   = EXCLUDED.geo_name,
                    state_fips = EXCLUDED.state_fips,
                    geometry   = EXCLUDED.geometry
        """))
        after = conn.execute(text("SELECT COUNT(*) FROM geographies")).scalar()
        conn.execute(text(f"DROP TABLE IF EXISTS {STAGING_TABLE}"))
    return before, after


def main():
    parser = argparse.ArgumentParser(description=__doc__,
                                     formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument('--shapefile', required=True,
                        help='ECHO-format shapefile (Year, State, GEOID, Name [, house]).')
    parser.add_argument('--year', help='Load only this year from the file.')
    parser.add_argument('--level',
                        help='Force the geography level instead of inferring it.')
    parser.add_argument('--all', action='store_true',
                        help='Also refresh rows already present, replacing their name '
                             'and geometry. Default is to add only what is missing.')
    parser.add_argument('--dry-run', action='store_true',
                        help='Report what would change without writing.')
    args = parser.parse_args()

    target = confirm_target("load geographies into", dry_run=args.dry_run)
    engine = create_engine(target.url, connect_args={
        'keepalives': 1, 'keepalives_idle': 30,
        'keepalives_interval': 10, 'keepalives_count': 5,
    })

    logging.info(f"=== Reading {args.shapefile} ===")
    rows = read_shapefile(args.shapefile, args.year, args.level)
    if not rows:
        logging.error("No usable rows found.")
        sys.exit(1)

    counts = {}
    for row in rows:
        counts[(row['year'], row['geo_level'])] = counts.get(
            (row['year'], row['geo_level']), 0) + 1
    for (year, level), n in sorted(counts.items()):
        logging.info(f"  {year}  {level:<24} {n:>7,}")

    logging.info("=== Comparing against the database ===")
    new, existing = split_new_and_existing(engine, rows)
    logging.info(f"  {len(new):,} row(s) missing from the database")
    logging.info(f"  {len(existing):,} row(s) already present")

    to_write = rows if args.all else new
    if not to_write:
        logging.info("Nothing to do — the database already has everything in this file.")
        logging.info("Use --all to refresh names and geometry for existing rows.")
        return

    if args.all and existing:
        logging.warning(f"  --all: {len(existing):,} existing row(s) will have their "
                        f"name and geometry replaced")

    logging.info(f"{len(to_write):,} row(s) will be written")
    if args.dry_run:
        logging.info("Dry run — no changes written.")
        return

    logging.info("=== Staging rows ===")
    stage_rows(engine, to_write)

    logging.info("=== Applying to geographies ===")
    before, after = apply_staged(engine)
    logging.info(f"=== geographies: {before:,} -> {after:,} rows "
                 f"(delta {after - before:+,}) ===")
    logging.info("Done.")
    logging.info("")
    logging.info("If results data was waiting on these geographies, load it now, e.g.")
    logging.info("  python3 load_saipe.py --only legislative")


if __name__ == '__main__':
    main()
