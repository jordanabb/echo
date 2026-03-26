"""
convert_shapefiles.py - Convert ECHO REVAMP shapefiles to GeoJSON.

This is the SLOW step (processes geometry for 800k+ features).
Run this separately from create_national.py.

Output: clean_output_national/geojson/<geo_level>_geographies.geojson
"""

import json
import os
import logging
import fiona
from shapely.geometry import shape, mapping, MultiPolygon

logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')

REVAMP_DIR = os.path.join(os.path.dirname(__file__), '..', '..', 'ECHO REVAMP')
OUTPUT_DIR = "clean_output_national/geojson"


def format_geoid(geo_id, geo_level):
    geo_id_str = str(geo_id).strip()
    if '.' in geo_id_str:
        geo_id_str = geo_id_str.split('.')[0]
    if geo_level in ('county', 'sldu', 'sldl'):
        return geo_id_str.zfill(5)
    elif geo_level == 'school_district':
        return geo_id_str.zfill(7)
    elif geo_level == 'tract':
        return geo_id_str.zfill(11)
    return geo_id_str


SHAPEFILE_MAP = {
    'county': {
        'path': os.path.join(REVAMP_DIR, 'final_county_geos', 'final_county_geos.shp'),
        'geo_level_val': 'county',
        'id_col': 'GEOID', 'name_col': 'NAME', 'year_col': 'year',
    },
    'school_district': {
        'path': os.path.join(REVAMP_DIR, 'sd_geos', 'sd_geos.shp'),
        'geo_level_val': 'school_district',
        'id_col': 'GEOID', 'name_col': 'Name', 'year_col': 'Year',
    },
    'legislative': {
        'path': os.path.join(REVAMP_DIR, 'legdistgeos', 'leg_dist_geos_mar.shp'),
        'geo_level_val': None,
        'id_col': 'GEOID', 'name_col': 'Name', 'year_col': 'Year',
        'house_col': 'house',
    },
    'tract': {
        'path': os.path.join(REVAMP_DIR, 'tract_geos', 'tract_geos.shp'),
        'geo_level_val': 'tract',
        'id_col': 'GEOID', 'name_col': 'Name', 'year_col': 'Year',
    },
}


def convert_shapefile(geo_type, config):
    """Convert a single shapefile to per-level GeoJSON files."""
    shp_path = config['path']
    if not os.path.exists(shp_path):
        logging.warning(f"Not found: {shp_path}")
        return

    logging.info(f"Converting {geo_type}: {shp_path}")
    features_by_level = {}

    with fiona.open(shp_path) as src:
        total = len(src)
        for i, feat in enumerate(src):
            props = feat['properties']
            geom = shape(feat['geometry'])

            if geom.geom_type == 'Polygon':
                geom = MultiPolygon([geom])

            # Simplify geometry for choropleth performance (~80-90% vertex reduction)
            geom = geom.simplify(0.001, preserve_topology=True)

            geo_id_raw = str(props[config['id_col']])
            name = props.get(config['name_col'], '')
            year = int(float(str(props[config['year_col']])))

            if config['geo_level_val'] is None:
                house = str(props.get(config['house_col'], '')).lower()
                geo_level = 'sldu' if house == 'upper' else 'sldl'
            else:
                geo_level = config['geo_level_val']

            geo_id = format_geoid(geo_id_raw, geo_level)

            feature = {
                'type': 'Feature',
                'properties': {
                    'geo_id': geo_id,
                    'geo_name': name,
                    'geo_level': geo_level,
                    'year': year,
                },
                'geometry': mapping(geom),
            }
            features_by_level.setdefault(geo_level, []).append(feature)

            if (i + 1) % 10000 == 0:
                logging.info(f"  {i+1}/{total} features processed")

    for level, features in features_by_level.items():
        out_path = os.path.join(OUTPUT_DIR, f"{level}_geographies.geojson")
        with open(out_path, 'w') as f:
            json.dump({'type': 'FeatureCollection', 'features': features}, f)
        logging.info(f"  Wrote {len(features)} {level} features to {out_path}")


if __name__ == "__main__":
    import sys

    os.makedirs(OUTPUT_DIR, exist_ok=True)

    # Allow converting a single type: python convert_shapefiles.py county
    if len(sys.argv) > 1:
        target = sys.argv[1]
        if target in SHAPEFILE_MAP:
            convert_shapefile(target, SHAPEFILE_MAP[target])
        else:
            print(f"Unknown type: {target}. Options: {list(SHAPEFILE_MAP.keys())}")
    else:
        for geo_type, config in SHAPEFILE_MAP.items():
            convert_shapefile(geo_type, config)

    logging.info("All conversions complete!")
