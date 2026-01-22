# Streamlined Data Preparation Workflow

This workflow allows you to prepare all data locally and provide a clean, production-ready database export to your IT team. IT simply restores it to AWS RDS without running any ETL scripts.

## Overview

```
You (Local)                    IT Team (AWS)
───────────                    ─────────────
1. Load data with ETL    →
2. Verify data quality   →
3. Export database       →     4. Restore to RDS
                               5. Verify & deploy
```

## Your Workflow (Data Preparation)

### Step 1: Set Up Local Development Environment

```bash
# Start local PostgreSQL with PostGIS
docker-compose up -d

# Verify database is running
docker ps | grep echo_db
```

### Step 2: Load Your Data

```bash
# Navigate to ETL directory
cd packages/etl

# Activate Python virtual environment
python -m venv .venv
source .venv/bin/activate  # Windows: .venv\Scripts\activate
pip install -r requirements.txt

# Run your ETL scripts
python load_geometry_data.py
python load_data_to_db.py

# Or any custom data loading scripts you have
```

### Step 3: Verify Data Quality

Run the verification script to check your data:

```bash
# From project root
docker exec -i echo_db psql -U user -d echo_data < scripts/verify_data.sql
```

Review the output to ensure:
- [ ] All expected geographies are loaded
- [ ] All indicators have data
- [ ] No orphaned records
- [ ] Spatial data (geometries) are complete
- [ ] Value ranges look reasonable

### Step 4: Export Production Database

```bash
# From project root
./scripts/export_production_db.sh
```

This creates a `production_export/` folder with:
- **SQL dump file** - Full database export
- **Compressed version** (.gz) - Smaller for transfer
- **README for IT** - Restore instructions

**Output example:**
```
production_export/
├── echo_production_20260121_153045.sql      # 45MB
├── echo_production_20260121_153045.sql.gz   # 8MB
└── README_FOR_IT.txt                        # Instructions
```

### Step 5: Review Export

Optional but recommended - verify the export looks good:

```bash
# Check file size (should be reasonable)
ls -lh production_export/*.sql

# Quick preview of first/last lines
head -n 50 production_export/echo_production_*.sql
tail -n 50 production_export/echo_production_*.sql
```

### Step 6: Share with IT Team

**Option A: Direct File Share**
- Zip the `production_export/` folder
- Share via your organization's file sharing (SharePoint, Google Drive, etc.)

**Option B: Cloud Storage**
- Upload to S3 bucket
- Share bucket path with IT

**Option C: Secure Transfer**
- Use your organization's secure file transfer system

**Include in your handoff:**
- The `production_export/` folder
- Link to [IT_HANDOFF.md](IT_HANDOFF.md) in the GitHub repo
- Your contact info for questions

## IT Team Workflow (Simplified)

With this approach, IT's job is much simpler:

### 1. Create RDS Instance
- PostgreSQL 15
- Enable PostGIS extension
- Create `echo_data` database

### 2. Restore Database
```bash
# Unzip if needed
gunzip echo_production_YYYYMMDD_HHMMSS.sql.gz

# Restore to RDS
psql -h your-rds-endpoint.amazonaws.com \
     -U postgres \
     -d echo_data \
     -f echo_production_YYYYMMDD_HHMMSS.sql
```

### 3. Deploy Application
- Follow [DEPLOYMENT.md](DEPLOYMENT.md) for container deployment
- No ETL scripts to run!
- Just deploy frontend and backend containers

## Benefits of This Approach

✅ **Simpler for IT** - No Python/ETL environment needed
✅ **Faster deployment** - No data processing on AWS
✅ **Quality controlled** - You verify data before handoff
✅ **Repeatable** - Easy to create new exports as data updates
✅ **Testable** - IT can restore to staging environment first
✅ **Smaller attack surface** - No ETL dependencies in production

## When to Re-Export

You'll need to create a new export when:

1. **Data updates** - New indicators, geographies, or years added
2. **Data corrections** - Fixing errors in existing data
3. **Schema changes** - Database structure modifications
4. **Testing** - Creating staging/test environments

## Updating Production Data Later

When you need to update production data:

### Option 1: Full Re-Export (Recommended for major updates)
1. Update data locally
2. Run export script again
3. IT restores fresh to RDS (backing up old first)

### Option 2: Incremental Updates (For small changes)
1. Create SQL update scripts
2. Test locally
3. IT runs update scripts on RDS

For incremental updates, create targeted SQL like:
```sql
-- Example: Add new indicator data
INSERT INTO results_data (geo_id, geo_level, year, indicator_id, value)
VALUES (...);

-- Example: Update existing values
UPDATE results_data
SET value = new_value
WHERE indicator_id = 'XXX' AND year = 2024;
```

## Troubleshooting

### Export script fails
**Problem:** Docker container not running
**Solution:** `docker-compose up -d`

**Problem:** Permission denied
**Solution:** `chmod +x scripts/export_production_db.sh`

### Export file is unexpectedly small
**Problem:** Data not fully loaded
**Solution:** Run verification script, check ETL logs

### IT can't restore to RDS
**Problem:** PostGIS not enabled
**Solution:** They need to run `CREATE EXTENSION postgis;` first

**Problem:** Authentication error
**Solution:** Check RDS security groups and credentials

## Scripts Reference

### Export Script
**Location:** [scripts/export_production_db.sh](scripts/export_production_db.sh)
**Purpose:** Create production-ready database dump
**Usage:** `./scripts/export_production_db.sh`

### Verification Script
**Location:** [scripts/verify_data.sql](scripts/verify_data.sql)
**Purpose:** Check data quality before export
**Usage:** `docker exec -i echo_db psql -U user -d echo_data < scripts/verify_data.sql`

## Best Practices

1. **Always verify before export** - Run verification script
2. **Use compressed files** - The .gz version for transfers
3. **Keep export history** - Don't delete old exports immediately
4. **Document changes** - Note what changed between exports
5. **Test restores** - IT should restore to staging first
6. **Backup before updates** - IT should snapshot RDS before new exports

## Next Steps

1. Load your data using ETL scripts
2. Verify data quality
3. Run export script
4. Share with IT team
5. IT restores and deploys application

Your data preparation is completely independent of AWS deployment!
