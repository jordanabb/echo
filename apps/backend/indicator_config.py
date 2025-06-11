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
    "schooldist": {"name": "School District", "sublevels": []},
    "sldl": {"name": "State House District", "sublevels": []},
    "sldu": {"name": "State Senate District", "sublevels": []},
}

# --- INDICATOR METADATA ---
INDICATOR_METADATA = {
    # --- School District Finance ---
    "total_revenue_pp": {
        "name": "Total Revenue Per Pupil ($)",
        "theme": "School District Finance",
        "description": "Total education revenue from all federal, state, and local sources, divided by total number of enrolled students."
    },
    "federal_revenue_pp": {
        "name": "Federal Revenue Per Pupil ($)",
        "theme": "School District Finance",
        "description": "Education revenue provided through federal programs, divided by total enrollment."
    },
    "state_revenue_pp": {
        "name": "State Revenue Per Pupil ($)",
        "theme": "School District Finance",
        "description": "Education revenue provided by state government, divided by total enrollment."
    },
    "local_revenue_pp": {
        "name": "Local Revenue Per Pupil ($)",
        "theme": "School District Finance",
        "description": "Education revenue raised from local sources, including property taxes and other local income streams, divided by total enrollment."
    },
    "local_property_tax_revenue_pp": {
        "name": "Local Property Tax Revenue ($)",
        "theme": "School District Finance",
        "description": "Education revenue raised from property taxes specifically."
    },
    # --- Poverty ---
    "poverty_rate": {
        "name": "Poverty Rate (%)",
        "theme": "Poverty",
        "description": "Percent of school-age children (those aged 5-17) residing in the geographic unit who live in households that fall below the federal poverty line."
    },
    # --- Demographics & Enrollment ---
    "total_enrollment": {
        "name": "Total Enrollment",
        "theme": "Demographics",
        "description": "Total number of enrolled students in a school district."
    },
    "pct_white": {
        "name": "White (% Students)",
        "theme": "Demographics",
        "description": "White students as a percent of total enrolled students."
    },
    "pct_black": {
        "name": "Black (% Students)",
        "theme": "Demographics",
        "description": "Black students as a percent of total enrolled students."
    },
    "pct_latino": {
        "name": "Latino (% Students)",
        "theme": "Demographics",
        "description": "Latino students as a percent of total enrolled students."
    },
    "pct_asian": {
        "name": "Asian (% Students)",
        "theme": "Demographics",
        "description": "Asian students as a percent of total enrolled students."
    },
    "pct_native": {
        "name": "Native (% Students)",
        "theme": "Demographics",
        "description": "Native students as a percent of total enrolled students."
    },
    "pct_pacific_islander": {
        "name": "Pacific Islander (% Students)",
        "theme": "Demographics",
        "description": "Pacific Islander students as a percent of total enrolled students."
    },
    # --- Community Indicators (ACS) ---
    "median_income": {
        "name": "Median Household Income ($)",
        "theme": "Community",
        "description": "Median income of all households in the geographic unit. (Source: ACS)"
    },
    "unemployment_rate": {
        "name": "Unemployment Rate (%)",
        "theme": "Community",
        "description": "Percent of the civilian labor force that is unemployed. (Source: ACS)"
    },
    "pct_broadband": {
        "name": "Broadband Internet (% Having)",
        "theme": "Community",
        "description": "Percent of households with broadband internet access. (Source: ACS)"
    },
    "pct_college_or_higher": {
        "name": "College Degree Attained (% Adults ≥25)",
        "theme": "Community",
        "description": "Percent of adults aged 25 or older with an associate or bachelor's degree. (Source: ACS)"
    },
    # --- Health Indicators (CDC PLACES) ---
    "lacking_health_insurance": {
        "name": "Lacking Health Insurance (% Adults)",
        "theme": "Health",
        "description": "Percent of adults (aged 18+) without health insurance. (Source: CDC PLACES)"
    },
    "food_insecurity": {
        "name": "Food Insecurity in Past 12 Months (% Adults)",
        "theme": "Health",
        "description": "Percent of adults reporting insufficient food access in the past year. (Source: CDC PLACES)"
    },
    # --- Environment ---
    "air_quality_index": {
        "name": "Median Air Quality Index",
        "theme": "Environment",
        "description": "Median value of daily U.S. Air Quality Index. Higher values represent more hazardous air quality. (Source: EPA)"
    },
}