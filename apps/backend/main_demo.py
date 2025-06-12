# Location: apps/backend/main_demo.py
# Demo version without database dependency

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
import schemas
from indicator_config import INDICATOR_METADATA, GEOGRAPHY_HIERARCHY

# ===================================================================
#   FastAPI App Initialization
# ===================================================================

app = FastAPI(
    title="ECHO Data Dashboard API (Demo)",
    description="Demo version of the backend API for the ECHO project.",
    version="1.0.0-demo",
)

# Add CORS middleware to allow frontend connections
app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:5177", "http://localhost:3000"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# ===================================================================
#   API Endpoints
# ===================================================================

@app.get("/api/metadata", response_model=schemas.MetadataResponse)
def get_metadata():
    """
    Provides the frontend with all necessary metadata to populate
    its dynamic filter controls and UI elements. This is the "source of truth"
    for what data is available in the application.
    
    Demo version with mock data.
    """
    
    # Create mock available years for each indicator
    mock_years = [2023, 2022, 2021, 2020, 2019]
    
    # Process indicators with mock data
    indicator_list = []
    for id, meta in INDICATOR_METADATA.items():
        indicator_list.append(schemas.IndicatorMetadata(
            id=id,
            name=meta["name"],
            theme=meta["theme"],
            description=meta["description"],
            available_years=mock_years
        ))

    return {
        "indicators": indicator_list,
        "geographies": GEOGRAPHY_HIERARCHY
    }

@app.get("/")
def root():
    """Root endpoint for health check"""
    return {"message": "ECHO Data Dashboard API (Demo) is running"}

@app.get("/health")
def health_check():
    """Health check endpoint"""
    return {"status": "healthy", "version": "1.0.0-demo"}
