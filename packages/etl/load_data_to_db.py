import pandas as pd
import geopandas as gpd
from sqlalchemy import create_engine, text
import os
from dotenv import load_dotenv
import logging

# --- 1. CONFIGURATION ---
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')

# Load environment variables from the root .env file
# This ensures the script can find your DB credentials
dotenv_path = os.path.join(os.path.dirname(__file__), '..', '..', '.env')
load_dotenv(dotenv_path=dotenv_path)

# Get database connection details from environment variables
DB_USER = os.getenv("DB_USER")
DB_PASSWORD = os.getenv("DB_PASSWORD")
DB_HOST = os.getenv("DB_HOST")
DB_PORT = os.getenv("DB_PORT")
DB_NAME = os.getenv("DB_NAME")

DATABASE_URL = f"postgresql://{DB_USER}:{DB_PASSWORD}@{DB_HOST}:{DB_PORT}/{DB_NAME}"
engine = create_engine(DATABASE_URL)

# Define paths to your CLEAN, PROCESSED output files
CLEAN_DATA_DIR = "clean_output/"
GEOGRAPHIES_FILE = os.path.join(CLEAN_DATA_DIR, "geographies.csv") # The info file
RESULTS_FILE = os.path.join(CLEAN_DATA_DIR, "results.csv")

def load_data():
    """Loads the clean, processed files into the database."""
    logging.info("--- Starting Final Data Load to Database ---")
    
    try:
        # --- Load Geographies ---
        # NOTE: We read the CSV file since no GeoJSON file is available.
        # This will create a table without geometry data.
        logging.info(f"Reading geography data from '{GEOGRAPHIES_FILE}'...")
        geographies_df = pd.read_csv(GEOGRAPHIES_FILE)
        
        # This is a small but important check. The geo_level column might be read
        # as a generic 'object'. We need to ensure it's treated as text for the ENUM type.
        if 'geo_level' in geographies_df.columns:
            geographies_df['geo_level'] = geographies_df['geo_level'].astype(str)

        # Drop dependent tables first to avoid foreign key constraint issues
        logging.info("Dropping existing tables if they exist...")
        with engine.connect() as conn:
            conn.execute(text("DROP TABLE IF EXISTS results_data CASCADE"))
            conn.execute(text("DROP TABLE IF EXISTS geographies CASCADE"))
            conn.commit()
        
        logging.info(f"Loading {len(geographies_df)} geographies to 'geographies' table...")
        # Use to_sql to load the data. Since we dropped the table, we can use 'replace'
        geographies_df.to_sql(
            'geographies',
            engine,
            if_exists='replace',
            index=False
        )
        logging.info("-> Geographies table loaded successfully.")
        
        # --- Load Results Data ---
        logging.info(f"Reading results data from '{RESULTS_FILE}'...")
        results_df = pd.read_csv(RESULTS_FILE)
        
        # Same check for the geo_level column here before loading
        if 'geo_level' in results_df.columns:
            results_df['geo_level'] = results_df['geo_level'].astype(str)

        logging.info(f"Loading {len(results_df)} data points to 'results_data' table...")
        results_df.to_sql(
            'results_data',
            engine,
            if_exists='replace',
            index=False,
            chunksize=20000 # Breaks the load into smaller chunks to save memory
        )
        logging.info("-> Results_data table loaded successfully.")
        
        logging.info("✅✅✅ DATABASE IS POPULATED AND READY! ✅✅✅")

    except FileNotFoundError as e:
        logging.error(f"FILE NOT FOUND: {e}. Please ensure you have run 'process_data.py' and that the clean files exist in 'packages/etl/clean_output/'.")
    except Exception as e:
        logging.error(f"Database loading failed. Error: {e}")

if __name__ == "__main__":
    load_data()
