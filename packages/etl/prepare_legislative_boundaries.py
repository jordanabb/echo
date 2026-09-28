"""
Turn raw Census TIGER/Line legislative district shapefiles into the format the
ECHO geography pipeline expects.

TIGER publishes state legislative districts one file per state per chamber, with
none of the columns this project keys on: no year (it is only in the filename),
no chamber (only implied by SLDU vs SLDL), and the name field is called
something else. This script merges them and produces a single shapefile whose
schema matches ECHO REVAMP/legdistgeos/leg_dist_geos_mar.shp exactly, so
create_national.py and the geometry loaders need no changes.

    Year   str   the data vintage, e.g. "2023"
    State  str   two-letter abbreviation, e.g. "AL"
    GEOID  str   5 characters, leading zeros preserved
    Name   str   "State Senate District 1 (2022), Alabama"
    house  str   "upper" or "lower"

Reads and writes with fiona rather than geopandas, matching create_national.py
and convert_shapefiles.py -- and avoiding geopandas' incompatibility with
fiona 1.10, which breaks read_file outright.

Usage:
    # inspect what would be produced, writing nothing
    python3 prepare_legislative_boundaries.py --input ~/Downloads/tiger2023 --dry-run

    # write a standalone shapefile for the new year
    python3 prepare_legislative_boundaries.py --input ~/Downloads/tiger2023 \
        --output "../../ECHO REVAMP/legdistgeos/leg_dist_2023.shp"

    # or append the new year onto the existing master file
    python3 prepare_legislative_boundaries.py --input ~/Downloads/tiger2023 \
        --append-to "../../ECHO REVAMP/legdistgeos/leg_dist_geos_mar.shp"

Appending refuses to run if the target already contains the year being added,
so re-running it cannot silently double the districts.

File naming
-----------
Input names matter. TIGER files are found by looking for "sldu" or "sldl" in
the filename, and the vintage is read from the "tl_<year>_" prefix, so keep
Census's own names: tl_2023_01_sldu.shp. Renaming them either hides the file
or loses the year (--year overrides the latter).

Output names do not matter -- load_geographies.py takes whatever path it is
given. The convention here is one file per vintage, beside the existing
boundaries:

    ECHO REVAMP/legdistgeos/leg_dist_<year>.shp

Either .shp or .geojson works; the extension selects the format and both are
read back identically. .shp is the default because it matches the file already
in that folder and is roughly half the size, which matters when it is synced to
S3. The tradeoff is that shapefile attribute fields have fixed widths -- Name is
80 characters in the existing file -- and anything longer is truncated without
warning. GeoJSON has no such limit and can be read in a text editor.
"""
import argparse
import datetime
import logging
import pathlib
import re
import shutil
import sys

import fiona
from fiona.crs import CRS
from shapely.geometry import MultiPolygon, mapping, shape
from shapely.ops import transform as shapely_transform

logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')

# The pipeline reads these five fields and nothing else; every one is a string
# in the existing file, including Year.
OUTPUT_COLUMNS = ['Year', 'State', 'GEOID', 'Name', 'house']

# Everything ECHO stores is WGS84, and the geographies column is declared
# geometry(MultiPolygon, 4326). TIGER ships NAD83, so a transform is usually
# needed -- the shift is under a metre, but the label has to be right.
TARGET_EPSG = 4326

# State legislative district GEOIDs are state FIPS + 3 characters.
GEOID_WIDTH = 5

# TIGER names the chamber through the file name of a per-state download...
CHAMBERS = {'sldu': 'upper', 'sldl': 'lower'}

# ...and inside the data itself, which is the only thing a merged file has.
MTFCC_CHAMBER = {'G5210': 'upper', 'G5220': 'lower'}

OUTPUT_SCHEMA = {
    'geometry': 'MultiPolygon',
    'properties': [(column, 'str:80') for column in OUTPUT_COLUMNS],
}

FIPS = {
    '01': ('AL', 'Alabama'),        '02': ('AK', 'Alaska'),
    '04': ('AZ', 'Arizona'),        '05': ('AR', 'Arkansas'),
    '06': ('CA', 'California'),     '08': ('CO', 'Colorado'),
    '09': ('CT', 'Connecticut'),    '10': ('DE', 'Delaware'),
    '11': ('DC', 'District of Columbia'),
    '12': ('FL', 'Florida'),        '13': ('GA', 'Georgia'),
    '15': ('HI', 'Hawaii'),         '16': ('ID', 'Idaho'),
    '17': ('IL', 'Illinois'),       '18': ('IN', 'Indiana'),
    '19': ('IA', 'Iowa'),           '20': ('KS', 'Kansas'),
    '21': ('KY', 'Kentucky'),       '22': ('LA', 'Louisiana'),
    '23': ('ME', 'Maine'),          '24': ('MD', 'Maryland'),
    '25': ('MA', 'Massachusetts'),  '26': ('MI', 'Michigan'),
    '27': ('MN', 'Minnesota'),      '28': ('MS', 'Mississippi'),
    '29': ('MO', 'Missouri'),       '30': ('MT', 'Montana'),
    '31': ('NE', 'Nebraska'),       '32': ('NV', 'Nevada'),
    '33': ('NH', 'New Hampshire'),  '34': ('NJ', 'New Jersey'),
    '35': ('NM', 'New Mexico'),     '36': ('NY', 'New York'),
    '37': ('NC', 'North Carolina'), '38': ('ND', 'North Dakota'),
    '39': ('OH', 'Ohio'),           '40': ('OK', 'Oklahoma'),
    '41': ('OR', 'Oregon'),         '42': ('PA', 'Pennsylvania'),
    '44': ('RI', 'Rhode Island'),   '45': ('SC', 'South Carolina'),
    '46': ('SD', 'South Dakota'),   '47': ('TN', 'Tennessee'),
    '48': ('TX', 'Texas'),          '49': ('UT', 'Utah'),
    '50': ('VT', 'Vermont'),        '51': ('VA', 'Virginia'),
    '53': ('WA', 'Washington'),     '54': ('WV', 'West Virginia'),
    '55': ('WI', 'Wisconsin'),      '56': ('WY', 'Wyoming'),
    '72': ('PR', 'Puerto Rico'),
}


def pick(available, *candidates):
    """First candidate column present, ignoring case. None if none of them are.

    Sources differ on capitalisation and on which name they use -- TIGER says
    STATEFP and NAMELSAD, a file someone has already reshaped may say state and
    Name -- and an exact-match lookup rejects the second kind for no good
    reason.
    """
    lookup = {str(col).lower(): col for col in available}
    for name in candidates:
        if name.lower() in lookup:
            return lookup[name.lower()]
    return None


# Reverse of FIPS, so a file identifying states by abbreviation is as usable as
# one using the numeric code.
BY_ABBREV = {abbrev: (fips, name) for fips, (abbrev, name) in FIPS.items()}


def resolve_state(props, state_col, geo_id):
    """Return (abbreviation, full name), or (None, None) if it cannot be told.

    Accepts a FIPS code or a postal abbreviation, and falls back to the leading
    two characters of the GEOID, which are the state FIPS by construction.
    """
    raw = str(props.get(state_col, '')).strip() if state_col else ''

    if raw:
        digits = raw.zfill(2)
        if digits in FIPS:
            return FIPS[digits]
        upper = raw.upper()
        if upper in BY_ABBREV:
            _, name = BY_ABBREV[upper]
            return upper, name

    prefix = geo_id[:2]
    if prefix in FIPS:
        return FIPS[prefix]
    return None, None


def find_inputs(location):
    """Return [(path, chamber_or_None)] for the shapefile(s) to read.

    Accepts either a single file -- including one already merged to cover both
    chambers and every state -- or a directory, searched recursively because
    unzipping a hundred TIGER archives usually leaves a hundred folders rather
    than one flat pile.

    A chamber of None means the filename did not say, and it has to be worked
    out per row from the data instead.
    """
    location = pathlib.Path(location).expanduser()

    if location.is_file():
        return [(location, chamber_from_filename(location))]

    if not location.is_dir():
        logging.error(f"No such file or directory: {location}")
        sys.exit(1)

    found = []
    for path in sorted(location.rglob('*.shp')) + sorted(location.rglob('*.geojson')):
        found.append((path, chamber_from_filename(path)))

    if not found:
        logging.error(f"No shapefiles found under {location}")
        logging.error("Unzip the TIGER downloads first; this looks for .shp/.geojson.")
        sys.exit(1)
    return found


def chamber_from_filename(path):
    """'upper'/'lower' if TIGER's naming says so, else None."""
    lowered = path.name.lower()
    for marker, chamber in CHAMBERS.items():
        if marker in lowered:
            return chamber
    return None


def resolve_chamber(props, available, filename_chamber, override):
    """Work out which chamber a district belongs to, or None if nothing says.

    A merged file covering both chambers cannot say so through its name, so the
    data has to. TIGER marks it with MTFCC (G5210 upper, G5220 lower); a file
    already in ECHO format carries 'house'; and the per-chamber district number
    columns only ever appear in their own chamber's file.
    """
    if override:
        return override
    if filename_chamber:
        return filename_chamber

    house_col = pick(available, 'house', 'chamber', 'HOUSE')
    if house_col and props.get(house_col):
        return 'upper' if str(props[house_col]).strip().lower() in ('upper', 'u', 'senate') \
            else 'lower'

    mtfcc_col = pick(available, 'MTFCC', 'MTFCC20')
    if mtfcc_col and props.get(mtfcc_col):
        return MTFCC_CHAMBER.get(str(props[mtfcc_col]).strip().upper())

    upper_col = pick(available, 'SLDUST', 'SLDUST20')
    lower_col = pick(available, 'SLDLST', 'SLDLST20')
    if upper_col and not lower_col:
        return 'upper'
    if lower_col and not upper_col:
        return 'lower'
    return None


def year_from_filename(path):
    """TIGER encodes the vintage as tl_<year>_<state>_<layer>.shp."""
    match = re.search(r'tl_(\d{4})_', path.name)
    return match.group(1) if match else None


def _reprojector(source_crs):
    """Return a function that moves geometry to WGS84, or None when already there."""
    if not source_crs:
        logging.warning(f"  no CRS recorded; assuming EPSG:{TARGET_EPSG}")
        return None
    try:
        epsg = CRS.from_user_input(source_crs).to_epsg()
    except Exception:
        epsg = None
    if epsg == TARGET_EPSG:
        return None

    from pyproj import Transformer
    transformer = Transformer.from_crs(source_crs, f"EPSG:{TARGET_EPSG}", always_xy=True)
    return lambda geom: shapely_transform(transformer.transform, geom)


def read_one(path, chamber, year_override, house_override=None):
    """Read one TIGER file and yield rows already shaped for the ECHO schema."""
    year = year_override or year_from_filename(path)
    if not year:
        # A file already in ECHO format carries the vintage in a column.
        with fiona.open(str(path)) as probe:
            if 'Year' in probe.schema['properties']:
                first = next(iter(probe), None)
                if first:
                    year = str(first['properties']['Year']).strip()
    if not year:
        logging.error(f"Cannot tell which year {path.name} is for.")
        logging.error("Pass --year explicitly, or keep TIGER's tl_<year>_... names.")
        sys.exit(1)

    rows = []
    with fiona.open(str(path)) as src:
        available = set(src.schema['properties'])
        geoid_col = pick(available, 'GEOID', 'GEOID20', 'GEOID10', 'geo_id')
        name_col = pick(available, 'NAMELSAD', 'NAMELSAD20', 'Name', 'NAME', 'geo_name')
        state_col = pick(available, 'STATEFP', 'STATEFP20', 'STATEFP10',
                         'state_fips', 'state', 'STUSPS', 'State')
        lsy_col = pick(available, 'LSY', 'LSY20')

        if not geoid_col or not name_col:
            wanted = [n for n, c in (('GEOID', geoid_col), ('a name', name_col)) if not c]
            logging.warning(f"  {path.name}: no column for {' and '.join(wanted)} "
                            f"— skipping")
            logging.warning(f"      columns present: {sorted(available)}")
            return rows

        reproject = _reprojector(src.crs)
        skipped_states = set()

        for feature in src:
            props = feature['properties']
            # Read as text throughout: a GEOID that becomes a number loses its
            # leading zero and then matches no geography.
            geo_id = str(props[geoid_col]).strip()
            abbrev, state_name = resolve_state(props, state_col, geo_id)
            if not abbrev:
                skipped_states.add(str(props.get(state_col, '')).strip() or geo_id[:2])
                continue

            house = resolve_chamber(props, available, chamber, house_override)
            if house is None:
                logging.error(f"  {path.name}: cannot tell which chamber these "
                              f"districts belong to.")
                logging.error("  The filename does not say, and there is no 'house',")
                logging.error("  'MTFCC', 'SLDUST' or 'SLDLST' column to go on.")
                logging.error("  Pass --house upper or --house lower if this file "
                              "holds one chamber.")
                sys.exit(1)

            # The existing names carry the districting plan's year in brackets,
            # which TIGER supplies as LSY (legislative session year).
            plan_year = str(props[lsy_col]).strip() if lsy_col and props.get(lsy_col) else ''
            if not plan_year or plan_year.lower() == 'none':
                plan_year = year

            geom = shape(feature['geometry'])
            if reproject:
                geom = reproject(geom)
            # The geographies column is declared MultiPolygon, so normalise now
            # rather than letting a single-part polygon fail on insert.
            if geom.geom_type == 'Polygon':
                geom = MultiPolygon([geom])

            rows.append({
                'geometry': geom,
                'properties': {
                    'Year': str(year),
                    'State': abbrev,
                    'GEOID': geo_id,
                    'Name': "{} ({}), {}".format(
                        str(props[name_col]).strip(), plan_year, state_name),
                    'house': house,
                },
            })

        if skipped_states:
            logging.warning(f"  {path.name}: unrecognised state FIPS "
                            f"{sorted(skipped_states)} — those rows skipped")
    return rows


def validate(rows):
    """Report anything that would fail to match a geography once loaded."""
    problems = 0

    widths = {}
    for row in rows:
        widths[len(row['properties']['GEOID'])] = widths.get(
            len(row['properties']['GEOID']), 0) + 1
    if set(widths) != {GEOID_WIDTH}:
        logging.error(f"  GEOID widths present: {widths} (expected all {GEOID_WIDTH})")
        problems += 1

    blank = sum(1 for r in rows if not r['properties']['GEOID'])
    if blank:
        logging.error(f"  {blank} row(s) have no GEOID")
        problems += 1

    empty = sum(1 for r in rows if r['geometry'].is_empty)
    if empty:
        logging.error(f"  {empty} row(s) have no geometry")
        problems += 1

    seen, dupes = set(), 0
    for r in rows:
        p = r['properties']
        key = (p['GEOID'], p['house'], p['Year'])
        if key in seen:
            dupes += 1
        seen.add(key)
    if dupes:
        logging.error(f"  {dupes} duplicate (GEOID, house, Year) row(s)")
        problems += 1

    return problems


def write_shapefile(path, rows):
    path = pathlib.Path(path).expanduser()
    path.parent.mkdir(parents=True, exist_ok=True)
    with fiona.open(str(path), 'w', driver='ESRI Shapefile',
                    crs=CRS.from_epsg(TARGET_EPSG), schema=OUTPUT_SCHEMA) as dst:
        for row in rows:
            dst.write({'geometry': mapping(row['geometry']),
                       'properties': row['properties']})
    return path


def backup_shapefile(path):
    """Copy every sidecar file, not just the .shp.

    A shapefile is a set -- .shp, .shx, .dbf, .prj, .cpg -- and copying only the
    .shp produces something GDAL cannot open at all. That is worse than having
    no backup, because it looks like one until the moment it is needed.
    """
    stamp = datetime.datetime.now().strftime('%Y%m%d_%H%M%S')
    backup_dir = path.parent / "{}_backup_{}".format(path.stem, stamp)
    backup_dir.mkdir()
    copied = 0
    for sidecar in sorted(path.parent.glob(path.stem + '.*')):
        if sidecar.is_file():
            shutil.copy2(str(sidecar), str(backup_dir / sidecar.name))
            copied += 1
    return backup_dir, copied


def read_existing(path):
    """Read an ECHO-format legislative shapefile back into the same row shape."""
    rows = []
    with fiona.open(str(path)) as src:
        for feature in src:
            geom = shape(feature['geometry'])
            if geom.geom_type == 'Polygon':
                geom = MultiPolygon([geom])
            rows.append({
                'geometry': geom,
                'properties': {c: str(feature['properties'].get(c, '') or '')
                               for c in OUTPUT_COLUMNS},
            })
    return rows


def main():
    parser = argparse.ArgumentParser(description=__doc__,
                                     formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument('--input', required=True,
                        help='A shapefile, or a folder of them (searched recursively). '
                             'A single merged file covering both chambers and every '
                             'state works too.')
    parser.add_argument('--house', choices=['upper', 'lower'],
                        help='Force the chamber. Only needed when one file holds a '
                             'single chamber and neither its name nor its columns say so.')
    parser.add_argument('--year',
                        help='Data vintage to record. Default: read from the tl_<year>_ filename.')
    parser.add_argument('--output', help='Write a standalone shapefile here.')
    parser.add_argument('--append-to',
                        help='Append onto an existing ECHO legislative shapefile instead.')
    parser.add_argument('--dry-run', action='store_true',
                        help='Report what would be produced without writing anything.')
    args = parser.parse_args()

    if not (args.output or args.append_to or args.dry_run):
        parser.error("give --output, --append-to, or --dry-run")

    logging.info("=== Finding input files ===")
    files = find_inputs(args.input)
    logging.info(f"Found {len(files)} file(s)")

    rows = []
    for path, chamber in files:
        got = read_one(path, chamber, args.year, args.house)
        if got:
            rows.extend(got)
            chambers = sorted({r['properties']['house'] for r in got})
            logging.info(f"  {path.name}: {len(got):,} districts "
                         f"({', '.join(chambers)})")

    if not rows:
        logging.error("Nothing usable was read.")
        sys.exit(1)

    logging.info("=== Result ===")
    tally = {}
    for row in rows:
        key = (row['properties']['Year'], row['properties']['house'])
        tally[key] = tally.get(key, 0) + 1
    for (year, house), n in sorted(tally.items()):
        logging.info(f"  {year}  {house:<6} {n:>6} districts")
    states = {r['properties']['State'] for r in rows}
    logging.info(f"  {len(states)} states/territories, {len(rows):,} rows total")

    logging.info("=== Validating ===")
    if validate(rows):
        logging.error("Refusing to continue while the above is unresolved.")
        sys.exit(1)
    logging.info("  no problems found")

    if args.append_to:
        target = pathlib.Path(args.append_to).expanduser()
        if not target.exists():
            logging.error(f"No such file: {target}")
            sys.exit(1)

        existing = read_existing(target)
        existing_years = {r['properties']['Year'] for r in existing}
        new_years = {r['properties']['Year'] for r in rows}

        clash = sorted(existing_years & new_years)
        if clash:
            logging.error(f"{target.name} already contains year(s) {clash}.")
            logging.error("Appending would duplicate every district for those years.")
            logging.error("Use --output to write a separate file instead.")
            sys.exit(1)

        if args.dry_run:
            logging.info(f"Dry run — would append {len(rows):,} rows to {target.name}, "
                         f"giving {len(existing) + len(rows):,} total.")
            return

        backup_dir, copied = backup_shapefile(target)
        logging.info(f"Backed up {copied} file(s) to {backup_dir.name}/")
        write_shapefile(target, existing + rows)
        logging.info(f"Wrote {len(existing) + len(rows):,} rows to {target}")
    else:
        if args.dry_run:
            logging.info(f"Dry run — would write {len(rows):,} rows.")
            return
        written = write_shapefile(args.output, rows)
        logging.info(f"Wrote {len(rows):,} rows to {written}")

    logging.info("")
    logging.info("Next: regenerate the geography rows and load them, then re-run")
    logging.info("the poverty load so the new year's rows find their districts:")
    logging.info("  python3 create_national.py")
    logging.info("  python3 convert_shapefiles.py")
    logging.info("  python3 load_geometry_national_fast.py")
    logging.info("  python3 load_saipe.py --only legislative")


if __name__ == '__main__':
    main()
