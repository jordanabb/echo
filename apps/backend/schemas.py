# apps/backend/schemas.py

from pydantic import BaseModel
from typing import List, Dict, Any, Optional

# ===================================================================
#   1. Metadata Endpoint (`GET /api/metadata`)
#      Defines the shape of the data that populates the UI filters.
# ===================================================================

class IndicatorMetadata(BaseModel):
    id: str
    name: str
    theme: str
    description: str
    available_years: List[int]

class MetadataResponse(BaseModel):
    indicators: List[IndicatorMetadata]
    geographies: Dict[str, Any]

# ===================================================================
#   2. Map View Endpoint (`GET /api/map-view`)
#      Defines the shape of the data needed to render the choropleth map.
# ===================================================================

class LegendEntry(BaseModel):
    label: str
    color: str

class MapViewData(BaseModel):
    geo_id: str
    value: Optional[float]  # Use Optional for values that can be null
    bin: int                # -1 for no data, 0-4 for quintiles

class MapViewResponse(BaseModel):
    geoJson: Dict[str, Any] # A GeoJSON FeatureCollection dictionary
    data: List[MapViewData]
    legend: List[LegendEntry]

class NoDataResponse(BaseModel):
    message: str

# ===================================================================
#   3. Table Data Endpoint (`POST /api/table-data`)
#      Defines the shape for requesting and receiving tabular data.
# ===================================================================

class TableDataRequest(BaseModel):
    geo_ids: List[str]
    indicator_ids: List[str]
    years: List[int]

# The response for table data is a list of dictionaries, which can be
# represented in Python as List[Dict[str, Any]]. We don't need a rigid
# Pydantic model for the response here because the columns are dynamic
# based on the user's request.