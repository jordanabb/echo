"""
create_national.py - National-scale ETL for ECHO REVAMP data.

TWO-PHASE approach:
  Phase 1 (this script): Process shapefile PROPERTIES + CSVs → geographies.csv + results.csv
  Phase 2 (convert_shapefiles.py): Convert shapefiles → GeoJSON (slow, run separately)

This runs INDEPENDENTLY of the existing create_sample.py pipeline
so the current production data is never touched.
"""

import pandas as pd
import os
import logging
import fiona

# --- CONFIGURATION ---
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')

# Input directory
# Where the raw source files live. Defaults to "ECHO REVAMP" beside the repo
# root, but ECHO_RAW_DIR overrides it so the inputs can sit anywhere -- a
# Documents folder, a shared drive -- without copying them into the checkout.
REVAMP_DIR = os.environ.get('ECHO_RAW_DIR') or os.path.join(
    os.path.dirname(__file__), '..', '..', 'ECHO REVAMP')

# Output directory (separate from existing pipeline)
OUTPUT_DIR = "clean_output_national/"

# --- SHAPEFILE DEFINITIONS ---
SHAPEFILE_MAP = {
    'county': {
        'path': os.path.join(REVAMP_DIR, 'final_county_geos', 'final_county_geos.shp'),
        'geo_level_val': 'county',
        'id_col': 'GEOID',
        'name_col': 'NAME',
        'year_col': 'year',
    },
    'school_district': {
        'path': os.path.join(REVAMP_DIR, 'sd_geos', 'sd_geos.shp'),
        'geo_level_val': 'school_district',
        'id_col': 'GEOID',
        'name_col': 'Name',
        'year_col': 'Year',
    },
    'legislative': {
        'path': os.path.join(REVAMP_DIR, 'legdistgeos', 'leg_dist_geos_mar.shp'),
        'geo_level_val': None,  # Derived from 'house' column
        'id_col': 'GEOID',
        'name_col': 'Name',
        'year_col': 'Year',
        'house_col': 'house',
    },
    'tract': {
        'path': os.path.join(REVAMP_DIR, 'tract_geos', 'tract_geos.shp'),
        'geo_level_val': 'tract',
        'id_col': 'GEOID',
        'name_col': 'Name',
        'year_col': 'Year',
    },
    'congressional_district': {
        'path': os.path.join(REVAMP_DIR, 'all_cong_data', 'all_cong_data.shp'),
        'geo_level_val': 'congressional_district',
        'id_col': 'GEOID',
        'name_col': 'NAME',
        'year_col': 'year',
    },
}

# --- CSV DEFINITIONS ---
CSV_FILE_MAP = {
    # To add a new data source: just add another dict to the appropriate list.
    # - 'id_col': which column has the geographic ID
    # - 'type': used for rename mapping ('acs', 'ccd', 'f33', or 'passthrough')
    #   'passthrough' means column names already match database display names
    'county': [
        {'filename': 'counties_acs.csv', 'id_col': 'GEOID', 'type': 'acs'},
        {'filename': 'counties_ccd.csv', 'id_col': 'GEOID', 'type': 'ccd'},
        {'filename': 'f33_counties.csv', 'id_col': 'GEOID', 'type': 'f33'},
        {'filename': 'counties_places.csv', 'id_col': 'CountyFIPS', 'type': 'places'},
        {'filename': 'county_grad.csv', 'id_col': 'GEOID', 'type': 'edu'},
        {'filename': 'homeless_counties.csv', 'id_col': 'GEOID', 'type': 'edu'},
        {'filename': 'counties_enrolled_race.csv', 'id_col': 'GEOID', 'type': 'enrolled_race'},
    ],
    'tract': [
        {'filename': 'tracts_acs.csv', 'id_col': 'GEOID', 'type': 'acs'},
        {'filename': 'tracts_ccd.csv', 'id_col': 'GEOID', 'type': 'ccd'},
        {'filename': 'f33_tracts.csv', 'id_col': 'GEOID', 'type': 'f33'},
        {'filename': 'places_tracts.csv', 'id_col': 'GEOID', 'type': 'places'},
        {'filename': 'tracts_grad.csv', 'id_col': 'GEOID', 'type': 'edu'},
        {'filename': 'homeless_tracts.csv', 'id_col': 'GEOID', 'type': 'edu'},
        {'filename': 'tracts_enrolled_race.csv', 'id_col': 'GEOID', 'type': 'enrolled_race'},
    ],
    'school_district': [
        {'filename': 'school_districts_acs.csv', 'id_col': 'GEOID', 'type': 'acs'},
        {'filename': 'sd_ccd.csv', 'id_col': 'NCESID', 'type': 'ccd'},
        {'filename': 'f33_sd.csv', 'id_col': 'NCESID', 'type': 'f33'},
        {'filename': 'school_districts_places.csv', 'id_col': 'NCESID', 'type': 'places'},
        {'filename': 'sd_grad.csv', 'id_col': 'NCESID', 'type': 'edu'},
        {'filename': 'homeless_sd.csv', 'id_col': 'NCESID', 'type': 'edu'},
        {'filename': 'sd_enrolled_race.csv', 'id_col': 'NC ESID', 'type': 'enrolled_race'},
    ],
    'legislative': [
        {'filename': 'leg_dists_acs.csv', 'id_col': 'GEOID', 'type': 'acs'},
        {'filename': 'leg_dist_ccd.csv', 'id_col': 'GEOID', 'type': 'ccd'},
        {'filename': 'f33_leg_dist (1).csv', 'id_col': 'LEGID', 'type': 'f33'},
        {'filename': 'leg_dist_places.csv', 'id_col': 'LEGID', 'type': 'places'},
        {'filename': 'leg_dist_grad.csv', 'id_col': 'LEGID', 'type': 'edu'},
        {'filename': 'homeless_leg_dist.csv', 'id_col': 'LEGID', 'type': 'edu'},
        {'filename': 'leg_dist_enrolled_race.csv', 'id_col': 'LEGID', 'type': 'enrolled_race'},
    ],
    'congressional_district': [
        {'filename': 'cong_dist_acs.csv', 'id_col': 'GEOID', 'type': 'acs'},
        {'filename': 'cong_dist_ccd.csv', 'id_col': 'GEOID', 'type': 'ccd'},
        {'filename': 'f33_cong_dist.csv', 'id_col': 'GEOID', 'type': 'f33_raw'},
        {'filename': 'cong_dist_places.csv', 'id_col': 'CONGID', 'type': 'places'},
        {'filename': 'cong_dist_grad.csv', 'id_col': 'LEGID', 'type': 'edu'},
        {'filename': 'homeless_cong_dist.csv', 'id_col': 'LEGID', 'type': 'edu'},
        {'filename': 'cong_dist_enrolled_race.csv', 'id_col': 'GEOID', 'type': 'enrolled_race'},
    ],
}

# --- COLUMN RENAME MAPS ---
# These map raw CSV column names to the display names stored in the database.
# The display names MUST match the "name" field in indicator_config.py.

ACS_RENAME = {
    "mhhi": "Median Household Income ($)",
    "mhv": "Median Value, Owner-Occupied Homes ($)",
    "med_rent": "Median Monthly Residential Rent ($)",
    "perc_inc_rent": "Median Rent as % of Income",
    "population": "Total Population",
    "white": "White (% Population)",
    "black": "Black (% Population)",
    "native": "Native (% Population)",
    "asian": "Asian (% Population)",
    "pi": "Pacific Islander (% Population)",
    "other": "Other Race (% Population)",
    "twoormore": "Two or More Races (% Population)",
    "vacancy_rate": "Housing Unit Vacancy Rate (%)",
    "owner_occupied_perc": "Percent Homes, Owner-Occupied",
    "cell_perc": "Mobile Internet Only (% Having)",
    "broadband_perc": "Broadband Internet (% Having)",
    "other_internet": "Other Forms Internet Access (% Having)",
    "hs_edu": "High-School Diploma (% Adults 25+ Yrs)",
    "college": "College Degree Attained (% Adults 25+ Yrs)",
    "unemployment_rate": "Unemployment Rate (%)",
    "english_at_home": "English as Primary Language (% Households)",
}

CCD_RENAME = {
    "perc_ell": "English Language Learners (% Students)",
    "perc_idea": "Students with Disabilities (% Students)",
}

# F33 columns already use display names — list them for passthrough recognition.
# These names must match the "name" field in indicator_config.py exactly.
F33_PASSTHROUGH_COLS = [
    "Total Enrollment",
    "Total Revenue ($)",
    "Federal Revenue ($)",
    "State Revenue ($)",
    "Local Revenue ($)",
    "Local Property Tax Revenue ($)",
    "Local Property Tax Revenue Per Pupil ($)",
    "Federal Title I Allocation ($)",
    "Federal Title III Allocation ($)",
    "Federal Title VII Allocation ($)",
    "Federal IDEA Allocation ($)",
    "Total Revenue Per Pupil ($)",
    "Federal Revenue Per Pupil ($)",
    "State Revenue Per Pupil ($)",
    "Local Revenue Per Pupil ($)",
]

PLACES_RENAME = {
    "Current_lack_of_health_insurance_among_adults_aged_18-64_years": "Lacking Health Insurance (% Adults)",
    "Obesity_among_adults": "Obesity Rate (% Adults)",
    "Current_asthma_among_adults": "Asthma Rate (% Adults)",
    "Visits_to_doctor_for_routine_checkup_within_the_past_year_among_adults": "Doctor Checkup in Past 12 Months (% Adults)",
    "Received_food_stamps_in_the_past_12_months_among_adults": "SNAP Receipt in Past 12 Months (% Adults)",
    "Lack_of_reliable_transportation_in_the_past_12_months_among_adults": "Unreliable Transportation in Past 12 Months (% Adults)",
    "Food_insecurity_in_the_past_12_months_among_adults": "Food Insecurity in Past 12 Months (% Adults)",
    "Housing_insecurity_in_the_past_12_months_among_adults": "Housing Insecurity in Past 12 Months (% Adults)",
    "Utility_services_shut-off_threat_in_the_past_12_months_among_adults": "Utility Shut-Off Notice in Past 12 Months (% Adults)",
}

EDU_RENAME = {
    "graduation_rate": "High School Graduation Rate (%)",
    "perc_homeless": "Student Homelessness (% Students)",
}

ENROLLED_RACE_RENAME = {
    "White, including W. Hispanic (% Students)": "White (% Students)",
    "White (% Students)": "White (% Students)",
    "white_ps": "White (% Students)",
    "black_ps": "Black (% Students)",
    "hispanic_ps": "Latino (% Students)",
    "asian_ps": "Asian (% Students)",
    "indigenous_ps": "Native (% Students)",
    "pacific_islander_ps": "Pacific Islander (% Students)",
    "multiple_races_ps": "Two or More Races (% Students)",
    "non_white_ps": "Students of Color (%)",
}

F33_RAW_RENAME = {
    "enrollment": "Total Enrollment",
    "total_rev": "Total Revenue ($)",
    "fed_rev": "Federal Revenue ($)",
    "state_rev": "State Revenue ($)",
    "local_rev": "Local Revenue ($)",
    "prop_tax_rev": "Local Property Tax Revenue ($)",
    "prop_tax_rev_pp": "Local Property Tax Revenue Per Pupil ($)",
    "title1": "Federal Title I Allocation ($)",
    "title3": "Federal Title III Allocation ($)",
    "title7": "Federal Title VII Allocation ($)",
    "IDEA": "Federal IDEA Allocation ($)",
    "total_rev_pp": "Total Revenue Per Pupil ($)",
    "fed_rev_pp": "Federal Revenue Per Pupil ($)",
    "state_rev_pp": "State Revenue Per Pupil ($)",
    "local_rev_pp": "Local Revenue Per Pupil ($)",
}

ALL_RENAMES = {**ACS_RENAME, **CCD_RENAME, **PLACES_RENAME, **EDU_RENAME, **ENROLLED_RACE_RENAME, **F33_RAW_RENAME}

# Columns that already use their display name in the source CSVs
ENROLLED_RACE_PASSTHROUGH_COLS = [
    "Black (% Students)",
    "Latino (% Students)",
    "Asian (% Students)",
    "Native (% Students)",
    "Pacific Islander (% Students)",
    "Two or More Races (% Students)",
    "Students of Color (%)",
    "White (% Students)",
]

# All valid indicator display names (renamed + passthrough)
ALL_INDICATOR_NAMES = set(ALL_RENAMES.values()) | set(F33_PASSTHROUGH_COLS) | set(ENROLLED_RACE_PASSTHROUGH_COLS)

# --- GEOID FORMATTING ---
def format_geoid(geo_id, geo_level):
    """Format GEOID with proper zero-padding based on geography type."""
    geo_id_str = str(geo_id).strip()
    if '.' in geo_id_str:
        geo_id_str = geo_id_str.split('.')[0]

    if geo_level in ('county', 'sldu', 'sldl'):
        return geo_id_str.zfill(5)
    elif geo_level == 'school_district':
        return geo_id_str.zfill(7)
    elif geo_level == 'tract':
        return geo_id_str.zfill(11)
    elif geo_level == 'congressional_district':
        return geo_id_str.zfill(4)
    return geo_id_str


# =============================================================
# STEP 1: Extract geography PROPERTIES from shapefiles (no geometry)
# =============================================================
def extract_geographies():
    """Read shapefile properties only (fast - skips geometry processing)."""
    logging.info("=== Extracting Geography Properties from Shapefiles ===")

    all_geos = []

    for geo_type, config in SHAPEFILE_MAP.items():
        shp_path = config['path']
        if not os.path.exists(shp_path):
            logging.warning(f"Shapefile not found: {shp_path}, skipping.")
            continue

        logging.info(f"Reading {geo_type} properties from {shp_path}...")
        rows = []

        with fiona.open(shp_path) as src:
            total = len(src)
            for i, feat in enumerate(src):
                props = feat['properties']

                geo_id_raw = str(props[config['id_col']])
                name = props.get(config['name_col'], '')
                year = int(float(str(props[config['year_col']])))

                if config['geo_level_val'] is None:
                    house = str(props.get(config['house_col'], '')).lower()
                    geo_level = 'sldu' if house == 'upper' else 'sldl'
                else:
                    geo_level = config['geo_level_val']

                geo_id = format_geoid(geo_id_raw, geo_level)
                rows.append({
                    'geo_id': geo_id,
                    'geo_name': name,
                    'geo_level': geo_level,
                    'year': year,
                })

                if (i + 1) % 50000 == 0:
                    logging.info(f"  ...processed {i+1}/{total} features")

        df = pd.DataFrame(rows)
        all_geos.append(df)
        logging.info(f"  {geo_type}: {len(df)} geography rows")

    master_geos = pd.concat(all_geos, ignore_index=True)
    logging.info(f"Total geographies: {len(master_geos)}")
    return master_geos


# =============================================================
# STEP 2: Process CSVs → Long-format results
# =============================================================
def process_csvs(master_geos):
    """Read all ACS + CCD CSVs, merge, rename, and melt to long format."""
    logging.info("=== Processing CSV Data ===")

    all_results = []

    for geo_type, csv_list in CSV_FILE_MAP.items():
        logging.info(f"--- Processing CSVs for: {geo_type} ---")

        if geo_type == 'legislative':
            geo_levels = ['sldu', 'sldl']
        else:
            geo_levels = [geo_type]

        valid_geos = master_geos[master_geos['geo_level'].isin(geo_levels)]
        valid_geo_ids = set(valid_geos['geo_id'].astype(str))

        dfs_for_type = []

        for csv_info in csv_list:
            filepath = os.path.join(REVAMP_DIR, csv_info['filename'])
            if not os.path.exists(filepath):
                logging.warning(f"  CSV not found: {filepath}, skipping.")
                continue

            logging.info(f"  Reading {csv_info['filename']}...")
            df = pd.read_csv(filepath, low_memory=False)

            # Drop unnamed index columns
            df = df.loc[:, ~df.columns.str.contains('^Unnamed')]

            # Standardize ID column to 'geo_id'
            id_col = csv_info['id_col']
            if id_col in df.columns:
                df.rename(columns={id_col: 'geo_id'}, inplace=True)
            else:
                for col in df.columns:
                    if col.lower() == id_col.lower():
                        df.rename(columns={col: 'geo_id'}, inplace=True)
                        break

            # Standardize Year column
            for col in df.columns:
                if col.lower() == 'year':
                    df.rename(columns={col: 'year'}, inplace=True)
                    break

            if 'geo_id' not in df.columns or 'year' not in df.columns:
                logging.warning(f"  Missing geo_id or year column in {csv_info['filename']}, skipping.")
                continue

            # Format geo_ids
            if geo_type == 'legislative':
                df['geo_id'] = df['geo_id'].apply(lambda x: format_geoid(x, 'sldl'))
            else:
                df['geo_id'] = df['geo_id'].apply(lambda x: format_geoid(x, geo_type))

            # Filter to only geo_ids that exist in our shapefiles
            df = df[df['geo_id'].isin(valid_geo_ids)].copy()

            if df.empty:
                logging.warning(f"  No matching geo_ids found in {csv_info['filename']}.")
                continue

            # For legislative districts: derive geo_level from house column
            # GEOIDs overlap between upper/lower chambers, so geo_level is required
            if geo_type == 'legislative':
                # Find house column (case-insensitive)
                house_col = None
                for col in df.columns:
                    if col.lower() == 'house':
                        house_col = col
                        break

                if house_col:
                    # Derive geo_level from house column
                    df['geo_level'] = df[house_col].apply(
                        lambda h: 'sldu' if str(h).lower() == 'upper' else 'sldl'
                    )
                    df.drop(columns=[house_col], inplace=True)
                else:
                    # No house column (e.g., CCD) — join with geography table to get geo_level
                    # Each row gets duplicated for both sldl and sldu where the geo_id exists
                    df = pd.merge(
                        valid_geos[['geo_id', 'geo_level', 'year']],
                        df,
                        on=['geo_id', 'year'],
                        how='inner'
                    )

            # Drop non-indicator columns (metadata cols that shouldn't be melted)
            drop_cols = ['State', 'state', 'Name', 'name', 'SCHLEV', 'TotalPopulation', 'CountyFIPS']
            df.drop(columns=[c for c in drop_cols if c in df.columns], inplace=True, errors='ignore')

            dfs_for_type.append(df)
            logging.info(f"    {len(df)} rows after filtering")

        if not dfs_for_type:
            logging.warning(f"  No data for {geo_type}.")
            continue

        # Merge all CSVs for this geo_type
        from functools import reduce
        if geo_type == 'legislative':
            # Legislative districts: merge on (geo_id, geo_level, year) to avoid cross-joining
            merge_keys = ['geo_id', 'geo_level', 'year']
        else:
            merge_keys = ['geo_id', 'year']

        merged = reduce(
            lambda left, right: pd.merge(left, right, on=merge_keys, how='outer'),
            dfs_for_type
        )

        # Join with master_geos to get geo_level (for non-legislative types)
        if geo_type == 'legislative':
            # geo_level already present from above
            pass
        else:
            merged = pd.merge(
                valid_geos[['geo_id', 'geo_level', 'year']],
                merged,
                on=['geo_id', 'year'],
                how='inner'
            )

        # Rename columns to display names
        merged.rename(columns=ALL_RENAMES, inplace=True)

        # Melt to long format
        id_vars = ['geo_id', 'geo_level', 'year']
        value_vars = [col for col in merged.columns if col in ALL_INDICATOR_NAMES]

        if not value_vars:
            logging.warning(f"  No indicator columns found for {geo_type} after rename.")
            continue

        long_df = pd.melt(
            merged,
            id_vars=id_vars,
            value_vars=value_vars,
            var_name='indicator_id',
            value_name='value'
        )
        long_df.dropna(subset=['value'], inplace=True)

        # Convert "NA" strings to NaN and drop
        long_df = long_df[long_df['value'] != 'NA']

        all_results.append(long_df)
        logging.info(f"  {geo_type}: {len(long_df)} result rows after melt")

    if not all_results:
        logging.error("No results produced!")
        return None

    master_results = pd.concat(all_results, ignore_index=True)
    logging.info(f"Total result rows: {len(master_results)}")
    return master_results


# =============================================================
# MAIN
# =============================================================
if __name__ == "__main__":
    logging.info("===== ECHO National Data Processing =====")
    os.makedirs(OUTPUT_DIR, exist_ok=True)

    # Step 1: Extract geography properties from shapefiles (fast)
    master_geos = extract_geographies()
    if master_geos is None or master_geos.empty:
        logging.error("No geographies produced. Exiting.")
        exit(1)

    # Step 2: Process CSVs
    master_results = process_csvs(master_geos)
    if master_results is None or master_results.empty:
        logging.error("No results produced. Exiting.")
        exit(1)

    # Step 3: Save outputs
    geo_path = os.path.join(OUTPUT_DIR, "geographies.csv")
    master_geos.to_csv(geo_path, index=False)
    logging.info(f"Saved geographies to {geo_path}")

    results_path = os.path.join(OUTPUT_DIR, "results.csv")
    master_results.to_csv(results_path, index=False)
    logging.info(f"Saved results to {results_path}")

    # Summary
    logging.info("=== Summary ===")
    logging.info(f"Geographies: {len(master_geos)} rows")
    for level, count in master_geos['geo_level'].value_counts().items():
        logging.info(f"  {level}: {count}")
    logging.info(f"Results: {len(master_results)} rows")
    logging.info(f"Indicators: {master_results['indicator_id'].nunique()}")
    for ind, count in master_results['indicator_id'].value_counts().items():
        logging.info(f"  {ind}: {count}")
    logging.info(f"Years: {sorted(master_results['year'].unique())}")
    logging.info("===== Done! =====")
