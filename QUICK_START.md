# Quick Start Guide

## Local Development

### Prerequisites
- Docker and Docker Compose
- Node.js 20+ with pnpm
- Python 3.9+

### Start Development Environment

1. **Start PostgreSQL:**
   ```bash
   docker-compose up -d
   ```

2. **Start Backend:**
   ```bash
   cd apps/backend
   python -m venv .venv
   source .venv/bin/activate  # Windows: .venv\Scripts\activate
   pip install -r requirements.txt
   uvicorn main:app --reload --port 8000
   ```

3. **Start Frontend:**
   ```bash
   cd apps/frontend
   pnpm install
   pnpm run dev
   ```

4. **Access Application:**
   - Frontend: http://localhost:5175
   - Backend API: http://localhost:8000
   - API Docs: http://localhost:8000/docs

## Production Deployment

### Using Docker Compose

1. **Configure Environment:**
   ```bash
   cp .env.production.example .env.production
   # Edit .env.production with your values
   ```

2. **Build and Start:**
   ```bash
   docker-compose -f docker-compose.prod.yml up -d
   ```

3. **Load Data:**
   ```bash
   docker exec -it echo_backend_prod python /app/../etl/load_data_to_db.py
   ```

### AWS Deployment

See [DEPLOYMENT.md](DEPLOYMENT.md) for detailed AWS deployment instructions.

## Project Structure

```
echo/
├── apps/
│   ├── backend/          # FastAPI backend
│   │   ├── main.py       # Main API application
│   │   ├── models.py     # Database models
│   │   ├── schemas.py    # Pydantic schemas
│   │   └── Dockerfile    # Production Dockerfile
│   └── frontend/         # SvelteKit frontend
│       ├── src/          # Source code
│       └── Dockerfile    # Production Dockerfile
├── packages/
│   └── etl/              # Data loading scripts
│       ├── schema.sql    # Database schema
│       └── load_*.py     # ETL scripts
├── docker-compose.yml         # Development
├── docker-compose.prod.yml    # Production
└── .env.production.example    # Environment template
```

## Common Tasks

### Reset Database
```bash
docker-compose down -v
docker-compose up -d
```

### Run Tests
```bash
# Frontend
cd apps/frontend
pnpm run test

# Backend
cd apps/backend
pytest
```

### View Logs
```bash
# Development
docker-compose logs -f postgres

# Production
docker-compose -f docker-compose.prod.yml logs -f
```

## Environment Variables

### Backend ([apps/backend/.env.example](apps/backend/.env.example:1))
- `DATABASE_URL` - PostgreSQL connection string
- `CORS_ORIGINS` - Allowed frontend origins

### Frontend ([apps/frontend/.env.example](apps/frontend/.env.example:1))
- `PUBLIC_API_URL` - Backend API endpoint

See `.env.production.example` for production configuration.
