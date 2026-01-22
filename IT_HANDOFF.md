# IT Team Handoff - AWS Deployment

## Overview
This document provides everything your IT team needs to deploy the ECHO Data Dashboard to AWS.

## 🎯 Streamlined Workflow

**Good News:** You won't need to run ETL scripts or load data!

The developer will provide you with a **production-ready database export** that you simply restore to AWS RDS. This approach:
- ✅ No Python/ETL environment needed
- ✅ Faster deployment
- ✅ Pre-verified data quality
- ✅ Simpler infrastructure

**What you'll receive:**
- SQL database dump file (ready to restore)
- This documentation
- Dockerfiles for frontend/backend

## Repository Access
**GitHub Repository:** https://github.com/jordanabb/echo
**Deployment Branch:** `feat/aws-deployment-prep`

The IT team should:
```bash
git clone https://github.com/jordanabb/echo.git
cd echo
git checkout feat/aws-deployment-prep
```

## Key Documentation Files
Your IT team should review these files in order:

1. **[DEPLOYMENT.md](DEPLOYMENT.md)** - Complete AWS deployment guide
   - Step-by-step instructions for AWS setup
   - Architecture diagram and service requirements
   - Security best practices

2. **[QUICK_START.md](QUICK_START.md)** - Testing deployment locally
   - How to test Docker containers before AWS deployment

3. **[.env.production.example](.env.production.example)** - Required environment variables

## Application Architecture

### Tech Stack
- **Frontend:** SvelteKit (Node.js)
- **Backend:** FastAPI (Python 3.9)
- **Database:** PostgreSQL 15 with PostGIS extension

### Container Images
- Backend: [apps/backend/Dockerfile](apps/backend/Dockerfile)
- Frontend: [apps/frontend/Dockerfile](apps/frontend/Dockerfile)

### Ports
- Frontend: 3000
- Backend: 8000
- Database: 5432

## What IT Needs to Provide Back to You

After deployment, the IT team should provide:

### 1. Database Connection Information
- [ ] RDS endpoint hostname
- [ ] Database name
- [ ] Database username
- [ ] Database password (or AWS Secrets Manager ARN)
- [ ] Port (typically 5432)

**Format:** `postgresql://[user]:[password]@[endpoint]:5432/echo_data`

### 2. Application URLs
- [ ] Production frontend URL (e.g., https://echo.yourdomain.com)
- [ ] Production backend API URL (e.g., https://api.echo.yourdomain.com)
- [ ] API documentation URL (typically https://api.echo.yourdomain.com/docs)

### 3. AWS Resource Information
- [ ] ECR repository URLs (for future image updates)
- [ ] ECS cluster name
- [ ] ECS service names (frontend & backend)
- [ ] Load balancer DNS name
- [ ] AWS region being used

### 4. Access Credentials (if applicable)
- [ ] AWS Console access for monitoring
- [ ] CloudWatch log group names
- [ ] Any VPN/bastion info for database access

## Database Initialization

### Streamlined Approach (Recommended)

The developer will provide you with a complete database export file:

**File you'll receive:** `echo_production_YYYYMMDD_HHMMSS.sql.gz` (or .sql)

**Steps to restore:**

1. **Create RDS PostgreSQL instance** (see AWS Architecture section)

2. **Enable PostGIS extension:**
   ```sql
   CREATE EXTENSION IF NOT EXISTS postgis;
   CREATE EXTENSION IF NOT EXISTS postgis_topology;
   ```

3. **Create database:**
   ```sql
   CREATE DATABASE echo_data;
   ```

4. **Restore the database dump:**
   ```bash
   # If using compressed file
   gunzip -c echo_production_YYYYMMDD_HHMMSS.sql.gz | \
   psql -h [RDS-ENDPOINT] -U postgres -d echo_data

   # Or if using uncompressed
   psql -h [RDS-ENDPOINT] -U postgres -d echo_data \
        -f echo_production_YYYYMMDD_HHMMSS.sql
   ```

5. **Verify restore:**
   ```sql
   SELECT COUNT(*) FROM geographies;
   SELECT COUNT(*) FROM results_data;
   ```

**That's it!** No ETL scripts to run. The database dump includes:
- Complete schema with spatial indices
- All geographic boundaries
- All indicator data
- Proper constraints and relationships

### Alternative: Manual Schema + ETL (Not Recommended)

If for some reason you need to set up from scratch:
- Schema: [packages/etl/schema.sql](packages/etl/schema.sql)
- ETL scripts in `packages/etl/`
- Contact developer for assistance

## Environment Variables the IT Team Must Configure

From [.env.production.example](.env.production.example):

### Backend
```env
DATABASE_URL=postgresql://[credentials]@[rds-endpoint]:5432/echo_data
CORS_ORIGINS=https://yourdomain.com
PORT=8000
ENVIRONMENT=production
```

### Frontend
```env
PUBLIC_API_URL=https://api.yourdomain.com
NODE_ENV=production
```

## Security Requirements

Ensure IT team follows these security practices:

- [ ] Database is NOT publicly accessible
- [ ] All traffic uses HTTPS (SSL/TLS certificates)
- [ ] Database credentials stored in AWS Secrets Manager
- [ ] Security groups configured with least privilege
- [ ] RDS encryption at rest enabled
- [ ] CloudWatch logging enabled

## Estimated AWS Costs

Share with your IT team for budget planning:

**Minimal Setup (Development/Testing):**
- RDS db.t3.micro: ~$15-20/month
- ECS Fargate (2 tasks): ~$15-25/month
- ALB: ~$20-25/month
- Data transfer: ~$5-10/month
- **Total: ~$55-80/month**

**Production Setup:**
- RDS db.t3.small (Multi-AZ): ~$60-80/month
- ECS Fargate (4+ tasks): ~$40-60/month
- ALB: ~$25-30/month
- CloudFront CDN: ~$5-15/month
- Data transfer: ~$10-20/month
- **Total: ~$140-205/month**

## Testing Before Production

IT team can test the full stack locally with Docker:

```bash
# Create production environment file
cp .env.production.example .env.production
# Edit with test values

# Build and start all services
docker-compose -f docker-compose.prod.yml up --build
```

Access at:
- Frontend: http://localhost:3000
- Backend: http://localhost:8000
- Health check: http://localhost:8000/health

## Timeline & Next Steps

1. **IT Team Reviews Documentation** (1-2 days)
   - Read DEPLOYMENT.md
   - Test Docker locally
   - Identify any questions or concerns

2. **AWS Infrastructure Setup** (3-5 days)
   - Create RDS database
   - Set up ECS cluster and services
   - Configure load balancer and networking
   - Set up monitoring and logging

3. **Handback to You** (1 day)
   - Receive connection info
   - Load data via ETL scripts
   - Verify application works

4. **Go Live** (1 day)
   - Final testing
   - DNS cutover (if applicable)
   - Monitor for issues

## Support Contacts

**For application questions:**
- Repository issues: https://github.com/jordanabb/echo/issues
- Contact: [Your contact info]

**For AWS/infrastructure questions:**
- IT team will determine internal support process

## Additional Resources

- FastAPI documentation: https://fastapi.tiangolo.com/
- SvelteKit documentation: https://kit.svelte.dev/
- PostGIS documentation: https://postgis.net/
- AWS ECS documentation: https://docs.aws.amazon.com/ecs/

## Checklist for IT Team

Before starting deployment:
- [ ] Clone repository and checkout `feat/aws-deployment-prep` branch
- [ ] Review DEPLOYMENT.md completely
- [ ] Test Docker containers locally
- [ ] Confirm AWS account access and permissions
- [ ] Confirm budget approval
- [ ] Identify production domain name (if applicable)

During deployment:
- [ ] Create RDS PostgreSQL instance with PostGIS
- [ ] Create ECR repositories and push images
- [ ] Create ECS cluster and task definitions
- [ ] Configure load balancer and target groups
- [ ] Set up CloudWatch logging
- [ ] Configure security groups and networking
- [ ] Request/configure SSL certificates
- [ ] Initialize database schema

After deployment:
- [ ] Provide connection info back to developer
- [ ] Verify health checks passing
- [ ] Test application functionality
- [ ] Set up monitoring alerts
- [ ] Document any deviations from deployment guide
