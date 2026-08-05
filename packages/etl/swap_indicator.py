"""
Surgically swap out one or more indicators in results_data without
touching the rest of the dataset.

Defaults are set up for educational attainment (hs_edu, college) sourced
from the *_acs.csv files in ECHO REVAMP. To swap other indicators,
edit INDICATORS_TO_SWAP and SOURCE_FILES below.

Process (atomic, single transaction):
  1. Read the CSVs and melt them into long format (geo_id, year, indicator_id, value).
  2. DELETE existing rows in results_data for the target indicator_ids.
  3. INSERT the new rows.
  4. Print before/after counts for sanity.

Usage:
    python3 swap_indicator.py              # do the swap
    python3 swap_indicator.py --dry-run    # validate without writing
"""
import argparse
import logging
import os
import sys

import pandas as pd
from sqlalchemy import create_engine, text

from create_national import REVAMP_DIR, CSV_FILE_MAP, format_geoid
from db_target import confirm_target

logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')

# -----------------------------------------------------------------------------
# Configure what to swap
# -----------------------------------------------------------------------------
# Map raw CSV column → indicator_id stored in results_data.
# These display names MUST match the "name" field in indicator_config.py.
INDICATORS_TO_SWAP = {
    "hs_edu": "High-School Diploma (% Adults 25+ Yrs)",
    "college": "College Degree Attained (% Adults 25+ Yrs)",
}

# Which CSV files carry the new data, by geo_level. Only the columns named
# in INDICATORS_TO_SWAP (plus geo_id and year) are read from each file.
SOURCE_FILES = {
    'county':                 'counties_acs.csv',
    'tract':                  'tracts_acs.csv',
    'school_district':        'school_districts_acs.csv',
    'legislative':            'leg_dists_acs.csv',  # produces sldu + sldl rows
    'congressional_district': 'cong_dist_acs.csv',
}

# -----------------------------------------------------------------------------

def find_id_col(geo_level: str) -> str:
    """Look up the CSV id column convention used for this geo_level."""
    for csv_info in CSV_FILE_MAP.get(geo_level, []):
        if csv_info['type'] == 'acs':
            return csv_info['id_col']
    return 'GEOID'


def load_csv_to_long(geo_level: str, filename: str) -> pd.DataFrame:
    """Read one CSV, keep only the indicator columns of interest, return long format."""
    path = os.path.join(REVAMP_DIR, filename)
    if not os.path.exists(path):
        logging.warning(f"  Missing file for {geo_level}: {filename} — skipping")
        return pd.DataFrame()

    df = pd.read_csv(path, low_memory=False)
    df = df.loc[:, ~df.columns.str.contains('^Unnamed')]

    id_col = find_id_col(geo_level)
    if id_col in df.columns:
        df = df.rename(columns={id_col: 'geo_id'})
    elif 'GEOID' in df.columns:
        df = df.rename(columns={'GEOID': 'geo_id'})
    else:
        logging.warning(f"  {filename}: no id column ({id_col}) — skipping")
        return pd.DataFrame()

    if 'year' not in df.columns:
        for col in df.columns:
            if col.lower() == 'year':
                df = df.rename(columns={col: 'year'})
                break

    if 'geo_id' not in df.columns or 'year' not in df.columns:
        logging.warning(f"  {filename}: missing geo_id or year — skipping")
        return pd.DataFrame()

    present_cols = [c for c in INDICATORS_TO_SWAP if c in df.columns]
    if not present_cols:
        logging.warning(f"  {filename}: none of {list(INDICATORS_TO_SWAP)} present — skipping")
        return pd.DataFrame()

    # Handle legislative: the leg CSV typically has a 'house' column to distinguish sldu/sldl
    if geo_level == 'legislative':
        house_col = next((c for c in df.columns if c.lower() == 'house'), None)
        if not house_col:
            logging.warning(f"  {filename}: legislative file missing 'house' column — skipping")
            return pd.DataFrame()
        df['geo_level'] = df[house_col].apply(
            lambda h: 'sldu' if str(h).lower() == 'upper' else 'sldl'
        )
        df['geo_id'] = df['geo_id'].apply(lambda x: format_geoid(x, 'sldl'))
    else:
        df['geo_level'] = geo_level
        df['geo_id'] = df['geo_id'].apply(lambda x: format_geoid(x, geo_level))

    keep = ['geo_id', 'geo_level', 'year'] + present_cols
    df = df[keep]

    # Rename CSV columns → indicator_id display names, then melt
    df = df.rename(columns=INDICATORS_TO_SWAP)
    value_vars = [INDICATORS_TO_SWAP[c] for c in present_cols]

    long_df = pd.melt(
        df,
        id_vars=['geo_id', 'geo_level', 'year'],
        value_vars=value_vars,
        var_name='indicator_id',
        value_name='value',
    )
    long_df = long_df.dropna(subset=['value'])
    long_df = long_df[long_df['value'].astype(str) != 'NA']
    long_df['value'] = long_df['value'].astype(str)
    return long_df


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--dry-run', action='store_true',
                        help='Validate the new data without modifying the database.')
    args = parser.parse_args()

    target = confirm_target("swap indicators in", dry_run=args.dry_run)
    engine = create_engine(target.url)
    indicator_ids = list(INDICATORS_TO_SWAP.values())

    # Build the new long-format dataframe from all source CSVs
    logging.info("=== Reading new CSVs ===")
    parts = []
    for geo_level, filename in SOURCE_FILES.items():
        logging.info(f"  {geo_level}: {filename}")
        parts.append(load_csv_to_long(geo_level, filename))
    new_df = pd.concat([p for p in parts if not p.empty], ignore_index=True)

    if new_df.empty:
        logging.error("No new data found. Aborting.")
        sys.exit(1)

    logging.info(f"Prepared {len(new_df):,} rows across {new_df['indicator_id'].nunique()} indicators "
                 f"and {new_df['geo_level'].nunique()} geo levels.")
    logging.info(f"Rows per indicator:\n{new_df.groupby('indicator_id').size().to_string()}")

    # Verify all geo_id/geo_level/year tuples exist in geographies (FK)
    with engine.connect() as conn:
        existing_geos = pd.read_sql(
            "SELECT DISTINCT geo_id, geo_level::text AS geo_level, year FROM geographies",
            conn,
        )
    merged = new_df.merge(existing_geos, on=['geo_id', 'geo_level', 'year'], how='left', indicator=True)
    orphan_count = (merged['_merge'] == 'left_only').sum()
    if orphan_count:
        logging.warning(f"  {orphan_count:,} new rows don't match any (geo_id, geo_level, year) in geographies — they will be dropped.")
        new_df = merged[merged['_merge'] == 'both'][['geo_id', 'geo_level', 'year', 'indicator_id', 'value']]

    if args.dry_run:
        logging.info("Dry run — no changes written. Stopping here.")
        return

    # Atomic swap
    with engine.begin() as conn:
        before = conn.execute(
            text("SELECT COUNT(*) FROM results_data WHERE indicator_id = ANY(:ids)"),
            {"ids": indicator_ids},
        ).scalar()
        logging.info(f"=== Existing rows for target indicators: {before:,} ===")

        logging.info("Deleting old rows...")
        conn.execute(
            text("DELETE FROM results_data WHERE indicator_id = ANY(:ids)"),
            {"ids": indicator_ids},
        )

        logging.info("Inserting new rows...")
        new_df.to_sql('results_data', conn, if_exists='append', index=False, chunksize=50000)

        after = conn.execute(
            text("SELECT COUNT(*) FROM results_data WHERE indicator_id = ANY(:ids)"),
            {"ids": indicator_ids},
        ).scalar()
        logging.info(f"=== Rows after swap: {after:,} (delta {after - before:+,}) ===")

    logging.info("Swap complete.")


if __name__ == "__main__":
    main()
