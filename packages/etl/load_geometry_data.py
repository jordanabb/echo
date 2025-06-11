import json
from sqlalchemy import create_engine, text
from shapely.geometry import shape, MultiPolygon, Polygon
import os
from dotenv import load_dotenv
import logging

# --- CONFIGURATION ---
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')

# Load environment variables from the root .env file
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

# Define paths to GeoJSON files
DATA_SAMPLE_DIR = "data_sample/"
GEOJSON_FILES = [
    "county_geographies_sample.geojson",
    "tract_geographies_sample.geojson",
    "school_district_geographies_sample.geojson",
    "legislative_geographies_sample.geojson"
]

def load_geometry_data():
    """Loads geometry data from GeoJSON files and updates the geographies table."""
    logging.info("--- Starting Geometry Data Load ---")
    
    try:
        # First, let's add a geometry column to the existing geographies table
        logging.info("Adding geometry column to geographies table...")
        with engine.connect() as conn:
            # Add geometry column if it doesn't exist
            conn.execute(text("""
                ALTER TABLE geographies 
                ADD COLUMN IF NOT EXISTS geometry geometry(MULTIPOLYGON, 4326);
            """))
            conn.commit()
        
        # Load each GeoJSON file and update the corresponding records
        total_updated = 0
        
        for geojson_file in GEOJSON_FILES:
            file_path = os.path.join(DATA_SAMPLE_DIR, geojson_file)
            
            if not os.path.exists(file_path):
                logging.warning(f"File not found: {file_path}, skipping...")
                continue
                
            logging.info(f"Loading geometry data from {geojson_file}...")
            
            # Read the GeoJSON file
            with open(file_path, 'r') as f:
                geojson_data = json.load(f)
            
            # Update records in the database
            updated_count = 0
            with engine.connect() as conn:
                for feature in geojson_data['features']:
                    properties = feature['properties']
                    geometry = feature['geometry']
                    
                    # Convert geometry to shapely object
                    geom = shape(geometry)
                    
                    # Ensure geometry is in the correct format (MULTIPOLYGON)
                    if geom.geom_type == 'Polygon':
                        geom = MultiPolygon([geom])
                    elif geom.geom_type != 'MultiPolygon':
                        # For other geometry types, try to convert
                        geom = MultiPolygon([geom]) if hasattr(geom, 'geoms') else MultiPolygon([geom])
                    
                    # Convert geometry to WKT format for PostgreSQL
                    geom_wkt = geom.wkt
                    
                    # Update the geometry for matching records
                    result = conn.execute(text("""
                        UPDATE geographies 
                        SET geometry = ST_GeomFromText(:geom_wkt, 4326)
                        WHERE geo_id = :geo_id 
                        AND geo_level = :geo_level 
                        AND year = :year
                    """), {
                        'geom_wkt': geom_wkt,
                        'geo_id': str(properties['geo_id']),
                        'geo_level': properties['geo_level'],
                        'year': int(properties['year'])
                    })
                    
                    if result.rowcount > 0:
                        updated_count += 1
                
                conn.commit()
            
            logging.info(f"-> Updated {updated_count} records from {geojson_file}")
            total_updated += updated_count
        
        # Verify the results
        with engine.connect() as conn:
            result = conn.execute(text("""
                SELECT geo_level, COUNT(*) as total, 
                       COUNT(geometry) as with_geometry
                FROM geographies 
                GROUP BY geo_level
                ORDER BY geo_level;
            """))
            
            logging.info("Geometry data summary:")
            for row in result:
                logging.info(f"  {row.geo_level}: {row.with_geometry}/{row.total} records have geometry")
        
        logging.info(f"✅ Geometry data loading complete! Updated {total_updated} total records.")

    except Exception as e:
        logging.error(f"Geometry data loading failed. Error: {e}")
        raise

if __name__ == "__main__":
    load_geometry_data()
