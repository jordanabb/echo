# AWS Deployment Guide

This guide covers deploying the ECHO Data Dashboard to AWS.

## Table of Contents
1. [Prerequisites](#prerequisites)
2. [Environment Setup](#environment-setup)
3. [AWS Architecture Overview](#aws-architecture-overview)
4. [Deployment Steps](#deployment-steps)
5. [Database Setup](#database-setup)
6. [Monitoring & Maintenance](#monitoring--maintenance)

## Prerequisites

- AWS Account with appropriate permissions
- Docker installed locally
- AWS CLI configured
- Domain name (optional but recommended)

## Environment Setup

### 1. Environment Variables

Copy the environment templates and fill in production values:

```bash
# Root environment
cp .env.production.example .env.production

# Frontend environment
cp apps/frontend/.env.example apps/frontend/.env.production

# Backend environment
cp apps/backend/.env.example apps/backend/.env.production
```

**Critical Environment Variables:**

- `DATABASE_URL`: Your AWS RDS PostgreSQL connection string
- `CORS_ORIGINS`: Your production domain(s)
- `PUBLIC_API_URL`: Your production backend API URL
- `DB_PASSWORD`: Strong password for database (use AWS Secrets Manager)

### 2. Install Dependencies

```bash
# Frontend
cd apps/frontend
pnpm install
pnpm add -D @sveltejs/adapter-node

# Backend
cd ../backend
python -m venv .venv
source .venv/bin/activate  # On Windows: .venv\Scripts\activate
pip install -r requirements.txt
```

## AWS Architecture Overview

### Recommended Architecture

```
Internet
    ↓
CloudFront (CDN) + Route 53 (DNS)
    ↓
Application Load Balancer (ALB)
    ↓
    ├─→ ECS Fargate: Frontend (Port 3000)
    └─→ ECS Fargate: Backend (Port 8000)
            ↓
    RDS PostgreSQL with PostGIS
```

### AWS Services Required

1. **Amazon RDS** - PostgreSQL 15 with PostGIS extension
2. **Amazon ECS Fargate** - Container orchestration for frontend & backend
3. **Application Load Balancer** - Route traffic to containers
4. **Amazon ECR** - Store Docker images
5. **AWS Secrets Manager** - Secure credential storage
6. **CloudWatch** - Logging and monitoring
7. **Route 53** - DNS management
8. **Certificate Manager** - SSL/TLS certificates

## Deployment Steps

### Step 1: Create RDS PostgreSQL Database

1. **Create RDS Instance:**
   - Engine: PostgreSQL 15
   - Instance class: db.t3.micro (start small, scale up)
   - Storage: 20 GB SSD (auto-scaling enabled)
   - Enable Multi-AZ for production
   - Set master password in AWS Secrets Manager

2. **Enable PostGIS Extension:**
   ```sql
   CREATE EXTENSION postgis;
   CREATE EXTENSION postgis_topology;
   ```

3. **Initialize Schema:**
   ```bash
   psql -h your-rds-endpoint.region.rds.amazonaws.com \
        -U postgres -d echo_data \
        -f packages/etl/schema.sql
   ```

4. **Security Group Configuration:**
   - Inbound: PostgreSQL (5432) from backend security group only
   - No public access

### Step 2: Build and Push Docker Images

1. **Create ECR Repositories:**
   ```bash
   aws ecr create-repository --repository-name echo-backend
   aws ecr create-repository --repository-name echo-frontend
   ```

2. **Login to ECR:**
   ```bash
   aws ecr get-login-password --region us-east-1 | \
   docker login --username AWS --password-stdin \
   <account-id>.dkr.ecr.us-east-1.amazonaws.com
   ```

3. **Build and Push Backend:**
   ```bash
   cd apps/backend
   docker build -t echo-backend .
   docker tag echo-backend:latest \
     <account-id>.dkr.ecr.us-east-1.amazonaws.com/echo-backend:latest
   docker push <account-id>.dkr.ecr.us-east-1.amazonaws.com/echo-backend:latest
   ```

4. **Build and Push Frontend:**
   ```bash
   cd apps/frontend
   docker build -t echo-frontend .
   docker tag echo-frontend:latest \
     <account-id>.dkr.ecr.us-east-1.amazonaws.com/echo-frontend:latest
   docker push <account-id>.dkr.ecr.us-east-1.amazonaws.com/echo-frontend:latest
   ```

### Step 3: Create ECS Cluster and Services

1. **Create ECS Cluster:**
   ```bash
   aws ecs create-cluster --cluster-name echo-production
   ```

2. **Create Task Definitions** (use AWS Console or Infrastructure as Code)

   **Backend Task Definition:**
   - Image: ECR backend image
   - CPU: 512, Memory: 1024
   - Environment Variables from Secrets Manager
   - Port Mapping: 8000
   - Health Check: `/health` endpoint

   **Frontend Task Definition:**
   - Image: ECR frontend image
   - CPU: 256, Memory: 512
   - Environment Variables
   - Port Mapping: 3000

3. **Create ECS Services:**
   - Desired count: 2 (for redundancy)
   - Load balancer attached
   - Auto-scaling enabled

### Step 4: Configure Application Load Balancer

1. **Create Target Groups:**
   - Backend: Port 8000, Health check: `/health`
   - Frontend: Port 3000, Health check: `/`

2. **Create ALB:**
   - Scheme: Internet-facing
   - Listeners: HTTP (80), HTTPS (443)

3. **Configure Listener Rules:**
   - `/api/*` → Backend target group
   - `/*` → Frontend target group

### Step 5: Configure DNS and SSL

1. **Request SSL Certificate** (AWS Certificate Manager)
   - Domain: yourdomain.com
   - Validation: DNS or Email

2. **Configure Route 53:**
   - Create A record pointing to ALB
   - Create CNAME for www subdomain

### Step 6: Load Data (ETL)

1. **Connect to Backend Container:**
   ```bash
   aws ecs execute-command --cluster echo-production \
     --task <task-id> --container backend --interactive --command /bin/bash
   ```

2. **Run ETL Scripts:**
   ```bash
   python /path/to/etl/load_data_to_db.py
   python /path/to/etl/load_geometry_data.py
   ```

   Or use a temporary EC2 instance in the same VPC.

## Database Setup

### Initial Schema

The schema is automatically applied via [packages/etl/schema.sql](packages/etl/schema.sql:1):

- `geographies` table: Stores geographic boundaries with PostGIS geometries
- `results_data` table: Stores indicator values for each geography
- Composite primary keys handle multiple years of data
- Spatial indices for fast map queries

### Backup Strategy

1. **Enable Automated Backups:**
   - Retention: 7-30 days
   - Backup window: Low-traffic period

2. **Manual Snapshots:**
   - Before major data loads
   - Before schema changes

## Monitoring & Maintenance

### CloudWatch Dashboards

Monitor these metrics:
- ECS CPU and Memory utilization
- RDS connections and query performance
- ALB request count and latency
- Target health status

### Logging

- Application logs → CloudWatch Logs
- Access logs → S3 bucket
- Error tracking → Consider Sentry integration

### Health Checks

- Backend: `GET /health` (port 8000)
- Frontend: `GET /` (port 3000)
- Database: Connection test in health endpoint

### Scaling

1. **Auto-scaling ECS Services:**
   - Target CPU: 70%
   - Min tasks: 2
   - Max tasks: 10

2. **RDS Scaling:**
   - Start with db.t3.micro
   - Monitor and upgrade as needed
   - Enable storage auto-scaling

## Cost Optimization

- Use AWS Free Tier where applicable
- Start with smallest instance sizes
- Enable auto-scaling to handle traffic spikes
- Set up billing alerts
- Consider Reserved Instances for production

## Security Checklist

- [ ] Database not publicly accessible
- [ ] All traffic uses HTTPS
- [ ] Secrets stored in AWS Secrets Manager
- [ ] Security groups configured with least privilege
- [ ] IAM roles follow least privilege principle
- [ ] Enable RDS encryption at rest
- [ ] Enable CloudWatch logs for audit trail

## Troubleshooting

### Common Issues

1. **Container won't start:**
   - Check CloudWatch logs
   - Verify environment variables
   - Test Docker image locally

2. **Database connection fails:**
   - Verify security group rules
   - Check DATABASE_URL format
   - Confirm PostGIS extension installed

3. **CORS errors:**
   - Update CORS_ORIGINS environment variable
   - Verify frontend PUBLIC_API_URL

4. **502 Bad Gateway:**
   - Check target health in ALB
   - Verify backend health check endpoint
   - Review backend logs

## Alternative Deployment Options

### AWS App Runner
Simpler alternative to ECS:
- Automatic load balancing and scaling
- Less configuration required
- Good for getting started quickly

### AWS Amplify (Frontend Only)
For static frontend deployment:
- Automatic builds from Git
- Built-in CDN
- Backend would need separate hosting

## Next Steps After Deployment

1. Set up monitoring and alerts
2. Configure automated backups
3. Implement CI/CD pipeline
4. Load test the application
5. Create runbook for common operations
6. Document incident response procedures

## Support

For deployment assistance, contact your AWS support team or Solutions Architect.
