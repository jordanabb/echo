"""
load_geometry_national.py - Load national GeoJSON geometry into the database.

Reads GeoJSON files from clean_output_national/geojson/ and updates
the geometry column in the geographies table.

Prerequisites:
  1. Run create_national.py first (produces geographies.csv + results.csv)
  2. Run load_data_to_db.py (with CLEAN_DATA_DIR pointed at clean_output_national/)
  3. Run convert_shapefiles.py (produces GeoJSON files)
  4. Then run this script to load geometry
"""

import json
from sqlalchemy import create_engine, text
from shapely.geometry import shape, MultiPolygon
import os
from dotenv import load_dotenv
import logging

from db_target import confirm_target

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

GEOJSON_DIR = "clean_output_national/geojson"

# All expected GeoJSON files
GEOJSON_FILES = [
    "county_geographies.geojson",
    "school_district_geographies.geojson",
    "sldl_geographies.geojson",
    "sldu_geographies.geojson",
    "tract_geographies.geojson",
]


def load_geometry_data():
    """Load geometry from GeoJSON files into the geographies table."""
    logging.info("--- Starting National Geometry Data Load ---")

    try:
        # Add geometry column if it doesn't exist
        with engine.connect() as conn:
            conn.execute(text("""
                ALTER TABLE geographies
                ADD COLUMN IF NOT EXISTS geometry geometry(MULTIPOLYGON, 4326);
            """))
            conn.commit()

        total_updated = 0

        for geojson_file in GEOJSON_FILES:
            file_path = os.path.join(GEOJSON_DIR, geojson_file)
            if not os.path.exists(file_path):
                logging.warning(f"Not found: {file_path}, skipping.")
                continue

            logging.info(f"Loading {geojson_file}...")

            with open(file_path, 'r') as f:
                geojson_data = json.load(f)

            features = geojson_data['features']
            logging.info(f"  {len(features)} features to load")

            # Process in batches for better performance
            batch_size = 1000
            updated_count = 0

            with engine.connect() as conn:
                for i in range(0, len(features), batch_size):
                    batch = features[i:i + batch_size]

                    for feature in batch:
                        props = feature['properties']
                        geom = shape(feature['geometry'])

                        if geom.geom_type == 'Polygon':
                            geom = MultiPolygon([geom])

                        result = conn.execute(text("""
                            UPDATE geographies
                            SET geometry = ST_GeomFromText(:geom_wkt, 4326)
                            WHERE geo_id = :geo_id
                            AND geo_level = :geo_level
                            AND year = :year
                        """), {
                            'geom_wkt': geom.wkt,
                            'geo_id': str(props['geo_id']),
                            'geo_level': props['geo_level'],
                            'year': int(props['year'])
                        })

                        if result.rowcount > 0:
                            updated_count += 1

                    conn.commit()

                    if (i + batch_size) % 10000 == 0 or i + batch_size >= len(features):
                        logging.info(f"  ...{min(i + batch_size, len(features))}/{len(features)} processed, {updated_count} updated")

            logging.info(f"  Updated {updated_count} records from {geojson_file}")
            total_updated += updated_count

        # Verify
        with engine.connect() as conn:
            result = conn.execute(text("""
                SELECT geo_level, COUNT(*) as total,
                       COUNT(geometry) as with_geometry
                FROM geographies
                GROUP BY geo_level
                ORDER BY geo_level;
            """))

            logging.info("Geometry summary:")
            for row in result:
                logging.info(f"  {row.geo_level}: {row.with_geometry}/{row.total} have geometry")

        logging.info(f"Total updated: {total_updated}")

    except Exception as e:
        logging.error(f"Failed: {e}")
        raise


if __name__ == "__main__":
    confirm_target("load geometry into")
    load_geometry_data()
