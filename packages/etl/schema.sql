-- This script is designed to be re-runnable. It first drops old tables if they exist.
DROP TABLE IF EXISTS results_data;
DROP TABLE IF EXISTS geographies;
DROP TYPE IF EXISTS geo_level_enum;


-- We create a custom "type" for geo_level to ensure only valid values can be inserted.
-- This enforces data integrity.
CREATE TYPE geo_level_enum AS ENUM ('county', 'school_district', 'sldu', 'sldl', 'census_tract');


-- Create the table to hold all geographic information and shapes.
CREATE TABLE geographies (
    -- Define the columns and their data types
    geo_id VARCHAR(20) NOT NULL,
    geo_level geo_level_enum NOT NULL,
    year INT NOT NULL,
    geo_name VARCHAR(255) NOT NULL,
    geometry geometry(MultiPolygon, 4326) NOT NULL,

    -- This is the crucial part: define a composite PRIMARY KEY.
    -- This ensures that the combination of these three columns is always unique,
    -- perfectly handling the legislative district issue.
    PRIMARY KEY (geo_id, geo_level, year)
);

-- Create a spatial index on the geometry column. This is ESSENTIAL for making
-- map-based queries (like finding all shapes in a certain area) extremely fast.
CREATE INDEX geographies_geom_idx ON geographies USING GIST (geometry);


-- Create the table to hold all the individual indicator data points.
CREATE TABLE results_data (
    id SERIAL PRIMARY KEY, -- A simple, auto-incrementing number for each row
    geo_id VARCHAR(20) NOT NULL,
    geo_level geo_level_enum NOT NULL,
    year INT NOT NULL,
    indicator_id VARCHAR(100) NOT NULL,
    value NUMERIC(20, 4), -- A high-precision numeric type for storing various kinds of numbers

    -- This sets up the foreign key relationship to our new composite primary key.
    -- It ensures that you cannot have a data point for a geography that doesn't exist
    -- in the 'geographies' table, which maintains data integrity.
    FOREIGN KEY (geo_id, geo_level, year) REFERENCES geographies (geo_id, geo_level, year)
);

-- Create an index on the foreign key columns to make JOINs and lookups on this table fast.
CREATE INDEX results_data_geo_level_year_idx ON results_data (geo_id, geo_level, year);