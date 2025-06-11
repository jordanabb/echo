from sqlalchemy import Column, Integer, String, Float
from geoalchemy2 import Geometry
from database import Base

class Geography(Base):
    __tablename__ = 'geographies'

    # The primary key for ORM purposes.
    # Assumes a simple integer primary key column named 'id' exists.
    id = Column(Integer, primary_key=True, index=True)

    # The actual data columns
    geo_id = Column(String, index=True)
    geo_name = Column(String)
    geo_level = Column(String, index=True)
    year = Column(Integer, index=True) # Assuming year is part of the geography record
    geometry = Column(Geometry('MULTIPOLYGON'))


class ResultsData(Base):
    __tablename__ = 'results_data'

    # The primary key for ORM purposes.
    id = Column(Integer, primary_key=True, index=True)

    # The actual data columns
    geo_id = Column(String, index=True)
    indicator_id = Column(String, index=True)
    year = Column(Integer, index=True)
    value = Column(Float, nullable=True) # Allow null values for data points
