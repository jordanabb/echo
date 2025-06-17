import pandas as pd
import json
import os
import logging
from functools import reduce



# --- END OF MASTER CONFIGURATION ---


# --- 2. SCRIPT SETUP ---
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
SAMPLE_GEO_DIR = "data_sample/"
NATIONAL_DATA_SOURCE_DIR = "/Users/jordanabbott/Downloads/"
OUTPUT_DIR = "clean_output/"


# --- 3. DATA DEFINITIONS - Define all possible files here ---

# Map target level to its geography file and how to process it.
# The 'id_col_options' list lets the script search for multiple possible ID column names.
GEOGRAPHY_FILE_MAP = {
    'county': {
        'filename': 'county_geographies_sample.geojson', 
        'geo_level_val': 'county',
        'id_col_options': ['GEOID', 'geoid']
    },
    'school_district': {
        'filename': 'school_district_geographies_sample.geojson',
        'geo_level_val': 'school_district',
        'id_col_options': ['GEOID', 'geoid', 'NCESID', 'ncesid']
    },
    'legislative': {
        'filename': 'legislative_geographies_sample.geojson',
        'id_col_options': ['GEOID', 'geoid', 'LEGID', 'legid', 'Legid']
        # 'geo_level_val' is not needed here because it's derived from the 'house' column
    },
    'tract': {
        'filename': 'tract_geographies_sample.geojson', 
        'geo_level_val': 'tract',
        'id_col_options': ['GEOID', 'geoid']
    }

}

# Map target level to the list of national CSVs to process.
# We now also specify the possible ID column names for each CSV file.
CSV_FILE_MAP = {
    'county': [
        {'filename': 'counties/counties_acs.csv', 'id_col_options': ['GEOID', 'geoid']},
        {'filename': 'counties/new_county_aqi.csv', 'id_col_options': ['GEOID', 'geoid']},
        {'filename': 'counties/counties_enrolled_race.csv', 'id_col_options': ['GEOID', 'geoid']},
        {'filename': 'counties/f33_counties.csv', 'id_col_options': ['GEOID', 'geoid']},
        {'filename': 'counties/counties_ccd.csv', 'id_col_options': ['GEOID', 'geoid']},
        {'filename': 'counties/counties_places.csv', 'id_col_options': ['GEOID', 'geoid']},
        {'filename': 'counties/county_grad.csv', 'id_col_options': ['GEOID', 'geoid']},
        {'filename': 'counties/homeless_counties.csv', 'id_col_options': ['GEOID', 'geoid']},
    ],
    'tract': [
        {'filename': 'tracts/tracts_acs.csv', 'id_col_options': ['GEOID', 'geoid']},
        {'filename': 'tracts/new_county_aqi.csv', 'id_col_options': ['GEOID', 'geoid']},
        {'filename': 'tracts/tracts_enrolled_race.csv', 'id_col_options': ['GEOID', 'geoid']},
        {'filename': 'tracts/f33_tracts.csv', 'id_col_options': ['GEOID', 'geoid']},
        {'filename': 'tracts/tracts_ccd.csv', 'id_col_options': ['GEOID', 'geoid']},
        {'filename': 'tracts/places_tracts.csv', 'id_col_options': ['GEOID', 'geoid']},
        {'filename': 'tracts/tracts_grad.csv', 'id_col_options': ['GEOID', 'geoid']},
        {'filename': 'tracts/homeless_tracts.csv', 'id_col_options': ['GEOID', 'geoid']},
    ],
    'school_district': [
        {'filename': 'school_districts/school_districts_acs.csv', 'id_col_options': ['NCESID', 'ncesid', 'GEOID', 'geoid']},
        {'filename': 'school_districts/saipe_sd.csv', 'id_col_options': ['NCESID', 'ncesid', 'GEOID', 'geoid']},
        {'filename': 'school_districts/f33_sd.csv', 'id_col_options': ['NCESID', 'ncesid', 'GEOID', 'geoid']},
        {'filename': 'school_districts/sd_enrolled_race.csv', 'id_col_options': ['NCESID', 'ncesid', 'GEOID', 'geoid']},
        {'filename': 'school_districts/sd_aqi.csv', 'id_col_options': ['NCESID', 'ncesid', 'GEOID', 'geoid']},
        {'filename': 'school_districts/school_districts_places.csv', 'id_col_options': ['NCESID', 'ncesid', 'GEOID', 'geoid']},
        {'filename': 'school_districts/sd_grad.csv', 'id_col_options': ['NCESID', 'ncesid', 'GEOID', 'geoid']},
        {'filename': 'school_districts/homeless_sd.csv', 'id_col_options': ['NCESID', 'ncesid', 'GEOID', 'geoid']},

        # ... add all other school district CSVs here ...
    ],
    'legislative': [
        {'filename': 'legislative_districts/leg_districts_acs.csv', 'id_col_options': ['GEOID', 'geoid', 'LEGID', 'legid', 'Legid']},
        {'filename': 'legislative_districts/f33_leg_dist.csv', 'id_col_options': ['GEOID', 'geoid', 'LEGID', 'legid', 'Legid']},
        {'filename': 'legislative_districts/leg_dist_enrolled_race.csv', 'id_col_options': ['GEOID', 'geoid', 'LEGID', 'legid', 'Legid']},
        {'filename': 'legislative_districts/leg_dist_ccd.csv', 'id_col_options': ['GEOID', 'geoid', 'LEGID', 'legid', 'Legid']},
        {'filename': 'legislative_districts/leg_dist_places.csv', 'id_col_options': ['GEOID', 'geoid', 'LEGID', 'legid', 'Legid']},
        {'filename': 'legislative_districts/homeless_leg_dist.csv', 'id_col_options': ['GEOID', 'geoid', 'LEGID', 'legid', 'Legid']},

    ]
    
}

# --- (The renaming dictionaries remain the same as before) ---
# ... [paste the full renaming dictionaries here] ...
acs_rename_dict = { "mhhi": "Median Household Income ($)", "mhv": "Median Value, Owner-Occupied Homes ($)", "med_rent": "Median Monthly Residential Rent ($)", "perc_inc_rent": "Median Rent as % of Income", "population": "Total Population", "white": "White, including W. Hispanic (%)", "black": "Black (% Population)", "native": "Native (% Population)", "asian": "Asian (% Population)", "pi": "Pacific Islander (% Population)", "other": "Other Race (% Population)", "twoormore": "Two or More Races (% Population)", "vacancy_rate": "Housing Unit Vacancy Rate (%)", "owner_occupied_perc": "Percent Homes, Owner-Occupied", "cell_perc": "Mobile Internet Only (% Having)", "broadband_perc": "Broadband Internet (% Having)", "other_internet": "Other Forms Internet Access (% Having)", "hs_edu": "High-School Diploma (% Adults ≥25 Yrs)", "college": "College Degree Atttained (% Adults ≥25 Yrs)", "unemployment_rate": "Unemployment Rate (%)", "english_at_home": "English as Primary Language (% Households)" }
school_finance_rename_dict = { "enrollment": "Total Enrollment", "total_rev_pp": "Total Revenue Per Pupil ($)", "fed_rev_pp": "Federal Revenue Per Pupil ($)", "state_rev_pp": "State Revenue Per Pupil ($)", "local_rev_pp": "Local Revenue Per Pupil ($)", "prop_tax_rev_pp": "Local Property Tax Revenue Per Pupil ($)", "total_rev": "Total Revenue ($)", "fed_rev": "Federal Revenue ($)", "state_rev": "State Revenue ($)", "local_rev": "Local Revenue ($)", "prop_tax_rev": "Local Property Tax Revenue ($)", "title1": "Federal Title I Allocation ($)", "title3": "Federal Title III Allocation ($)", "title7": "Federal Title VII Allocation ($)", "IDEA": "Federal IDEA Allocation ($)" }
cdc_places_rename_dict = { "Current_lack_of_health_insurance_among_adults_aged_18-64_years": "Lacking Health Insurance (% Adults)", "Obesity_among_adults": "Obesity Rate (% Adults)", "Current_ asthma_among_adults": "Asthma Rate (% Adults)", "Visits_to_doctor_for_routine_checkup_within_the_past_year_among_adults": "Doctor Checkup in Past 12 Months (% Adults)", "Received_food_stamps_in_the_past_12_months_among_adults": "SNAP Receipt in Past 12 Months (% Adults)", "Lack_of_reliable_transportation_in_the_past_12_months_among_adults": "Unreliable Transportation in Past 12 Months (% Adults)", "Food_insecurity_in_the_past_12_months_among_adults": "Food Insecurity in Past 12 Months (% Adults)", "Housing_insecurity_in_the_past_12_months_among_adults": "Housing Insecurity in Past 12 Months (% Adults)", "Utility_services_shut-off_threat_in_the_past_12_months_among_adults": "Utility Shut-Off Notice in Past 12 Months (% Adults)" }
school_profile_rename_dict = { "white_ps": "White (% Students)", "black_ps": "Black (% Students)", "asian_ps": "Asian (% Students)", "hispanic_ps": "Latino (% Students)", "indigenous_ps": "Native (% Students)", "pacific_islander_ps": "Pacific Islander (% Students)", "other_ps": "Other Race (% Students)", "multiple_races_ps": "Two or More Races (% Students)", "non_white_ps": "Students of Color (%)" }
ALL_RENAMES = { **acs_rename_dict, **school_finance_rename_dict, **cdc_places_rename_dict, **school_profile_rename_dict }



def find_and_rename_column(df, options, target_name):
    """A helper to find and rename columns from a list of possibilities."""
    # Create a lowercased copy of columns for case-insensitive matching
    df_cols_lower = {col.lower(): col for col in df.columns}
    for option in options:
        if option.lower() in df_cols_lower:
            original_col_name = df_cols_lower[option.lower()]
            df.rename(columns={original_col_name: target_name}, inplace=True)
            return True
    return False

def format_geoid_by_type(geo_id, geo_level):
    """Format GEOID with proper zero-padding based on geography type."""
    geo_id_str = str(geo_id).strip()
    
    # Remove any decimal points if the ID was read as a float
    if '.' in geo_id_str:
        geo_id_str = geo_id_str.split('.')[0]
    
    if geo_level in ['county', 'sldu', 'sldl']:
        # Counties and legislative districts should be 5 digits
        return geo_id_str.zfill(5)
    elif geo_level == 'school_district':
        # School districts should be 7 digits
        return geo_id_str.zfill(7)
    elif geo_level == 'tract':
        # Census tracts should be 11 digits
        return geo_id_str.zfill(11)
    else:
        # Default: return as string without modification
        return geo_id_str

# --- Processing Functions ---
def process_all_geographies():
    """Reads all geography files, standardizes them, and combines them."""
    logging.info("--- Reading and Standardizing All Sample Geographies ---")
    
    all_geos_list = []
    for geo_type, config in GEOGRAPHY_FILE_MAP.items():
        filepath = os.path.join(SAMPLE_GEO_DIR, config['filename'])
        try:
            # Read GeoJSON file as regular JSON
            with open(filepath, 'r') as f:
                geojson_data = json.load(f)
            
            # Extract properties from features
            features_data = []
            for feature in geojson_data['features']:
                properties = feature['properties']
                features_data.append(properties)
            
            # Convert to DataFrame
            df = pd.DataFrame(features_data)
            
            # Check if columns are already properly named, if not try to rename them
            if 'geo_id' not in df.columns:
                if not find_and_rename_column(df, config['id_col_options'], 'geo_id'):
                    raise ValueError(f"No valid ID column found in {config['filename']}")
            
            if 'geo_name' not in df.columns:
                find_and_rename_column(df, ['NAME', 'name'], 'geo_name')
            
            if 'year' not in df.columns:
                find_and_rename_column(df, ['YEAR', 'year', 'Year'], 'year')

            if 'geo_level' not in df.columns:
                if 'house' in df.columns:
                    df['geo_level'] = df['house'].apply(lambda h: 'sldu' if str(h).lower() == 'upper' else 'sldl')
                else:
                    df['geo_level'] = geo_type
            
            # Apply GEOID formatting based on geography type
            df['geo_id'] = df.apply(lambda row: format_geoid_by_type(row['geo_id'], row['geo_level']), axis=1)
            
            all_geos_list.append(df)
        except Exception as e:
            logging.error(f"Failed to process geography file {filepath}. Error: {e}")
            continue

    if not all_geos_list:
        logging.error("No geography files could be processed. Exiting.")
        return None
        
    master_geographies_df = pd.concat(all_geos_list, ignore_index=True)
    
    # Select and reorder final columns, dropping extras like 'house'
    final_geo_cols = ['geo_id', 'geo_name', 'geo_level', 'year']
    # Add year column if it doesn't exist
    if 'year' not in master_geographies_df.columns:
        master_geographies_df['year'] = 2021  # Default year
    
    master_geographies_df = master_geographies_df[final_geo_cols]

    logging.info(f"Successfully combined {len(master_geographies_df)} total geographies.")
    return master_geographies_df

def process_and_merge_all_indicators(master_geographies_gdf):
    """Filters all national CSVs using the master geography list, then merges them."""
    logging.info("--- Filtering and Merging All National CSVs ---")
    
    # Create a unique identifier for joining that includes geo_level for legislative districts
    master_geographies_gdf['join_key'] = master_geographies_gdf['geo_id'].astype(str) + "_" + master_geographies_gdf['geo_level']
    valid_join_keys = set(master_geographies_gdf['join_key'])

    # We process CSVs grouped by the geography type they belong to
    all_merged_dataframes = []

    for geo_type, csv_config_list in CSV_FILE_MAP.items():
        logging.info(f"--- Processing CSVs for geo_type: '{geo_type}' ---")
        
        # Get the GEOIDs for the current geo_type we're processing
        # Use exact matching to avoid 'tract' matching 'school_district'
        if geo_type == 'legislative':
            # For legislative, match both 'sldu' and 'sldl'
            current_geos = master_geographies_gdf[master_geographies_gdf['geo_level'].isin(['sldu', 'sldl'])]
        else:
            # For all other types, use exact matching
            current_geos = master_geographies_gdf[master_geographies_gdf['geo_level'] == geo_type]
        valid_geo_ids_for_type = set(current_geos['geo_id'].astype(str))

        if valid_geo_ids_for_type:
            list_of_dfs_for_type = []
            for file_info in csv_config_list:
                filepath = os.path.join(NATIONAL_DATA_SOURCE_DIR, file_info['filename'])
                try:
                    df = pd.read_csv(filepath, low_memory=False)
                    # Drop any unnamed index columns that might cause merge conflicts
                    df = df.loc[:, ~df.columns.str.contains('^Unnamed')]
                    
                    if find_and_rename_column(df, file_info['id_col_options'], 'geo_id') and find_and_rename_column(df, ['year', 'YEAR', 'Year'], 'year'):
                        # Apply GEOID formatting based on geography type
                        df['geo_id'] = df['geo_id'].apply(lambda x: format_geoid_by_type(x, geo_type))
                        df_filtered = df[df['geo_id'].isin(valid_geo_ids_for_type)].copy()
                        if not df_filtered.empty:
                            list_of_dfs_for_type.append(df_filtered)
                except Exception as e:
                    logging.warning(f"Could not process {file_info['filename']}. Error: {e}")

            if list_of_dfs_for_type:
                # Merge all CSVs for this specific geo_type
                merged_for_type = reduce(lambda left, right: pd.merge(left, right, on=['geo_id', 'year'], how='outer'), list_of_dfs_for_type)
                all_merged_dataframes.append(merged_for_type)

    if not all_merged_dataframes:
        logging.error("No indicator data could be processed.")
        return None

    # Concatenate the merged dataframes from all geo_types
    master_wide_df = pd.concat(all_merged_dataframes, ignore_index=True)
    logging.info(f"Successfully created master wide dataframe with {len(master_wide_df)} rows before final join.")
    
    # Final join with master geographies to ensure geo_level is present for melting
    final_wide_df = pd.merge(master_geographies_gdf[['geo_id', 'geo_level', 'year']], master_wide_df, on=['geo_id', 'year'], how='left')
    return final_wide_df

def clean_and_transform_to_long(wide_df):
    """Takes the final wide dataframe and melts it to the required long format."""
    logging.info("--- Cleaning and Transforming Data to Long Format ---")
    wide_df.rename(columns=ALL_RENAMES, inplace=True)
    
    id_vars = ['geo_id', 'geo_level', 'year']
    value_vars = [col for col in wide_df.columns if col in ALL_RENAMES.values()]
    
    long_df = pd.melt(wide_df, id_vars=id_vars, value_vars=value_vars, var_name='indicator_id', value_name='value')
    long_df.dropna(subset=['value'], inplace=True)
    
    logging.info(f"Melted data into {len(long_df)} rows.")
    return long_df

# --- Main execution block ---
if __name__ == "__main__":
    logging.info("===== Starting Data Processing and File Generation =====")
    
    # Ensure the output directory exists
    os.makedirs(OUTPUT_DIR, exist_ok=True)
    
    # 1. Process all geography files together
    master_geos = process_all_geographies()
    
    if master_geos is not None:
        # 2. Process all indicator files together
        wide_indicators = process_and_merge_all_indicators(master_geos)
        
        if wide_indicators is not None:
            # 3. Transform the merged indicator data into long format
            final_long_results = clean_and_transform_to_long(wide_indicators)

            # 4. Save the final, clean files
            
            # For the geographies, save the info
            geographies_output_path = os.path.join(OUTPUT_DIR, "geographies.csv")
            master_geos.to_csv(geographies_output_path, index=False)
            logging.info(f"✅ Successfully saved clean geographies info to '{geographies_output_path}'")

            # For the results data
            results_output_path = os.path.join(OUTPUT_DIR, "results.csv")
            final_long_results.to_csv(results_output_path, index=False)
            logging.info(f"✅ Successfully saved clean results data to '{results_output_path}'")
            
            logging.info("🎉 All processing complete!")
