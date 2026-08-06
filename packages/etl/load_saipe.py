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
import logging
import os
import sys

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

# Source file -> (id column, how to derive geo_level).
# The legislative file covers both chambers and is split by its 'house' column;
# the others map to a single level.
SOURCE_FILES = {
    'saipe_counties_22.csv': {'id_col': 'GEOID', 'geo_level': 'county'},
    'saipe_tracts_22.csv':   {'id_col': 'GEOID', 'geo_level': 'tract'},
    'saipe_leg_22.csv':      {'id_col': 'LEGID', 'geo_level': 'legislative'},
}

# -----------------------------------------------------------------------------


# Width each level's identifier must have once normalised. Letters are allowed —
# several states split legislative districts into lettered subdistricts (MN 27A,
# MD 1A, AK senate A-T) and those are valid Census identifiers.
EXPECTED_WIDTH = {'county': 5, 'tract': 11, 'sldu': 5, 'sldl': 5,
                  'school_district': 7, 'congressional_district': 4}


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


def load_file(filename, spec):
    """Read one SAIPE CSV and return it as long-format rows."""
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
    args = parser.parse_args()

    target = confirm_target("load SAIPE poverty data into", dry_run=args.dry_run)
    engine = create_engine(target.url)

    logging.info("=== Reading source files ===")
    parts = [load_file(name, spec) for name, spec in SOURCE_FILES.items()]
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

    with engine.begin() as conn:
        before = conn.execute(
            text("SELECT COUNT(*) FROM results_data WHERE indicator_id = :n"),
            {"n": INDICATOR_NAME}).scalar()
        logging.info(f"=== Existing rows for this indicator: {before:,} ===")

        conn.execute(text("DELETE FROM results_data WHERE indicator_id = :n"),
                     {"n": INDICATOR_NAME})
        new_df.to_sql('results_data', conn, if_exists='append', index=False,
                      chunksize=50000)

        after = conn.execute(
            text("SELECT COUNT(*) FROM results_data WHERE indicator_id = :n"),
            {"n": INDICATOR_NAME}).scalar()
        logging.info(f"=== Rows after load: {after:,} (delta {after - before:+,}) ===")

    logging.info("Done.")
    logging.info(f"Next: add '{INDICATOR_NAME}' to the dashboard config with")
    logging.info("  python3 ../../scripts/echo.py sync-indicators")


if __name__ == "__main__":
    main()
