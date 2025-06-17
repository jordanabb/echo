#!/usr/bin/env python3
"""
Database migration script to add state_fips column for optimized state filtering.
This script adds the state_fips column to the geographies table and populates it
from the existing geo_id data.
"""

import os
import sys
from sqlalchemy import create_engine, text
from dotenv import load_dotenv

# Load environment variables
load_dotenv()

def main():
    """Add state_fips column and populate it for performance optimization."""
    
    # Get database URL
    database_url = os.getenv("DATABASE_URL")
    if not database_url:
        print("ERROR: DATABASE_URL environment variable not set")
        sys.exit(1)
    
    # Create database engine
    engine = create_engine(database_url)
    
    print("🚀 Starting state_fips column migration...")
    
    try:
        with engine.connect() as conn:
            # Start a transaction
            trans = conn.begin()
            
            try:
                # Check if column already exists
                check_column_query = text("""
                    SELECT column_name 
                    FROM information_schema.columns 
                    WHERE table_name = 'geographies' 
                    AND column_name = 'state_fips'
                """)
                
                result = conn.execute(check_column_query).fetchone()
                
                if result:
                    print("✅ state_fips column already exists, skipping creation")
                else:
                    print("📝 Adding state_fips column...")
                    
                    # Add the state_fips column
                    add_column_query = text("""
                        ALTER TABLE geographies 
                        ADD COLUMN state_fips VARCHAR(2)
                    """)
                    conn.execute(add_column_query)
                    print("✅ state_fips column added successfully")
                
                # Populate the state_fips column from geo_id
                print("📊 Populating state_fips column from geo_id...")
                
                update_query = text("""
                    UPDATE geographies 
                    SET state_fips = LEFT(geo_id, 2)
                    WHERE state_fips IS NULL OR state_fips = ''
                """)
                
                result = conn.execute(update_query)
                rows_updated = result.rowcount
                print(f"✅ Updated {rows_updated} rows with state_fips values")
                
                # Create index for fast lookups
                print("🔍 Creating index on state_fips column...")
                
                # Check if index already exists
                check_index_query = text("""
                    SELECT indexname 
                    FROM pg_indexes 
                    WHERE tablename = 'geographies' 
                    AND indexname = 'idx_geographies_state_fips'
                """)
                
                index_result = conn.execute(check_index_query).fetchone()
                
                if index_result:
                    print("✅ Index on state_fips already exists")
                else:
                    create_index_query = text("""
                        CREATE INDEX idx_geographies_state_fips 
                        ON geographies(state_fips)
                    """)
                    conn.execute(create_index_query)
                    print("✅ Index created successfully")
                
                # Create composite index for optimal performance
                print("🔍 Creating composite index for geo_level + state_fips...")
                
                check_composite_index_query = text("""
                    SELECT indexname 
                    FROM pg_indexes 
                    WHERE tablename = 'geographies' 
                    AND indexname = 'idx_geographies_geo_level_state_fips'
                """)
                
                composite_index_result = conn.execute(check_composite_index_query).fetchone()
                
                if composite_index_result:
                    print("✅ Composite index already exists")
                else:
                    create_composite_index_query = text("""
                        CREATE INDEX idx_geographies_geo_level_state_fips 
                        ON geographies(geo_level, state_fips, year)
                    """)
                    conn.execute(create_composite_index_query)
                    print("✅ Composite index created successfully")
                
                # Verify the migration
                print("🔍 Verifying migration...")
                
                verify_query = text("""
                    SELECT 
                        COUNT(*) as total_rows,
                        COUNT(state_fips) as rows_with_state_fips,
                        COUNT(DISTINCT state_fips) as unique_states
                    FROM geographies
                """)
                
                verification = conn.execute(verify_query).fetchone()
                
                print(f"📊 Migration verification:")
                print(f"   Total rows: {verification.total_rows}")
                print(f"   Rows with state_fips: {verification.rows_with_state_fips}")
                print(f"   Unique states: {verification.unique_states}")
                
                if verification.total_rows == verification.rows_with_state_fips:
                    print("✅ All rows have state_fips values")
                else:
                    print("⚠️  Some rows are missing state_fips values")
                
                # Show sample data
                sample_query = text("""
                    SELECT geo_id, geo_name, geo_level, state_fips
                    FROM geographies 
                    WHERE state_fips IS NOT NULL
                    LIMIT 5
                """)
                
                sample_results = conn.execute(sample_query).fetchall()
                print("\n📋 Sample data:")
                for row in sample_results:
                    print(f"   {row.geo_id} | {row.geo_name} | {row.geo_level} | {row.state_fips}")
                
                # Commit the transaction
                trans.commit()
                print("\n🎉 Migration completed successfully!")
                
            except Exception as e:
                trans.rollback()
                print(f"❌ Error during migration: {e}")
                raise
                
    except Exception as e:
        print(f"❌ Failed to connect to database: {e}")
        sys.exit(1)

if __name__ == "__main__":
    main()
