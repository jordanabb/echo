"""
load_geometry_national_fast.py - Fast batch geometry loader.

Instead of individual UPDATE per feature, this:
1. Creates a temp table with (geo_id, geo_level, year, geom_wkt)
2. Bulk inserts all features via executemany
3. Runs a single UPDATE ... FROM join to set geometry

Much faster than row-by-row updates.
"""

import json
import os
import logging
from shapely.geometry import shape, MultiPolygon
from sqlalchemy import create_engine, text
from dotenv import load_dotenv

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

GEOJSON_FILES = [
    "county_geographies.geojson",
    "school_district_geographies.geojson",
    "sldl_geographies.geojson",
    "sldu_geographies.geojson",
    "tract_geographies.geojson",
]


def load_geometry_data():
    logging.info("--- Starting Fast National Geometry Data Load ---")

    with engine.connect() as conn:
        # Add geometry column if missing
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
        logging.info(f"  {len(features)} features to process")

        # Prepare all WKT data
        rows = []
        for feat in features:
            props = feat['properties']
            geom = shape(feat['geometry'])
            if geom.geom_type == 'Polygon':
                geom = MultiPolygon([geom])
            rows.append({
                'geo_id': str(props['geo_id']),
                'geo_level': props['geo_level'],
                'year': int(props['year']),
                'geom_wkt': geom.wkt,
            })

        logging.info(f"  Prepared {len(rows)} WKT geometries, inserting in batches...")

        with engine.connect() as conn:
            # Create temp table
            conn.execute(text("""
                CREATE TEMP TABLE IF NOT EXISTS geom_staging (
                    geo_id VARCHAR(20),
                    geo_level VARCHAR(50),
                    year INTEGER,
                    geom_wkt TEXT
                );
            """))
            conn.execute(text("TRUNCATE geom_staging;"))

            # Batch insert into temp table
            batch_size = 5000
            for i in range(0, len(rows), batch_size):
                batch = rows[i:i + batch_size]
                conn.execute(
                    text("INSERT INTO geom_staging (geo_id, geo_level, year, geom_wkt) VALUES (:geo_id, :geo_level, :year, :geom_wkt)"),
                    batch
                )
                if (i + batch_size) % 50000 == 0 or i + batch_size >= len(rows):
                    logging.info(f"  ...staged {min(i + batch_size, len(rows))}/{len(rows)}")

            conn.commit()
            logging.info(f"  Staging complete. Running bulk UPDATE...")

            # Single bulk UPDATE join
            result = conn.execute(text("""
                UPDATE geographies g
                SET geometry = ST_GeomFromText(s.geom_wkt, 4326)
                FROM geom_staging s
                WHERE g.geo_id = s.geo_id
                  AND g.geo_level = s.geo_level
                  AND g.year = s.year;
            """))

            updated = result.rowcount
            conn.commit()

            logging.info(f"  Updated {updated} records from {geojson_file}")
            total_updated += updated

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
    logging.info("--- Done! ---")


if __name__ == "__main__":
    load_geometry_data()
