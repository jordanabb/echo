"""
Load SAIPE child-poverty estimates into results_data.

SAIPE (Small Area Income and Poverty Estimates, US Census Bureau) publishes one
value per geography per year. The source files here carry several columns, but
only the poverty rate is loaded — population and child counts would duplicate
indicators the dashboard already has, and two population figures that disagree
is worse than one.

Process (atomic, single transaction):
  1. Read the CSVs, keeping IDs as strings so leading zeros survive.
  2. Normalise IDs to the widths used in the geographies table.
  3. Drop rows whose geography does not exist, reporting how many.
  4. DELETE any existing rows for this indicator, then INSERT the new ones.

Usage:
    python3 load_saipe.py --dry-run    # validate, write nothing
    python3 load_saipe.py              # load
"""
import argparse
import io
import logging
import os
import pathlib
import sys
import time

import pandas as pd
from sqlalchemy import create_engine, text

from create_national import REVAMP_DIR, format_geoid
from db_target import confirm_target

logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')

# Files found to contain unusable identifiers, collected so the run can stop with
# a single clear summary instead of a warning scrolled off the top.
MALFORMED = []

# -----------------------------------------------------------------------------
# What gets loaded
# -----------------------------------------------------------------------------
# The display name IS the key: it is stored in results_data.indicator_id and must
# match the "name" field of the corresponding entry in the backend's
# indicator_config.py exactly, or the dashboard cannot find the data.
INDICATOR_NAME = "Children in Poverty (%)"

# Column in the source CSVs holding the value.
VALUE_COLUMN = "poverty_rate"

# Every kind of source this loader understands. Which file is which is worked
# out by inspecting the contents, not by matching filenames -- exports get
# renamed, dated, and suffixed with "(1)", and a filename check turns that into
# a silent no-op.
#
# Derived from GEOID_WIDTH_TO_LEVEL below so that teaching discovery about a new
# geography level also makes it selectable with --only; keeping a second hand
# written list is how congressional districts came to be discoverable but not
# loadable.
KINDS = ('congressional_district', 'county', 'legislative', 'school_district', 'tract')

# -----------------------------------------------------------------------------


# Column order used for both the dataframe and the COPY statement.
COLUMNS = ['geo_id', 'geo_level', 'year', 'indicator_id', 'value']

# Rows per COPY. Small enough that each chunk finishes before an unreliable link
# has a chance to drop it, and each one is retried independently.
CHUNK_ROWS = 5000
MAX_ATTEMPTS = 4

# Rows are staged in a real table rather than a temporary one: a TEMP table dies
# with its connection, which is precisely the event being defended against.
STAGING_TABLE = '_saipe_staging'


def copy_chunks(engine, df):
    """Stream rows into the staging table, a chunk per connection.

    A single COPY of the whole set is one long-lived connection, and losing it
    anywhere means starting over. Chunking bounds what a dropped connection
    costs to whatever the current chunk was.
    """
    with engine.begin() as conn:
        conn.execute(text(f"DROP TABLE IF EXISTS {STAGING_TABLE}"))
        # No indexes and no constraints: this table exists only to receive rows
        # quickly, and is validated by row count before anything depends on it.
        conn.execute(text(
            f"CREATE TABLE {STAGING_TABLE} ("
            "geo_id VARCHAR(20), geo_level VARCHAR(50), year INTEGER, "
            "indicator_id TEXT, value VARCHAR(50))"))

    total = len(df)
    done = 0
    for start in range(0, total, CHUNK_ROWS):
        chunk = df.iloc[start:start + CHUNK_ROWS]
        buf = io.StringIO()
        chunk.to_csv(buf, index=False, header=False, columns=COLUMNS)

        for attempt in range(1, MAX_ATTEMPTS + 1):
            try:
                buf.seek(0)
                with engine.begin() as conn:
                    cur = conn.connection.cursor()
                    cur.copy_expert(
                        f"COPY {STAGING_TABLE} ({', '.join(COLUMNS)}) "
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


# Width each level's identifier must have once normalised. Letters are allowed —
# several states split legislative districts into lettered subdistricts (MN 27A,
# MD 1A, AK senate A-T) and those are valid Census identifiers.
EXPECTED_WIDTH = {'county': 5, 'tract': 11, 'sldu': 5, 'sldl': 5,
                  'school_district': 7, 'congressional_district': 4}

# Identifier width is what distinguishes one GEOID-keyed file from another, so
# discovery reads it straight from the widths above. sldu/sldl are absent here:
# they are also 5 wide, but arrive in a LEGID file and are told apart by its
# 'house' column rather than by width.
GEOID_WIDTH_TO_LEVEL = {
    EXPECTED_WIDTH['congressional_district']: 'congressional_district',
    EXPECTED_WIDTH['county']: 'county',
    EXPECTED_WIDTH['school_district']: 'school_district',
    EXPECTED_WIDTH['tract']: 'tract',
}


def discover_sources(directory):
    """Classify every CSV in `directory` by its columns and identifier widths.

    Returns {kind: spec}. A file is only considered if it carries the value and
    year columns this loader needs, so unrelated CSVs sitting in the same folder
    are ignored rather than misread.
    """
    directory = os.path.abspath(directory)
    if not os.path.isdir(directory):
        logging.error(f"Not a directory: {directory}")
        logging.error("Set ECHO_RAW_DIR to the folder holding the source CSVs.")
        sys.exit(1)

    found = {}
    for path in sorted(pathlib.Path(directory).glob('*.csv')):
        try:
            head = pd.read_csv(path, nrows=200, dtype=str)
        except Exception as exc:
            logging.debug(f"  unreadable, ignoring: {path.name} ({exc})")
            continue

        cols = set(head.columns)
        if VALUE_COLUMN not in cols or 'Year' not in cols:
            continue          # not a SAIPE file; nothing to say about it

        if {'LEGID', 'house'} <= cols:
            kind, id_col, level, levels = 'legislative', 'LEGID', 'legislative', ['sldu', 'sldl']
        elif 'GEOID' in cols:
            widths = head['GEOID'].dropna().str.len().mode()
            width = int(widths.iloc[0]) if len(widths) else 0
            level = GEOID_WIDTH_TO_LEVEL.get(width)
            if not level:
                logging.warning(f"  {path.name}: GEOIDs are {width} characters, "
                                f"which matches no geography level — ignoring")
                logging.warning(f"      expected one of: " + ", ".join(
                    "{} for {}".format(w, l) for w, l in sorted(GEOID_WIDTH_TO_LEVEL.items())))
                continue
            kind, id_col, levels = level, 'GEOID', [level]
        else:
            logging.warning(f"  {path.name}: has {VALUE_COLUMN} but no GEOID or "
                            f"LEGID column — ignoring")
            continue

        if kind in found:
            logging.error(f"Two files both look like {kind} data: "
                          f"{found[kind]['file']} and {path.name}")
            logging.error("Remove or move one; there is no way to tell which is intended.")
            sys.exit(1)

        found[kind] = {'file': path.name, 'id_col': id_col,
                       'geo_level': level, 'levels': levels}
        logging.info(f"  {path.name}  ->  {kind}")

    if not found:
        logging.error(f"No SAIPE files found in {directory}")
        logging.error(f"Files must contain '{VALUE_COLUMN}' and 'Year' columns, "
                      f"plus GEOID or LEGID.")
        sys.exit(1)
    return found


def find_malformed(df, id_col):
    """Flag identifiers that cannot be trusted, rather than quietly repairing them.

    Spreadsheets turn long numeric IDs into scientific notation ('2.5e+07').
    format_geoid truncates at the '.' and zero-pads the remainder, which converts
    a mangled Massachusetts district into '00002' — a wrong value that looks
    entirely reasonable and simply fails to match any geography later. Losing a
    whole state that way, silently, is the failure worth preventing.
    """
    raw = df[id_col].astype(str)
    scientific = raw.str.contains(r'[eE][+-]', na=False)
    wrong_width = df.apply(
        lambda r: len(r['geo_id']) != EXPECTED_WIDTH.get(r['geo_level'], len(r['geo_id'])),
        axis=1)
    return scientific | wrong_width


def load_file(spec):
    """Read one SAIPE CSV and return it as long-format rows."""
    filename = spec['file']
    path = os.path.join(REVAMP_DIR, filename)
    if not os.path.exists(path):
        logging.warning(f"  Missing: {filename} — skipping")
        return pd.DataFrame()

    id_col = spec['id_col']
    # dtype=str on the id column is the whole reason leading zeros survive:
    # read as a number, '01001' becomes 1001 and matches no county at all.
    df = pd.read_csv(path, dtype={id_col: str}, low_memory=False)

    missing_id = df[id_col].isna().sum()
    if missing_id:
        logging.warning(f"  {filename}: {missing_id} row(s) have no {id_col} — dropping")
        df = df[df[id_col].notna()]

    if spec['geo_level'] == 'legislative':
        # 'upper' is the state senate (sldu); everything else is the house (sldl).
        df['geo_level'] = df['house'].apply(
            lambda h: 'sldu' if str(h).strip().lower() == 'upper' else 'sldl')
    else:
        df['geo_level'] = spec['geo_level']

    # Zero-pad to the width the geographies table uses for each level.
    df['geo_id'] = df.apply(
        lambda row: format_geoid(row[id_col], row['geo_level']), axis=1)

    df['year'] = df['Year'].astype(int)
    df['indicator_id'] = INDICATOR_NAME
    # results_data.value is a text column; the API casts it when aggregating.
    df['value'] = df[VALUE_COLUMN].astype(str)

    bad = find_malformed(df, id_col)
    if bad.any():
        sample = df.loc[bad, [id_col, 'geo_id', 'geo_level']].head(5)
        logging.error(f"  {filename}: {bad.sum()} identifier(s) are malformed")
        for _, row in sample.iterrows():
            logging.error(f"      {row[id_col]!r} -> {row['geo_id']!r} ({row['geo_level']})")
        by_state = df.loc[bad, 'geo_id'].str[:2].value_counts().to_dict()
        logging.error(f"      affected state prefixes: {by_state}")
        MALFORMED.append((filename, int(bad.sum())))
        df = df[~bad]

    out = df[['geo_id', 'geo_level', 'year', 'indicator_id', 'value']]
    out = out.dropna(subset=['value'])
    logging.info(f"  {filename}: {len(out):,} rows "
                 f"({', '.join(sorted(out['geo_level'].unique()))})")
    return out


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--dry-run', action='store_true',
                        help='Validate the data without modifying the database.')
    parser.add_argument('--allow-malformed', action='store_true',
                        help='Load anyway, accepting that the affected areas will '
                             'be missing from the dashboard.')
    parser.add_argument('--only', nargs='+', choices=KINDS, metavar='SOURCE',
                        help='Load only these sources ({}). Existing rows for the '
                             'levels NOT selected are left untouched, so sources can '
                             'be loaded separately.'.format(', '.join(KINDS)))
    args = parser.parse_args()

    target = confirm_target("load SAIPE poverty data into", dry_run=args.dry_run)
    # Keepalives matter over the public internet: RDS is reached across it, and a
    # long bulk load on an idle-looking socket is what gets silently severed.
    engine = create_engine(target.url, connect_args={
        'keepalives': 1, 'keepalives_idle': 30,
        'keepalives_interval': 10, 'keepalives_count': 5,
    })

    logging.info(f"=== Looking for source files in {os.path.abspath(REVAMP_DIR)} ===")
    discovered = discover_sources(REVAMP_DIR)

    selected = {k: v for k, v in discovered.items()
                if not args.only or k in args.only}
    if args.only:
        absent = [k for k in args.only if k not in discovered]
        if absent:
            logging.error(f"Asked for {', '.join(absent)} but no such file was found.")
            logging.error(f"Found: {', '.join(sorted(discovered)) or 'nothing'}")
            sys.exit(1)
    # Only the levels being loaded are replaced. Deleting every row for the
    # indicator would silently destroy a source loaded on an earlier run.
    levels = sorted({lvl for spec in selected.values() for lvl in spec['levels']})
    logging.info("=== Reading source files: {} ===".format(', '.join(sorted(selected))))
    logging.info("    replacing geo levels: {}".format(', '.join(levels)))
    parts = [load_file(spec) for spec in selected.values()]
    new_df = pd.concat([p for p in parts if not p.empty], ignore_index=True)

    if new_df.empty:
        logging.error("No data found. Aborting.")
        sys.exit(1)

    if MALFORMED and not args.allow_malformed:
        total = sum(n for _, n in MALFORMED)
        logging.error("")
        logging.error(f"Refusing to load: {total} identifier(s) across "
                      f"{len(MALFORMED)} file(s) are unusable.")
        logging.error("These rows would be dropped, so whole districts would be "
                      "missing from the dashboard with nothing to indicate it.")
        logging.error("")
        logging.error("Usually a spreadsheet converted an ID column to a number. "
                      "Re-export with that column formatted as text.")
        logging.error("To proceed regardless: --allow-malformed")
        sys.exit(1)

    logging.info(f"Prepared {len(new_df):,} rows for '{INDICATOR_NAME}'")
    logging.info(f"Rows per level:\n{new_df.groupby('geo_level').size().to_string()}")
    logging.info(f"Years: {sorted(new_df['year'].unique())}")

    # Every row must point at a geography that exists, or it is invisible to the
    # dashboard and violates the relationship the schema assumes.
    with engine.connect() as conn:
        existing = pd.read_sql(
            "SELECT DISTINCT geo_id, geo_level::text AS geo_level, year FROM geographies",
            conn)

    merged = new_df.merge(existing, on=['geo_id', 'geo_level', 'year'],
                          how='left', indicator=True)
    orphans = merged[merged['_merge'] == 'left_only']
    if len(orphans):
        logging.warning(f"  {len(orphans):,} row(s) match no geography and will be dropped")
        logging.warning("  by level:\n" + orphans.groupby('geo_level').size().to_string())
        logging.warning("  examples: " + ", ".join(
            orphans['geo_id'].head(5).tolist()))
    new_df = merged[merged['_merge'] == 'both'][
        ['geo_id', 'geo_level', 'year', 'indicator_id', 'value']]

    if new_df.empty:
        logging.error("Nothing left after matching against geographies. Aborting.")
        sys.exit(1)
    logging.info(f"{len(new_df):,} rows will be written")

    if args.dry_run:
        logging.info("Dry run — no changes written.")
        return

    with engine.connect() as conn:
        before = conn.execute(
            text("SELECT COUNT(*) FROM results_data WHERE indicator_id = :n"),
            {"n": INDICATOR_NAME}).scalar()
        scoped = conn.execute(
            text("SELECT COUNT(*) FROM results_data WHERE indicator_id = :n "
                 "AND geo_level::text = ANY(:levels)"),
            {"n": INDICATOR_NAME, "levels": levels}).scalar()
    logging.info(f"=== Existing rows: {before:,} total, "
                 f"{scoped:,} in the levels being replaced ===")

    logging.info("=== Staging rows ===")
    copy_chunks(engine, new_df)

    # Everything below runs inside the database: no rows cross the network, so a
    # flaky link cannot interrupt the part that has to be atomic.
    logging.info("=== Swapping into results_data ===")
    with engine.begin() as conn:
        conn.execute(
            text("DELETE FROM results_data WHERE indicator_id = :n "
                 "AND geo_level::text = ANY(:levels)"),
            {"n": INDICATOR_NAME, "levels": levels})
        conn.execute(text(
            f"INSERT INTO results_data ({', '.join(COLUMNS)}) "
            f"SELECT {', '.join(COLUMNS)} FROM {STAGING_TABLE}"))
        conn.execute(text(f"DROP TABLE {STAGING_TABLE}"))

    with engine.connect() as conn:
        after = conn.execute(
            text("SELECT COUNT(*) FROM results_data WHERE indicator_id = :n"),
            {"n": INDICATOR_NAME}).scalar()
    logging.info(f"=== Rows after load: {after:,} (delta {after - before:+,}) ===")

    logging.info("Done.")
    logging.info(f"Next: add '{INDICATOR_NAME}' to the dashboard config with")
    logging.info("  python3 ../../scripts/echo.py sync-indicators")


if __name__ == "__main__":
    main()
