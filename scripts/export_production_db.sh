#!/bin/bash
# Export production-ready database for IT team to load into AWS RDS
# This script creates a clean SQL dump with all data and schema

set -e  # Exit on error

# Configuration
DB_CONTAINER="echo_db"
DB_USER="user"
DB_NAME="echo_data"
OUTPUT_DIR="./production_export"
TIMESTAMP=$(date +%Y%m%d_%H%M%S)
OUTPUT_FILE="${OUTPUT_DIR}/echo_production_${TIMESTAMP}.sql"

# Colors for output
GREEN='\033[0;32m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

echo -e "${BLUE}================================${NC}"
echo -e "${BLUE}Production Database Export${NC}"
echo -e "${BLUE}================================${NC}"

# Create output directory if it doesn't exist
mkdir -p "$OUTPUT_DIR"

# Check if Docker container is running
if ! docker ps | grep -q "$DB_CONTAINER"; then
    echo "Error: Database container '$DB_CONTAINER' is not running"
    echo "Please start it with: docker-compose up -d"
    exit 1
fi

echo -e "\n${GREEN}Step 1:${NC} Exporting database schema and data..."

# Export the database using pg_dump
docker exec "$DB_CONTAINER" pg_dump \
    -U "$DB_USER" \
    -d "$DB_NAME" \
    --clean \
    --if-exists \
    --no-owner \
    --no-privileges \
    -f /tmp/export.sql

# Copy from container to host
docker cp "${DB_CONTAINER}:/tmp/export.sql" "$OUTPUT_FILE"

# Clean up temp file in container
docker exec "$DB_CONTAINER" rm /tmp/export.sql

echo -e "${GREEN}✓${NC} Database exported successfully"

# Get file size
FILE_SIZE=$(du -h "$OUTPUT_FILE" | cut -f1)

echo -e "\n${GREEN}Step 2:${NC} Creating compressed backup..."

# Compress the SQL file
gzip -c "$OUTPUT_FILE" > "${OUTPUT_FILE}.gz"
COMPRESSED_SIZE=$(du -h "${OUTPUT_FILE}.gz" | cut -f1)

echo -e "${GREEN}✓${NC} Compressed backup created"

# Create a README for IT team
README_FILE="${OUTPUT_DIR}/README_FOR_IT.txt"
cat > "$README_FILE" << EOF
ECHO Database Export - Production Ready
======================================

Generated: $(date)
Database: $DB_NAME
Export Type: Full schema + data

FILES IN THIS PACKAGE:
----------------------
1. echo_production_${TIMESTAMP}.sql        - Full SQL dump ($FILE_SIZE)
2. echo_production_${TIMESTAMP}.sql.gz     - Compressed version ($COMPRESSED_SIZE)
3. README_FOR_IT.txt                       - This file

WHAT'S INCLUDED:
----------------
- Complete database schema with PostGIS extensions
- All geographic boundaries (counties, tracts, districts, etc.)
- All indicator data
- Spatial indices for performance
- Foreign key constraints for data integrity

HOW TO RESTORE TO AWS RDS:
--------------------------

Option 1: Using the uncompressed file
  psql -h your-rds-endpoint.region.rds.amazonaws.com \\
       -U postgres \\
       -d echo_data \\
       -f echo_production_${TIMESTAMP}.sql

Option 2: Using the compressed file
  gunzip -c echo_production_${TIMESTAMP}.sql.gz | \\
  psql -h your-rds-endpoint.region.rds.amazonaws.com \\
       -U postgres \\
       -d echo_data

PREREQUISITES:
--------------
1. RDS PostgreSQL 15 instance created
2. PostGIS extension enabled:
   CREATE EXTENSION IF NOT EXISTS postgis;
   CREATE EXTENSION IF NOT EXISTS postgis_topology;
3. Database 'echo_data' created:
   CREATE DATABASE echo_data;
4. Network access from your computer to RDS (security groups configured)

VERIFICATION AFTER RESTORE:
---------------------------
Check table counts:
  SELECT
    (SELECT COUNT(*) FROM geographies) as geographies_count,
    (SELECT COUNT(*) FROM results_data) as results_count;

Check spatial data:
  SELECT COUNT(*) FROM geographies WHERE geometry IS NOT NULL;

ESTIMATED RESTORE TIME:
-----------------------
Typically 2-10 minutes depending on data size and network speed.

SUPPORT:
--------
If you encounter issues during restore, contact the development team.
Common issues are documented in the main DEPLOYMENT.md file.

EOF

echo -e "${GREEN}✓${NC} Created README for IT team"

# Display summary
echo -e "\n${BLUE}================================${NC}"
echo -e "${BLUE}Export Complete!${NC}"
echo -e "${BLUE}================================${NC}"
echo -e "\nFiles created in ${GREEN}${OUTPUT_DIR}/${NC}:"
echo -e "  1. SQL dump:        echo_production_${TIMESTAMP}.sql (${FILE_SIZE})"
echo -e "  2. Compressed:      echo_production_${TIMESTAMP}.sql.gz (${COMPRESSED_SIZE})"
echo -e "  3. Instructions:    README_FOR_IT.txt"

echo -e "\n${GREEN}Next Steps:${NC}"
echo -e "  1. Review the exported data to ensure completeness"
echo -e "  2. Share the ${GREEN}${OUTPUT_DIR}${NC} folder with your IT team"
echo -e "  3. IT team can restore directly to AWS RDS"

echo -e "\n${BLUE}Tip:${NC} Use the .gz file for faster transfer over network/email"
echo ""
