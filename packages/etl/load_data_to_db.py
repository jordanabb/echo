import pandas as pd
from sqlalchemy import create_engine, text, String, Integer, Text
import os
from dotenv import load_dotenv
import logging

# --- 1. CONFIGURATION ---
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

# Override with CLEAN_DATA_DIR env var to load national data:
#   CLEAN_DATA_DIR=clean_output_national/ python3 load_data_to_db.py
CLEAN_DATA_DIR = os.getenv("CLEAN_DATA_DIR", "clean_output/")
GEOGRAPHIES_FILE = os.path.join(CLEAN_DATA_DIR, "geographies.csv")
RESULTS_FILE = os.path.join(CLEAN_DATA_DIR, "results.csv")

CHUNK_SIZE = 50000


def ensure_tables_and_constraints():
    """Create tables if they don't exist and ensure unique constraints for upserts."""
    with engine.connect() as conn:
        conn.execute(text("""
            CREATE TABLE IF NOT EXISTS geographies (
                geo_id VARCHAR(20),
                geo_name TEXT,
                geo_level VARCHAR(50),
                year INTEGER,
                state_fips VARCHAR(2),
                geometry geometry(MultiPolygon, 4326)
            )
        """))
        conn.execute(text("""
            CREATE TABLE IF NOT EXISTS results_data (
                geo_id VARCHAR(20),
                geo_level VARCHAR(50),
                year INTEGER,
                indicator_id TEXT,
                value VARCHAR(50)
            )
        """))

        # Add unique constraints if they don't exist (dedup first)
        conn.execute(text("""
            DO $$ BEGIN
                IF NOT EXISTS (SELECT 1 FROM pg_constraint WHERE conname = 'uq_geographies') THEN
                    DELETE FROM geographies g1 USING geographies g2
                    WHERE g1.ctid < g2.ctid
                      AND g1.geo_id = g2.geo_id
                      AND g1.geo_level = g2.geo_level
                      AND g1.year = g2.year;
                    ALTER TABLE geographies ADD CONSTRAINT uq_geographies UNIQUE (geo_id, geo_level, year);
                END IF;
            END $$
        """))
        conn.execute(text("""
            DO $$ BEGIN
                IF NOT EXISTS (SELECT 1 FROM pg_constraint WHERE conname = 'uq_results_data') THEN
                    DELETE FROM results_data r1 USING results_data r2
                    WHERE r1.ctid < r2.ctid
                      AND r1.geo_id = r2.geo_id
                      AND r1.geo_level = r2.geo_level
                      AND r1.year = r2.year
                      AND r1.indicator_id = r2.indicator_id;
                    ALTER TABLE results_data ADD CONSTRAINT uq_results_data UNIQUE (geo_id, geo_level, year, indicator_id);
                END IF;
            END $$
        """))
        conn.commit()
    logging.info("Tables and unique constraints verified.")


def upsert_geographies(df):
    """Upsert geographies using temp table for batch performance."""
    df = df.drop_duplicates(subset=['geo_id', 'geo_level', 'year'], keep='last')

    with engine.connect() as conn:
        for start in range(0, len(df), CHUNK_SIZE):
            chunk = df.iloc[start:start + CHUNK_SIZE]
            chunk[['geo_id', 'geo_name', 'geo_level', 'year', 'state_fips']].to_sql(
                '_tmp_geographies', engine, if_exists='replace', index=False
            )
            conn.execute(text("""
                INSERT INTO geographies (geo_id, geo_name, geo_level, year, state_fips)
                SELECT geo_id, geo_name, geo_level, year, state_fips
                FROM _tmp_geographies
                ON CONFLICT (geo_id, geo_level, year)
                DO UPDATE SET geo_name = EXCLUDED.geo_name,
                             state_fips = EXCLUDED.state_fips
            """))
            conn.execute(text("DROP TABLE IF EXISTS _tmp_geographies"))
            conn.commit()
            logging.info(f"  Geographies: {min(start + CHUNK_SIZE, len(df))}/{len(df)}")

    logging.info(f"-> Geographies complete: {len(df)} rows.")


def load_results_by_indicator(results_file):
    """Load results indicator by indicator, committing after each one."""
    logging.info(f"Reading results from '{results_file}'...")
    df = pd.read_csv(results_file, dtype={'geo_id': str, 'value': str})
    if 'geo_level' in df.columns:
        df['geo_level'] = df['geo_level'].astype(str)
    df = df.drop_duplicates(subset=['geo_id', 'geo_level', 'year', 'indicator_id'], keep='last')

    indicators = df['indicator_id'].unique()
    logging.info(f"Loading {len(df)} rows across {len(indicators)} indicators...")

    for i, indicator in enumerate(indicators, 1):
        indicator_df = df[df['indicator_id'] == indicator]

        with engine.connect() as conn:
            for start in range(0, len(indicator_df), CHUNK_SIZE):
                chunk = indicator_df.iloc[start:start + CHUNK_SIZE]
                chunk.to_sql('_tmp_results', engine, if_exists='replace', index=False)
                conn.execute(text("""
                    INSERT INTO results_data (geo_id, geo_level, year, indicator_id, value)
                    SELECT geo_id, geo_level, year, indicator_id, value FROM _tmp_results
                    ON CONFLICT (geo_id, geo_level, year, indicator_id)
                    DO UPDATE SET value = EXCLUDED.value
                """))
                conn.execute(text("DROP TABLE IF EXISTS _tmp_results"))
                conn.commit()

        logging.info(f"  [{i}/{len(indicators)}] {indicator}: {len(indicator_df)} rows")

    logging.info(f"-> Results complete: {len(df)} rows across {len(indicators)} indicators.")


def load_data():
    """Loads clean, processed files into the database."""
    logging.info("--- Starting Data Load ---")

    try:
        ensure_tables_and_constraints()

        # --- Load Geographies ---
        logging.info(f"Reading geography data from '{GEOGRAPHIES_FILE}'...")
        gdf = pd.read_csv(GEOGRAPHIES_FILE, dtype={'geo_id': str})
        if 'geo_level' in gdf.columns:
            gdf['geo_level'] = gdf['geo_level'].astype(str)
        if 'state_fips' not in gdf.columns:
            gdf['state_fips'] = gdf['geo_id'].str[:2]

        logging.info(f"Upserting {len(gdf)} geographies...")
        upsert_geographies(gdf)

        # --- Load Results (indicator by indicator) ---
        load_results_by_indicator(RESULTS_FILE)

        logging.info("--- Data Load Complete ---")

    except FileNotFoundError as e:
        logging.error(f"FILE NOT FOUND: {e}. Ensure clean files exist in '{CLEAN_DATA_DIR}'.")
    except Exception as e:
        logging.error(f"Database loading failed. Error: {e}")
        raise


if __name__ == "__main__":
    load_data()
