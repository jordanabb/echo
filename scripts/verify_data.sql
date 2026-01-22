-- Verification script to check data before export
-- Run this against your local database to ensure data is complete

-- Basic table counts
SELECT 'Table Counts' as check_type;
SELECT
    'geographies' as table_name,
    COUNT(*) as record_count
FROM geographies
UNION ALL
SELECT
    'results_data' as table_name,
    COUNT(*) as record_count
FROM results_data;

-- Geography levels breakdown
SELECT 'Geography Levels' as check_type;
SELECT
    geo_level,
    COUNT(*) as count,
    MIN(year) as min_year,
    MAX(year) as max_year
FROM geographies
GROUP BY geo_level
ORDER BY geo_level;

-- Indicator coverage
SELECT 'Indicator Coverage' as check_type;
SELECT
    indicator_id,
    COUNT(*) as record_count,
    COUNT(DISTINCT geo_id) as unique_geographies,
    MIN(year) as min_year,
    MAX(year) as max_year
FROM results_data
GROUP BY indicator_id
ORDER BY indicator_id;

-- Spatial data validation
SELECT 'Spatial Data Validation' as check_type;
SELECT
    geo_level,
    COUNT(*) as total_records,
    COUNT(CASE WHEN geometry IS NOT NULL THEN 1 END) as with_geometry,
    COUNT(CASE WHEN geometry IS NULL THEN 1 END) as missing_geometry
FROM geographies
GROUP BY geo_level;

-- Check for orphaned data (results without geographies)
SELECT 'Data Integrity Check' as check_type;
SELECT
    COUNT(*) as orphaned_results
FROM results_data r
WHERE NOT EXISTS (
    SELECT 1 FROM geographies g
    WHERE g.geo_id = r.geo_id
    AND g.geo_level = r.geo_level
    AND g.year = r.year
);

-- Value distribution check (look for nulls or outliers)
SELECT 'Value Statistics by Indicator' as check_type;
SELECT
    indicator_id,
    COUNT(*) as total_values,
    COUNT(value) as non_null_values,
    MIN(value) as min_value,
    MAX(value) as max_value,
    AVG(value) as avg_value
FROM results_data
GROUP BY indicator_id
ORDER BY indicator_id;

-- Final summary
SELECT 'Export Readiness Summary' as check_type;
SELECT
    (SELECT COUNT(*) FROM geographies) as total_geographies,
    (SELECT COUNT(*) FROM results_data) as total_data_points,
    (SELECT COUNT(DISTINCT indicator_id) FROM results_data) as unique_indicators,
    (SELECT COUNT(*) FROM geographies WHERE geometry IS NULL) as geometries_missing,
    (
        SELECT COUNT(*) FROM results_data r
        WHERE NOT EXISTS (
            SELECT 1 FROM geographies g
            WHERE g.geo_id = r.geo_id
            AND g.geo_level = r.geo_level
            AND g.year = r.year
        )
    ) as orphaned_data;
