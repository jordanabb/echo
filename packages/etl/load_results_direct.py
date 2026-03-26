"""
Load results data file-by-file directly into the database.
Each source CSV is read, transformed, and inserted independently.
Progress is logged after each file.

Usage:
    python3 load_results_direct.py
"""
import pandas as pd
from sqlalchemy import create_engine, text
import os, logging
from dotenv import load_dotenv
from create_national import (
    CSV_FILE_MAP, ALL_RENAMES, ALL_INDICATOR_NAMES,
    REVAMP_DIR, format_geoid, SHAPEFILE_MAP
)
import fiona

logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')

dotenv_path = os.path.join(os.path.dirname(__file__), '..', '..', '.env')
load_dotenv(dotenv_path=dotenv_path)

DB_USER = os.getenv("DB_USER")
DB_PASSWORD = os.getenv("DB_PASSWORD")
DB_HOST = os.getenv("DB_HOST")
DB_PORT = os.getenv("DB_PORT")
DB_NAME = os.getenv("DB_NAME")
DATABASE_URL = f"postgresql://{DB_USER}:{DB_PASSWORD}@{DB_HOST}:{DB_PORT}/{DB_NAME}"
engine = create_engine(DATABASE_URL)

DROP_COLS = ['State', 'state', 'Name', 'name', 'SCHLEV', 'TotalPopulation', 'CountyFIPS']


def get_valid_geo_ids():
    """Build a dict of geo_type -> set of (geo_id, geo_level) from shapefiles."""
    geo_ids = {}
    for geo_type, config in SHAPEFILE_MAP.items():
        shp_path = config['path']
        if not os.path.exists(shp_path):
            continue
        ids = {}
        with fiona.open(shp_path) as src:
            for feat in src:
                props = feat['properties']
                geo_id_raw = str(props[config['id_col']])
                year = int(float(str(props[config['year_col']])))
                if config['geo_level_val'] is None:
                    house = str(props.get(config['house_col'], '')).lower()
                    geo_level = 'sldu' if house == 'upper' else 'sldl'
                else:
                    geo_level = config['geo_level_val']
                geo_id = format_geoid(geo_id_raw, geo_level)
                ids[geo_id] = geo_level
        geo_ids[geo_type] = ids
    return geo_ids


def process_and_load_file(csv_info, geo_type, valid_geo_ids, valid_geos_df, file_num, total_files):
    """Process a single CSV and insert into results_data."""
    filepath = os.path.join(REVAMP_DIR, csv_info['filename'])
    if not os.path.exists(filepath):
        logging.warning(f"  [{file_num}/{total_files}] File not found: {csv_info['filename']}, skipping.")
        return 0

    df = pd.read_csv(filepath, low_memory=False)
    df = df.loc[:, ~df.columns.str.contains('^Unnamed')]

    # Standardize ID column
    id_col = csv_info['id_col']
    if id_col in df.columns:
        df.rename(columns={id_col: 'geo_id'}, inplace=True)
    else:
        for col in df.columns:
            if col.lower() == id_col.lower().replace(' ', ''):
                df.rename(columns={col: 'geo_id'}, inplace=True)
                break
            if col == id_col:
                df.rename(columns={col: 'geo_id'}, inplace=True)
                break

    # Standardize Year column
    for col in df.columns:
        if col.lower() == 'year':
            df.rename(columns={col: 'year'}, inplace=True)
            break

    if 'geo_id' not in df.columns or 'year' not in df.columns:
        logging.warning(f"  [{file_num}/{total_files}] Missing geo_id/year in {csv_info['filename']}, skipping.")
        return 0

    # Format geo_ids
    if geo_type == 'legislative':
        geo_levels = ['sldu', 'sldl']
        df['geo_id'] = df['geo_id'].apply(lambda x: format_geoid(x, 'sldl'))
    else:
        geo_levels = [geo_type]
        df['geo_id'] = df['geo_id'].apply(lambda x: format_geoid(x, geo_type))

    # Filter to valid geo_ids
    valid_ids = set(valid_geo_ids.keys())
    df = df[df['geo_id'].isin(valid_ids)].copy()
    if df.empty:
        logging.warning(f"  [{file_num}/{total_files}] No matching geo_ids in {csv_info['filename']}.")
        return 0

    # Handle legislative geo_level
    if geo_type == 'legislative':
        house_col = None
        for col in df.columns:
            if col.lower() == 'house':
                house_col = col
                break
        if house_col:
            df['geo_level'] = df[house_col].apply(
                lambda h: 'sldu' if str(h).lower() == 'upper' else 'sldl'
            )
            df.drop(columns=[house_col], inplace=True)
        else:
            vg = valid_geos_df[valid_geos_df['geo_level'].isin(geo_levels)]
            df = pd.merge(vg[['geo_id', 'geo_level', 'year']], df, on=['geo_id', 'year'], how='inner')
    else:
        df['geo_level'] = geo_type

    # Drop non-indicator columns
    df.drop(columns=[c for c in DROP_COLS if c in df.columns], inplace=True, errors='ignore')

    # Rename columns
    df.rename(columns=ALL_RENAMES, inplace=True)

    # Melt to long format
    id_vars = ['geo_id', 'geo_level', 'year']
    value_vars = [col for col in df.columns if col in ALL_INDICATOR_NAMES]
    if not value_vars:
        logging.warning(f"  [{file_num}/{total_files}] No indicator columns in {csv_info['filename']}.")
        return 0

    long_df = pd.melt(df, id_vars=id_vars, value_vars=value_vars, var_name='indicator_id', value_name='value')
    long_df.dropna(subset=['value'], inplace=True)
    long_df = long_df[long_df['value'] != 'NA']
    long_df['value'] = long_df['value'].astype(str)

    # Insert into database
    long_df.to_sql('results_data', engine, if_exists='append', index=False, chunksize=50000)

    logging.info(f"  [{file_num}/{total_files}] {csv_info['filename']}: {len(long_df)} rows loaded")
    return len(long_df)


def main():
    logging.info("=== Loading Results File by File ===")

    # Count total files
    total_files = sum(len(files) for files in CSV_FILE_MAP.values())
    file_num = 0
    total_rows = 0

    # Build valid geo_ids from shapefiles
    logging.info("Reading valid geo_ids from shapefiles...")
    all_valid_ids = get_valid_geo_ids()

    # Build a simple geos dataframe for legislative joins
    logging.info("Building geography lookup for legislative districts...")
    geo_rows = []
    for geo_type, ids in all_valid_ids.items():
        for geo_id, geo_level in ids.items():
            geo_rows.append({'geo_id': geo_id, 'geo_level': geo_level})
    # We need year info too — read from DB
    with engine.connect() as conn:
        geos_db = pd.read_sql("SELECT DISTINCT geo_id, geo_level, year FROM geographies", conn)

    for geo_type, csv_list in CSV_FILE_MAP.items():
        logging.info(f"--- {geo_type} ({len(csv_list)} files) ---")

        # Get valid ids for this geo type
        if geo_type == 'legislative':
            valid_ids = {**all_valid_ids.get('legislative', {})}
        else:
            valid_ids = all_valid_ids.get(geo_type, {})

        for csv_info in csv_list:
            file_num += 1
            rows = process_and_load_file(csv_info, geo_type, valid_ids, geos_db, file_num, total_files)
            total_rows += rows

    # Re-add unique constraint
    logging.info("Adding unique constraint...")
    with engine.connect() as conn:
        conn.execute(text("""
            ALTER TABLE results_data ADD CONSTRAINT uq_results_data
            UNIQUE (geo_id, geo_level, year, indicator_id)
        """))
        conn.commit()

    logging.info(f"=== Done! {total_rows} total rows across {file_num} files ===")


if __name__ == "__main__":
    main()
