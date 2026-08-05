# Quick Start Guide

Running ECHO on your own machine. For changing the deployed site, see
[docs/adding-a-dataset.md](docs/adding-a-dataset.md).

## Prerequisites

- Docker and Docker Compose
- Node.js 20 with pnpm 10
- Python 3.9+
- PostgreSQL client tools 16+ (`psql`, `pg_dump`)

`python scripts/echo.py preflight` checks all of these and tells you what is
missing. Full versions, install commands per platform, and which packages live
where: [docs/environment.md](docs/environment.md).

## Start the development environment

1. **Configure:**
   ```bash
   cp .env.example .env
   ```
   The defaults point at the local database below. Leave them alone unless you have a
   reason not to.

2. **Start PostgreSQL:**
   ```bash
   docker-compose up -d
   ```
   This runs PostGIS on port **5433** (not 5432, to avoid clashing with any Postgres
   already on your machine).

3. **Load some data.** The database starts empty. To work against real data, fetch a
   dump and restore it:
   ```bash
   python scripts/echo.py login
   python scripts/echo.py pull-data dumps
   python scripts/echo.py restore-local
   ```

4. **Start the backend:**
   ```bash
   cd apps/backend
   python -m venv .venv
   source .venv/bin/activate        # Windows: .venv\Scripts\activate
   pip install -r requirements.txt
   uvicorn main:app --reload --port 8000
   ```

5. **Start the frontend:**
   ```bash
   cd apps/frontend
   pnpm install
   pnpm run dev
   ```

6. **Open it:**
   - Frontend: http://localhost:5175
   - Backend API: http://localhost:8000
   - API docs: http://localhost:8000/docs

## Deploying

Not from here, and not from git — nothing deploys automatically. See
[docs/adding-a-dataset.md](docs/adding-a-dataset.md) for the full workflow, or in
short:

```bash
python scripts/echo.py deploy-backend
python scripts/echo.py deploy-frontend
```

## Project structure

```
echo/
├── apps/
│   ├── backend/               # FastAPI service
│   │   ├── main.py            # API endpoints
│   │   ├── indicator_config.py# which indicators the dashboard exposes
│   │   └── Dockerfile         # image deployed to App Runner
│   └── frontend/              # SvelteKit SPA, built to static files
├── packages/etl/              # data loading scripts
│   ├── db_target.py           # guards writes to production
│   └── load_*.py              # loaders
├── scripts/
│   ├── echo.py                # operations tool
│   └── verify_data.sql        # data-quality checks
├── docs/                      # infrastructure and dataset runbooks
└── docker-compose.yml         # local PostGIS
```

## Common tasks

**Reset the local database**
```bash
docker-compose down -v && docker-compose up -d
python scripts/echo.py restore-local
```

**Check the data**
```bash
python scripts/echo.py verify
python scripts/echo.py check-indicators
```

**Run tests**
```bash
cd apps/frontend && pnpm run test
cd apps/backend && pytest
```

**View database logs**
```bash
docker-compose logs -f postgres
```

## Environment variables

`.env` at the repo root — used by the backend and the ETL scripts:

- `DB_HOST` / `DB_PORT` / `DB_NAME` / `DB_USER` / `DB_PASSWORD` — which database.
  **This decides whether the ETL scripts write to your laptop or to production.**
- `DATABASE_URL` — the same thing as one string
- `CORS_ORIGINS` — which frontends the API accepts requests from

`.env.deploy` at the repo root — AWS resource names used by `scripts/echo.py`. Copy
it from `.env.deploy.example`.

`apps/frontend/.env`:

- `PUBLIC_API_URL` — which API the built frontend calls
- `PUBLIC_MAPBOX_TOKEN` — map tiles

Both `.env` files are git-ignored, and this repository is public. Keep credentials
out of anything you commit.
