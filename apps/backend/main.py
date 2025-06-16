# Location: apps/backend/main.py

# --- Standard Library Imports ---
import json

# --- Third-Party Imports ---
from fastapi import FastAPI, Depends, HTTPException
from sqlalchemy.orm import Session
from sqlalchemy import text
import pandas as pd
import geopandas as gpd
import mapclassify

# --- Local Application Imports ---
import models
import schemas
from database import SessionLocal, engine
from indicator_config import INDICATOR_METADATA, GEOGRAPHY_HIERARCHY, CHOROPLETH_PALETTE, NO_DATA_COLOR

# ===================================================================
#   Utility Functions
# ===================================================================

def normalize_geo_id(geo_id: str, geo_level: str) -> str:
    """
    Normalize geo_id to have the correct number of digits with zero-padding.
    
    Args:
        geo_id: The geographic identifier
        geo_level: The geographic level (county, tract, school_district, sldl, sldu)
    
    Returns:
        Normalized geo_id with proper zero-padding
    """
    # Define the expected lengths for each geography level
    geo_id_lengths = {
        'county': 5,
        'tract': 11,
        'school_district': 7,
        'sldl': 5,  # State Legislative District Lower
        'sldu': 5   # State Legislative District Upper
    }
    
    # Get the expected length for this geography level
    expected_length = geo_id_lengths.get(geo_level)
    
    if expected_length is None:
        # If we don't have a defined length, return as-is
        return str(geo_id)
    
    # Convert to string and pad with zeros on the left
    return str(geo_id).zfill(expected_length)

# ===================================================================
#   FastAPI App Initialization
# ===================================================================

# This line creates the database tables based on our models.py definitions
# if they don't already exist. It's safe to run every time.
models.Base.metadata.create_all(bind=engine)

app = FastAPI(
    title="ECHO Data Dashboard API",
    description="The backend API for the ECHO project, serving geographic and indicator data.",
    version="1.0.0",
)

# ===================================================================
#   Database Dependency
# ===================================================================

# This function is a "dependency" that provides a database session to any
# endpoint that needs it. It ensures the database connection is always
# properly opened and closed.
def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()

# ===================================================================
#   API Endpoints
# ===================================================================

@app.get("/api/metadata", response_model=schemas.MetadataResponse)
def get_metadata(db: Session = Depends(get_db)):
    """
    Provides the frontend with all necessary metadata to populate
    its dynamic filter controls and UI elements. This is the "source of truth"
    for what data is available in the application.
    """
    # Query the database to find which indicators actually exist
    existing_indicators_query = db.query(
        models.ResultsData.indicator_id
    ).distinct().all()
    
    existing_indicator_names = {row.indicator_id for row in existing_indicators_query}

    # Create a mapping from indicator names (as stored in DB) to config keys
    name_to_key_mapping = {meta["name"]: key for key, meta in INDICATOR_METADATA.items()}

    # Build indicator list using hardcoded metadata and available years
    indicator_list = []
    for id, meta in INDICATOR_METADATA.items():
        # Check if this indicator exists in the database
        if meta["name"] in existing_indicator_names:
            indicator_list.append(schemas.IndicatorMetadata(
                id=id,
                name=meta["name"],
                theme=meta["theme"],
                description=meta["description"],
                available_years=meta["available_years"]  # Use hardcoded years from config
            ))

    return {
        "indicators": indicator_list,
        "geographies": GEOGRAPHY_HIERARCHY
    }


@app.get(
    "/api/map-view",
    response_model=schemas.MapViewResponse,
    responses={404: {"model": schemas.NoDataResponse}}
)
def get_map_view_data(
    indicator: str,
    geo_level: str,
    year: int,
    state_filter: str = None,
    db: Session = Depends(get_db)
):
    """
    Provides all data required to render the main map view for a
    single indicator and year. Performs on-the-fly data classification
    using a quantile method to ensure a statistically sound and visually
    coherent map.
    """
    # Validate input parameters
    if not indicator or not geo_level or not year:
        raise HTTPException(status_code=400, detail="indicator, geo_level, and year are all required")
    
    # Create a mapping from indicator names (as stored in DB) to config keys
    name_to_key_mapping = {meta["name"]: key for key, meta in INDICATOR_METADATA.items()}
    
    # Determine the actual indicator name to use in the database query
    if indicator in INDICATOR_METADATA:
        # It's a config key, use the corresponding name for DB query
        db_indicator_name = INDICATOR_METADATA[indicator]["name"]
    elif indicator in name_to_key_mapping:
        # It's already a full name, use it directly
        db_indicator_name = indicator
    else:
        # Invalid indicator
        raise HTTPException(status_code=400, detail=f"Invalid indicator: {indicator}")
    
    # First, validate that the requested geo_level exists in the database
    geo_level_check_query = text("""
        SELECT DISTINCT geo_level 
        FROM geographies 
        WHERE geo_level = :geo_level AND year = :year
        LIMIT 1;
    """)
    
    geo_level_result = db.execute(geo_level_check_query, {"geo_level": geo_level, "year": year}).fetchone()
    if not geo_level_result:
        raise HTTPException(status_code=404, detail=f"No geographic data found for level '{geo_level}' in year {year}")
    
    # Construct a SQL query to get all geographies for the EXACT level and year, and LEFT JOIN
    # the relevant indicator data. This ensures we can draw all shapes, even
    # those with no data. Use DISTINCT ON to handle duplicate geo_ids.
    # Add state filtering if state_filter is provided
    state_filter_clause = ""
    query_params = {"indicator": db_indicator_name, "year": year, "geo_level": geo_level}
    
    if state_filter:
        # Filter by state using the first 2 digits of geo_id (state FIPS code)
        state_filter_clause = "AND LEFT(g.geo_id, 2) = :state_filter"
        query_params["state_filter"] = state_filter
    
    sql_query = text(f"""
        SELECT DISTINCT ON (g.geo_id) 
               g.geo_id, 
               g.geo_name,
               g.geo_level,
               g.year as geo_year,
               g.geometry, 
               r.value,
               r.year as data_year
        FROM geographies g
        LEFT JOIN results_data r ON g.geo_id = r.geo_id
                               AND r.indicator_id = :indicator
                               AND r.year = :year
        WHERE g.geo_level = :geo_level
          AND g.year = :year
          {state_filter_clause}
        ORDER BY g.geo_id, r.value DESC NULLS LAST;
    """)

    # Execute the query and load directly into a GeoPandas GeoDataFrame
    gdf = gpd.read_postgis(
        sql_query,
        db.bind,
        params=query_params,
        geom_col='geometry'
    )

    if gdf.empty:
        raise HTTPException(status_code=404, detail=f"No geographic data found for level '{geo_level}' in year {year}")

    # Validate that all returned data is for the correct geographic level
    unique_geo_levels = gdf['geo_level'].unique()
    if len(unique_geo_levels) != 1 or unique_geo_levels[0] != geo_level:
        print(f"ERROR: Expected geo_level '{geo_level}', but got: {unique_geo_levels}")
        raise HTTPException(status_code=500, detail=f"Data integrity error: mixed geographic levels returned")
    
    # Validate that all returned data is for the correct year
    unique_geo_years = gdf['geo_year'].unique()
    if len(unique_geo_years) != 1 or unique_geo_years[0] != year:
        print(f"ERROR: Expected year {year}, but got geo years: {unique_geo_years}")
        raise HTTPException(status_code=500, detail=f"Data integrity error: mixed years returned")

    # Log sample data for debugging (first 3 records only)
    sample_data = gdf[['geo_id', 'geo_level', 'geo_year', 'value', 'data_year']].head(3)
    print(f"API Debug - Requested: indicator={indicator}, geo_level={geo_level}, year={year}")
    print(f"API Debug - Returned {len(gdf)} features for geo_level='{unique_geo_levels[0]}', year={unique_geo_years[0]}")
    print(f"API Debug - Sample data:\n{sample_data.to_string()}")

    # Normalize geo_ids to ensure consistent formatting
    gdf['geo_id'] = gdf['geo_id'].apply(lambda x: normalize_geo_id(str(x), geo_level))

    # Convert string values to numeric (fix for data type issue)
    gdf['value'] = pd.to_numeric(gdf['value'], errors='coerce')
    
    # Classify the data into 5 bins (quintiles)
    data_for_classification = gdf['value'].dropna()

    if data_for_classification.empty or len(data_for_classification.unique()) < 5:
        # If there's no data or not enough variation, assign all to 'no data'
        gdf['bin'] = -1
        legend_entries = []
    else:
        classifier = mapclassify.Quantiles(data_for_classification, k=5)
        gdf['bin'] = gdf['value'].apply(lambda x: classifier.find_bin(x) if pd.notna(x) else -1)

        # Create the human-readable legend
        legend_entries = []
        for i, a_bin in enumerate(classifier.bins):
            lower_bound = classifier.bins[i-1] if i > 0 else data_for_classification.min()
            label = f"{lower_bound:,.2f} - {a_bin:,.2f}"
            legend_entries.append(schemas.LegendEntry(label=label, color=CHOROPLETH_PALETTE[i]))

    legend_entries.append(schemas.LegendEntry(label="No Data", color=NO_DATA_COLOR))
    
    # Prepare the final payload
    # Convert GeoDataFrame to a GeoJSON dictionary (include geo_name)
    geo_json_dict = json.loads(gdf[['geo_id', 'geo_name', 'geometry']].to_json())

    # Normalize geo_ids in the response data
    response_data = [
        schemas.MapViewData(
            geo_id=normalize_geo_id(str(row.geo_id), geo_level), 
            value=None if pd.isna(row.value) else float(row.value), 
            bin=int(row.bin)
        )
        for row in gdf[['geo_id', 'value', 'bin']].itertuples()
    ]

    # Final validation: ensure response data only contains the requested geo_level
    print(f"API Debug - Returning {len(response_data)} data points and {len(geo_json_dict.get('features', []))} GeoJSON features")

    return schemas.MapViewResponse(
        geoJson=geo_json_dict,
        data=response_data,
        legend=legend_entries
    )


@app.post("/api/table-data")
def get_table_data(request: schemas.TableDataRequest, db: Session = Depends(get_db)):
    """
    Provides custom, multi-year, multi-indicator datasets by "pivoting"
    the data in the database. This is a powerful endpoint designed to
    feed data tables and charts for deep analysis.
    """
    if not request.geo_ids or not request.indicator_ids or not request.years:
        raise HTTPException(status_code=400, detail="geo_ids, indicator_ids, and years are all required.")

    # Create a mapping from indicator names (as stored in DB) to config keys
    name_to_key_mapping = {meta["name"]: key for key, meta in INDICATOR_METADATA.items()}
    
    # Dynamically and safely create the PIVOT columns for the SQL query
    pivot_columns = []
    valid_indicator_names = []
    
    for ind_id in request.indicator_ids:
        # Check if the indicator ID matches either a config key OR a full name
        if ind_id in INDICATOR_METADATA:
            # It's a config key, use the corresponding name for DB query
            indicator_name = INDICATOR_METADATA[ind_id]["name"]
            pivot_columns.append(f"MAX(CASE WHEN indicator_id = '{indicator_name}' THEN value END) AS \"{ind_id}\"")
            valid_indicator_names.append(indicator_name)
        elif ind_id in name_to_key_mapping:
            # It's a full name, use it directly for DB query
            pivot_columns.append(f"MAX(CASE WHEN indicator_id = '{ind_id}' THEN value END) AS \"{name_to_key_mapping[ind_id]}\"")
            valid_indicator_names.append(ind_id)
        else:
            # Invalid indicator - not found in config
            continue

    if not pivot_columns:
        raise HTTPException(status_code=400, detail="Invalid indicator_ids provided.")

    pivot_sql = ", ".join(pivot_columns)

    # Note: Assumes geo_id is the unique key across all years in the `geographies` table.
    # If not, the join might need adjustment.
    sql_query = text(f"""
        SELECT
            r.geo_id,
            g.geo_name,
            r.year,
            {pivot_sql}
        FROM results_data r
        JOIN geographies g ON r.geo_id = g.geo_id
        WHERE r.geo_id IN :geo_ids
          AND r.indicator_id IN :indicator_ids
          AND r.year IN :years
        GROUP BY r.geo_id, g.geo_name, r.year
        ORDER BY g.geo_name, r.year;
    """)

    # Use pandas for efficient execution and conversion to JSON
    df = pd.read_sql_query(
        sql_query,
        db.bind,
        params={
            "geo_ids": tuple(request.geo_ids),
            "indicator_ids": tuple(valid_indicator_names),  # Use the validated names for DB query
            "years": tuple(request.years),
        }
    )
    
    if df.empty:
        return []

    # Convert pandas NaN (Not a Number) to None for proper JSON nulls
    df = df.where(pd.notna(df), None)

    return df.to_dict(orient='records')
