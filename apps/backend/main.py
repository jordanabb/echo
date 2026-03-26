# Location: apps/backend/main.py

# --- Standard Library Imports ---
import json
import os
from typing import List

# --- Third-Party Imports ---
from fastapi import FastAPI, Depends, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from sqlalchemy.orm import Session
from sqlalchemy import text
import pandas as pd
import geopandas as gpd
import mapclassify
from dotenv import load_dotenv

# Load environment variables
load_dotenv()

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
        'congressional_district': 4,
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
#   CORS Configuration
# ===================================================================

# Get allowed origins from environment variable, with fallback for development
cors_origins_str = os.getenv(
    "CORS_ORIGINS",
    "http://localhost:3000,http://localhost:5175,http://localhost:8000"
)
allowed_origins: List[str] = [origin.strip() for origin in cors_origins_str.split(",")]

app.add_middleware(
    CORSMiddleware,
    allow_origins=allowed_origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
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

@app.get("/health")
def health_check(db: Session = Depends(get_db)):
    """
    Health check endpoint for load balancers and monitoring.
    Returns 200 if the service and database are healthy.
    """
    try:
        # Test database connection
        db.execute(text("SELECT 1"))
        return {
            "status": "healthy",
            "service": "echo-api",
            "database": "connected"
        }
    except Exception as e:
        raise HTTPException(
            status_code=503,
            detail=f"Service unhealthy: {str(e)}"
        )

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
        # Filter by state using the optimized state_fips column
        state_filter_clause = "AND g.state_fips = :state_filter"
        query_params["state_filter"] = state_filter
    
    sql_query = text(f"""
        SELECT DISTINCT ON (g.geo_id)
               g.geo_id,
               g.geo_name,
               ST_AsGeoJSON(g.geometry)::json as geometry,
               r.value
        FROM geographies g
        LEFT JOIN results_data r ON g.geo_id = r.geo_id
                               AND r.indicator_id = :indicator
                               AND r.year = :year
                               AND r.geo_level = :geo_level
        WHERE g.geo_level = :geo_level
          AND g.year = :year
          {state_filter_clause}
        ORDER BY g.geo_id, r.value DESC NULLS LAST;
    """)

    result = db.execute(sql_query, query_params).fetchall()

    if not result:
        raise HTTPException(status_code=404, detail=f"No geographic data found for level '{geo_level}' in year {year}")

    # Build data structures directly — no geopandas needed
    features = []
    values = []
    for i, row in enumerate(result):
        geo_id = normalize_geo_id(str(row.geo_id), geo_level)
        val = None
        if row.value is not None:
            try:
                val = float(row.value)
            except (ValueError, TypeError):
                val = None
        features.append({
            "type": "Feature",
            "id": i,
            "properties": {"geo_id": geo_id, "geo_name": row.geo_name},
            "geometry": row.geometry
        })
        values.append((geo_id, val))

    # Classify into 5 bins (quintiles)
    valid_values = [v for _, v in values if v is not None]

    if len(set(valid_values)) < 5:
        bins_map = {geo_id: -1 for geo_id, _ in values}
        legend_entries = []
    else:
        classifier = mapclassify.Quantiles(pd.Series(valid_values), k=5)
        bins_map = {}
        for geo_id, val in values:
            if val is None:
                bins_map[geo_id] = -1
            else:
                bins_map[geo_id] = int(classifier.find_bin(val))

        legend_entries = []
        for i, a_bin in enumerate(classifier.bins):
            lower_bound = classifier.bins[i-1] if i > 0 else min(valid_values)
            label = f"{lower_bound:,.2f} - {a_bin:,.2f}"
            legend_entries.append(schemas.LegendEntry(label=label, color=CHOROPLETH_PALETTE[i]))

    legend_entries.append(schemas.LegendEntry(label="No Data", color=NO_DATA_COLOR))

    geo_json_dict = {"type": "FeatureCollection", "features": features}

    response_data = [
        schemas.MapViewData(geo_id=geo_id, value=val, bin=bins_map[geo_id])
        for geo_id, val in values
    ]

    print(f"API Debug - Returning {len(response_data)} data points and {len(features)} GeoJSON features")

    return schemas.MapViewResponse(
        geoJson=geo_json_dict,
        data=response_data,
        legend=legend_entries
    )


@app.get(
    "/api/geometries",
    response_model=schemas.GeometriesResponse,
    responses={404: {"model": schemas.NoDataResponse}}
)
def get_geometries(
    geo_level: str,
    year: int,
    state_filter: str = None,
    db: Session = Depends(get_db)
):
    """
    Provides ONLY the geometric boundaries for a given geography level and year.
    This endpoint is designed for caching - geometries don't change when indicators change.
    state_filter accepts a single FIPS code or comma-separated codes.
    """
    # Validate input parameters
    if not geo_level or not year:
        raise HTTPException(status_code=400, detail="geo_level and year are required")

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

    # Construct a SQL query to get all geographies for the EXACT level and year
    # Add state filtering if state_filter is provided
    state_filter_clause = ""
    query_params = {"year": year, "geo_level": geo_level}

    if state_filter:
        state_codes = [s.strip() for s in state_filter.split(',') if s.strip()]
        if len(state_codes) == 1:
            state_filter_clause = "AND g.state_fips = :state_filter"
            query_params["state_filter"] = state_codes[0]
        elif len(state_codes) > 1:
            state_filter_clause = "AND g.state_fips IN :state_filter"
            query_params["state_filter"] = tuple(state_codes)
    
    sql_query = text(f"""
        SELECT DISTINCT ON (g.geo_id)
               g.geo_id,
               g.geo_name,
               ST_AsGeoJSON(g.geometry)::json as geometry
        FROM geographies g
        WHERE g.geo_level = :geo_level
          AND g.year = :year
          {state_filter_clause}
        ORDER BY g.geo_id;
    """)

    result = db.execute(sql_query, query_params).fetchall()

    if not result:
        raise HTTPException(status_code=404, detail=f"No geographic data found for level '{geo_level}' in year {year}")

    # Build GeoJSON directly from SQL results — no geopandas needed
    features = []
    for i, row in enumerate(result):
        geo_id = normalize_geo_id(str(row.geo_id), geo_level)
        features.append({
            "type": "Feature",
            "id": i,
            "properties": {"geo_id": geo_id, "geo_name": row.geo_name},
            "geometry": row.geometry
        })

    geo_json_dict = {"type": "FeatureCollection", "features": features}

    print(f"Geometries API - Returning {len(features)} GeoJSON features for {geo_level}")

    return schemas.GeometriesResponse(
        geoJson=geo_json_dict,
        geo_level=geo_level,
        year=year,
        count=len(features)
    )


@app.get("/api/geo-ids")
def get_geo_ids(
    geo_level: str,
    year: int,
    state_filter: str = None,
    db: Session = Depends(get_db)
):
    """Returns only geo_ids for a given level/year — no geometry, very fast. Supports comma-separated state_filter."""
    query_params = {"geo_level": geo_level, "year": year}
    state_clause = ""
    if state_filter:
        state_codes = [s.strip() for s in state_filter.split(',') if s.strip()]
        if len(state_codes) == 1:
            state_clause = "AND state_fips = :state_filter"
            query_params["state_filter"] = state_codes[0]
        elif len(state_codes) > 1:
            state_clause = "AND state_fips IN :state_filter"
            query_params["state_filter"] = tuple(state_codes)

    result = db.execute(text(f"""
        SELECT DISTINCT geo_id
        FROM geographies
        WHERE geo_level = :geo_level AND year = :year {state_clause}
        ORDER BY geo_id
    """), query_params).fetchall()

    return [row.geo_id for row in result]


@app.get(
    "/api/indicator-data",
    response_model=schemas.IndicatorDataResponse,
    responses={404: {"model": schemas.NoDataResponse}}
)
def get_indicator_data(
    indicator: str,
    geo_level: str,
    year: int,
    state_filter: str = None,
    db: Session = Depends(get_db)
):
    """
    Provides ONLY the indicator data values for a given indicator, geography level, and year.
    This endpoint is optimized for fast variable switching without re-fetching geometries.
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
    
    # Add state filtering if state_filter is provided (supports comma-separated)
    state_filter_clause = ""
    query_params = {"indicator": db_indicator_name, "year": year, "geo_level": geo_level}

    if state_filter:
        state_codes = [s.strip() for s in state_filter.split(',') if s.strip()]
        if len(state_codes) == 1:
            state_filter_clause = "AND g.state_fips = :state_filter"
            query_params["state_filter"] = state_codes[0]
        elif len(state_codes) > 1:
            state_filter_clause = "AND g.state_fips IN :state_filter"
            query_params["state_filter"] = tuple(state_codes)

    # Query to get indicator data with geo_names for reference
    sql_query = text(f"""
        SELECT DISTINCT ON (g.geo_id) 
               g.geo_id, 
               g.geo_name,
               r.value
        FROM geographies g
        LEFT JOIN results_data r ON g.geo_id = r.geo_id
                               AND r.indicator_id = :indicator
                               AND r.year = :year
        WHERE g.geo_level = :geo_level
          AND g.year = :year
          {state_filter_clause}
        ORDER BY g.geo_id;
    """)

    # Execute the query
    result = db.execute(sql_query, query_params).fetchall()
    
    if not result:
        raise HTTPException(status_code=404, detail=f"No data found for indicator '{indicator}' at level '{geo_level}' in year {year}")

    # Convert to list of dictionaries and normalize geo_ids
    data_list = []
    values_for_classification = []
    
    for row in result:
        normalized_geo_id = normalize_geo_id(str(row.geo_id), geo_level)
        value = None if row.value is None else float(row.value)
        
        data_list.append({
            "geo_id": normalized_geo_id,
            "geo_name": row.geo_name,
            "value": value
        })
        
        if value is not None:
            values_for_classification.append(value)
    
    # Classify the data into 5 bins (quintiles) for legend
    legend_entries = []
    if values_for_classification and len(set(values_for_classification)) >= 5:
        classifier = mapclassify.Quantiles(values_for_classification, k=5)
        
        # Add bin information to data
        for item in data_list:
            if item["value"] is not None:
                item["bin"] = classifier.find_bin(item["value"])
            else:
                item["bin"] = -1
        
        # Create the human-readable legend
        for i, a_bin in enumerate(classifier.bins):
            lower_bound = classifier.bins[i-1] if i > 0 else min(values_for_classification)
            label = f"{lower_bound:,.2f} - {a_bin:,.2f}"
            legend_entries.append(schemas.LegendEntry(label=label, color=CHOROPLETH_PALETTE[i]))
    else:
        # If there's no data or not enough variation, assign all to 'no data'
        for item in data_list:
            item["bin"] = -1
    
    legend_entries.append(schemas.LegendEntry(label="No Data", color=NO_DATA_COLOR))
    
    print(f"Indicator Data API - Returning {len(data_list)} data points for indicator '{indicator}'")

    return schemas.IndicatorDataResponse(
        data=data_list,
        legend=legend_entries,
        indicator=indicator,
        geo_level=geo_level,
        year=year
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

    # Build the SQL query with optional geo_level filtering
    geo_level_clause = ""
    query_params = {
        "geo_ids": tuple(request.geo_ids),
        "indicator_ids": tuple(valid_indicator_names),  # Use the validated names for DB query
        "years": tuple(request.years),
    }
    
    if request.geo_level:
        geo_level_clause = "AND g.geo_level = :geo_level"
        query_params["geo_level"] = request.geo_level

    search_clause = ""
    if request.search:
        search_clause = "AND g.geo_name ILIKE :search"
        query_params["search"] = f"%{request.search}%"

    # Build pagination clause
    pagination_clause = ""
    if request.page is not None:
        page = max(1, request.page)
        page_size = max(1, min(request.page_size or 100, 1000))
        offset = (page - 1) * page_size
        pagination_clause = f"LIMIT {page_size} OFFSET {offset}"

    # Single query with COUNT(*) OVER() window function to get total in one round-trip
    sql_query = text(f"""
        SELECT *, COUNT(*) OVER() AS _total FROM (
            SELECT
                r.geo_id,
                g.geo_name,
                g.state_fips,
                r.year,
                {pivot_sql}
            FROM results_data r
            JOIN geographies g ON r.geo_id = g.geo_id AND g.year = r.year
            WHERE r.geo_id IN :geo_ids
              AND r.indicator_id IN :indicator_ids
              AND r.year IN :years
              {geo_level_clause}
              {search_clause}
            GROUP BY r.geo_id, g.geo_name, g.state_fips, r.year
            ORDER BY g.geo_name, r.year
        ) sub
        {pagination_clause};
    """)

    # Use pandas for efficient execution and conversion to JSON
    df = pd.read_sql_query(
        sql_query,
        db.bind,
        params=query_params
    )

    if df.empty:
        return {"data": [], "total": 0}

    # Extract total from window function, then drop the column
    total = int(df["_total"].iloc[0])
    df = df.drop(columns=["_total"])

    # Convert pandas NaN (Not a Number) to None for proper JSON nulls
    df = df.where(pd.notna(df), None)

    return {"data": df.to_dict(orient='records'), "total": total}
