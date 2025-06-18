# apps/backend/indicator_config.py

# This file acts as the central, machine-readable version of the
# project's Data & Methodology Codebook.

# --- CHOROPLETH & LEGEND SETTINGS ---
# 5-class Blue-Purple palette from https://colorbrewer2.org (colorblind-safe)
CHOROPLETH_PALETTE = ["#f2f0f7", "#cbc9e2", "#9e9ac8", "#756bb1", "#54278f"]
NO_DATA_COLOR = "#e0e0e0"  # A neutral gray

# --- GEOGRAPHY HIERARCHY ---
GEOGRAPHY_HIERARCHY = {
    "nation": {"name": "Nation", "sublevels": ["state"]},
    "state": {"name": "State", "sublevels": ["county", "sldl", "sldu"]}, # sldl/u = state leg. district lower/upper
    "county": {"name": "County", "sublevels": ["tract"]},
    "tract": {"name": "Census Tract", "sublevels": []},
    "school_district": {"name": "School District", "sublevels": []},
    "sldl": {"name": "State House District", "sublevels": []},
    "sldu": {"name": "State Senate District", "sublevels": []},
}

# --- INDICATOR METADATA ---
# These keys and names must match the actual indicator_id values in the database
INDICATOR_METADATA = {
    # --- Demographics ---
    "total_population": {
        "name": "Total Population",
        "theme": "Demographics",
        "description": "Total population in the geographic area.",
        "available_years": [2021, 2022]
    },
    "asian_students": {
        "name": "Asian (% Students)",
        "theme": "Demographics",
        "description": "Asian students as a percent of total enrolled students.",
        "available_years": [2021, 2022]
    },
    "black_students": {
        "name": "Black (% Students)",
        "theme": "Demographics",
        "description": "Black students as a percent of total enrolled students.",
        "available_years": [2021, 2022]
    },
    "latino_students": {
        "name": "Latino (% Students)",
        "theme": "Demographics",
        "description": "Latino students as a percent of total enrolled students.",
        "available_years": [2021, 2022]
    },
    "native_students": {
        "name": "Native (% Students)",
        "theme": "Demographics",
        "description": "Native students as a percent of total enrolled students.",
        "available_years": [2021, 2022]
    },
    "pacific_islander_students": {
        "name": "Pacific Islander (% Students)",
        "theme": "Demographics",
        "description": "Pacific Islander students as a percent of total enrolled students.",
        "available_years": [2021, 2022]
    },
    "two_or_more_races_students": {
        "name": "Two or More Races (% Students)",
        "theme": "Demographics",
        "description": "Students of two or more races as a percent of total enrolled students.",
        "available_years": [2021, 2022]
    },
    "students_of_color": {
        "name": "Students of Color (%)",
        "theme": "Demographics",
        "description": "Students of color as a percent of total enrolled students.",
        "available_years": [2021, 2022]
    },
    "asian_population": {
        "name": "Asian (% Population)",
        "theme": "Demographics",
        "description": "Asian population as a percent of total population.",
        "available_years": [2021, 2022]
    },
    "black_population": {
        "name": "Black (% Population)",
        "theme": "Demographics",
        "description": "Black population as a percent of total population.",
        "available_years": [2021, 2022]
    },
    "native_population": {
        "name": "Native (% Population)",
        "theme": "Demographics",
        "description": "Native American population as a percent of total population.",
        "available_years": [2021, 2022]
    },
    "pacific_islander_population": {
        "name": "Pacific Islander (% Population)",
        "theme": "Demographics",
        "description": "Pacific Islander population as a percent of total population.",
        "available_years": [2021, 2022]
    },
    "two_or_more_races_population": {
        "name": "Two or More Races (% Population)",
        "theme": "Demographics",
        "description": "Population of two or more races as a percent of total population.",
        "available_years": [2021, 2022]
    },
    "other_race_population": {
        "name": "Other Race (% Population)",
        "theme": "Demographics",
        "description": "Other race population as a percent of total population.",
        "available_years": [2021, 2022]
    },
    "total_enrollment": {
        "name": "Total Enrollment",
        "theme": "Demographics",
        "description": "Total student enrollment in the geographic area.",
        "available_years": [2021, 2022]
    },
    # --- School District Finance ---
    "federal_revenue_pp": {
        "name": "Federal Revenue Per Pupil ($)",
        "theme": "School District Finance",
        "description": "Education revenue provided through federal programs, divided by total enrollment.",
        "available_years": [2021, 2022]
    },
    "federal_revenue": {
        "name": "Federal Revenue ($)",
        "theme": "School District Finance",
        "description": "Total education revenue provided through federal programs.",
        "available_years": [2021, 2022]
    },
    "local_property_tax_revenue": {
        "name": "Local Property Tax Revenue ($)",
        "theme": "School District Finance",
        "description": "Education revenue raised from property taxes.",
        "available_years": [2021, 2022]
    },
    "local_property_tax_revenue_pp": {
        "name": "Local Property Tax Revenue Per Pupil ($)",
        "theme": "School District Finance",
        "description": "Education revenue raised from property taxes, divided by total enrollment.",
        "available_years": [2021, 2022]
    },
    "local_revenue": {
        "name": "Local Revenue ($)",
        "theme": "School District Finance",
        "description": "Total education revenue from local sources.",
        "available_years": [2021, 2022]
    },
    "local_revenue_pp": {
        "name": "Local Revenue Per Pupil ($)",
        "theme": "School District Finance",
        "description": "Total education revenue from local sources, divided by total enrollment.",
        "available_years": [2021, 2022]
    },
    "state_revenue": {
        "name": "State Revenue ($)",
        "theme": "School District Finance",
        "description": "Total education revenue from state sources.",
        "available_years": [2021, 2022]
    },
    "state_revenue_pp": {
        "name": "State Revenue Per Pupil ($)",
        "theme": "School District Finance",
        "description": "Total education revenue from state sources, divided by total enrollment.",
        "available_years": [2021, 2022]
    },
    "total_revenue": {
        "name": "Total Revenue ($)",
        "theme": "School District Finance",
        "description": "Total education revenue from all sources.",
        "available_years": [2021, 2022]
    },
    "total_revenue_pp": {
        "name": "Total Revenue Per Pupil ($)",
        "theme": "School District Finance",
        "description": "Total education revenue from all sources, divided by total enrollment.",
        "available_years": [2021, 2022]
    },
    "federal_idea_allocation": {
        "name": "Federal IDEA Allocation ($)",
        "theme": "School District Finance",
        "description": "Federal funding for special education services under IDEA.",
        "available_years": [2021, 2022]
    },
    "federal_title_i_allocation": {
        "name": "Federal Title I Allocation ($)",
        "theme": "School District Finance",
        "description": "Federal Title I funding for schools with high percentages of low-income students.",
        "available_years": [2021, 2022]
    },
    "federal_title_iii_allocation": {
        "name": "Federal Title III Allocation ($)",
        "theme": "School District Finance",
        "description": "Federal Title III funding for English language learners.",
        "available_years": [2021, 2022]
    },
    "federal_title_vii_allocation": {
        "name": "Federal Title VII Allocation ($)",
        "theme": "School District Finance",
        "description": "Federal Title VII funding for Native American education.",
        "available_years": [2021, 2022]
    },
    # --- Community Indicators ---
    "broadband_internet": {
        "name": "Broadband Internet (% Having)",
        "theme": "Community",
        "description": "Percent of households with broadband internet access.",
        "available_years": [2021, 2022]
    },
    "mobile_internet_only": {
        "name": "Mobile Internet Only (% Having)",
        "theme": "Community",
        "description": "Percent of households with only mobile internet access.",
        "available_years": [2021, 2022]
    },
    "other_forms_internet": {
        "name": "Other Forms Internet Access (% Having)",
        "theme": "Community",
        "description": "Percent of households with other forms of internet access.",
        "available_years": [2021, 2022]
    },
    "english_primary_language": {
        "name": "English as Primary Language (% Households)",
        "theme": "Community",
        "description": "Percent of households where English is the primary language spoken.",
        "available_years": [2021, 2022]
    },
    "housing_vacancy_rate": {
        "name": "Housing Unit Vacancy Rate (%)",
        "theme": "Community",
        "description": "Percent of housing units that are vacant.",
        "available_years": [2021, 2022]
    },
    "percent_homes_owner_occupied": {
        "name": "Percent Homes, Owner-Occupied",
        "theme": "Community",
        "description": "Percent of homes that are owner-occupied.",
        "available_years": [2021, 2022]
    },
    "median_household_income": {
        "name": "Median Household Income ($)",
        "theme": "Community",
        "description": "Median household income in the geographic area.",
        "available_years": [2021, 2022]
    },
    "median_home_value": {
        "name": "Median Value, Owner-Occupied Homes ($)",
        "theme": "Community",
        "description": "Median value of owner-occupied homes.",
        "available_years": [2021, 2022]
    },
    "unemployment_rate": {
        "name": "Unemployment Rate (%)",
        "theme": "Community",
        "description": "Percent of the labor force that is unemployed.",
        "available_years": [2021, 2022]
    },
    # --- Health Indicators ---
    "lacking_health_insurance": {
        "name": "Lacking Health Insurance (% Adults)",
        "theme": "Health",
        "description": "Percent of adults (aged 18+) without health insurance.",
        "available_years": [2021, 2022]
    },
    "asthma_rate": {
        "name": "Asthma Rate (% Adults)",
        "theme": "Health",
        "description": "Percent of adults with asthma.",
        "available_years": [2021, 2022]
    },
    "obesity_rate": {
        "name": "Obesity Rate (% Adults)",
        "theme": "Health",
        "description": "Percent of adults who are obese.",
        "available_years": [2021, 2022]
    },
    "doctor_checkup": {
        "name": "Doctor Checkup in Past 12 Months (% Adults)",
        "theme": "Health",
        "description": "Percent of adults who had a routine doctor checkup in the past 12 months.",
        "available_years": [2021, 2022]
    },
    # --- Economic Security ---
    "snap_receipt": {
        "name": "SNAP Receipt in Past 12 Months (% Adults)",
        "theme": "Economic Security",
        "description": "Percent of adults who received SNAP benefits in the past 12 months.",
        "available_years": [2022]
    },
    "food_insecurity": {
        "name": "Food Insecurity in Past 12 Months (% Adults)",
        "theme": "Economic Security",
        "description": "Percent of adults who experienced food insecurity in the past 12 months.",
        "available_years": [2022]
    },
    "housing_insecurity": {
        "name": "Housing Insecurity in Past 12 Months (% Adults)",
        "theme": "Economic Security",
        "description": "Percent of adults who experienced housing insecurity in the past 12 months.",
        "available_years": [2022]
    },
    "unreliable_transportation": {
        "name": "Unreliable Transportation in Past 12 Months (% Adults)",
        "theme": "Economic Security",
        "description": "Percent of adults who experienced unreliable transportation in the past 12 months.",
        "available_years": [2022]
    },
    "utility_shutoff": {
        "name": "Utility Shut-Off Notice in Past 12 Months (% Adults)",
        "theme": "Economic Security",
        "description": "Percent of adults who received a utility shut-off notice in the past 12 months.",
        "available_years": [2022]
    },
}
