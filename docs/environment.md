# Development environment

Everything needed to run, change and deploy ECHO from a fresh machine.

`python scripts/echo.py preflight` checks all of it and prints the fix for
anything missing — run that first, and after each step below, rather than
working through this by eye.

---

## Versions

These are the versions the code was written and tested against. Where a manifest
pins exactly, install exactly.

| | Version | Why it matters |
|---|---|---|
| Python | **3.9+** | The backend image is `python:3.9-slim`. Code must stay 3.9-compatible. |
| Node.js | **20.x** | The frontend is built with Node 20. |
| pnpm | **10.12.1** | Declared as `packageManager` in the root `package.json`. |
| PostgreSQL client | **16+** | Production RDS runs Postgres 16. `pg_dump` refuses to dump a *newer* server than itself, so a 15 client cannot dump production. |
| PostgreSQL (local) | 15 via Docker | `docker-compose.yml` runs `postgis/postgis:15-3.3` on port **5433**. |
| Docker | any current | Runs local Postgres, and builds the backend image. |
| AWS CLI | v2 | Every deploy and data-sync command. |

> The version split is deliberate and catches people out: your **local database**
> is Postgres 15, but your **client tools** must be 16+ to talk to production.
> Install the 16 client; it connects to 15 servers fine. The reverse is not true.

## System tools

| Tool | macOS | Windows | Linux |
|---|---|---|---|
| Docker | [Docker Desktop](https://docs.docker.com/get-docker/) | Docker Desktop | `apt install docker.io` |
| AWS CLI | `brew install awscli` | [MSI installer](https://aws.amazon.com/cli/), then reopen your terminal | `apt install awscli` |
| `psql` / `pg_dump` | `brew install postgresql@16` | [PostgreSQL installer](https://www.postgresql.org/download/windows/) — tick "Command Line Tools", then add its `bin\` folder to PATH | `apt install postgresql-client-16` |
| Node + pnpm | `brew install node` then `npm i -g pnpm` | [Node installer](https://nodejs.org/), then `npm i -g pnpm` | `apt install nodejs npm` then `npm i -g pnpm` |

**Windows:** use PowerShell, not Git Bash — the AWS CLI and Docker behave better
there. Everything in `scripts/echo.py` is pure Python and works the same on all
three platforms. After installing anything that changes PATH, open a new
terminal before re-running `preflight`.

## Python packages

Three separate sets, installed independently. Each has its own virtualenv.

### `packages/etl/requirements.txt` — ETL scripts *and* `scripts/echo.py`

```bash
cd packages/etl
python -m venv .venv
source .venv/bin/activate          # Windows: .venv\Scripts\activate
pip install -r requirements.txt
```

Exactly pinned, so a fresh install matches what these scripts were tested
against. Includes `shapely` and `fiona`, which the geometry loaders and the
shapefile converter import directly — they used to arrive only as `geopandas`
transitive dependencies, which would have broken silently if geopandas ever
dropped them.

`scripts/echo.py` needs nothing extra. It is standard library apart from
`sqlalchemy` and `python-dotenv`, both in this file.

### `apps/backend/requirements.txt` — the API

```bash
cd apps/backend
python -m venv .venv
source .venv/bin/activate          # Windows: .venv\Scripts\activate
pip install -r requirements.txt
```

**This file defines the production runtime** — the Dockerfile installs exactly
it. Changing a pin here changes what gets deployed on the next
`deploy-backend`, so treat edits as a production change and deploy deliberately.

`pydantic` is declared as a range rather than a pin because FastAPI resolves it
too, and pinning it here would change what the image builds with.

### Frontend

```bash
cd apps/frontend
pnpm install
```

Locked by `pnpm-lock.yaml`. Use `pnpm`, not `npm` or `yarn` — mixing lockfiles
produces a different dependency tree than the one that has been deployed.

Node's version is documented here rather than declared as `engines` in
`package.json`, so that a slightly different Node does not hard-fail an install.

## Setting up from scratch

```bash
git clone https://github.com/jordanabb/echo.git
cd echo

cp .env.example .env                 # database connection — starts local
cp .env.deploy.example .env.deploy   # AWS resource names — fill these in

cd packages/etl && python -m venv .venv && source .venv/bin/activate \
  && pip install -r requirements.txt && cd ../..
cd apps/backend && python -m venv .venv && source .venv/bin/activate \
  && pip install -r requirements.txt && cd ../..
cd apps/frontend && pnpm install && cd ../..

docker-compose up -d                 # local Postgres on port 5433

python scripts/echo.py preflight     # confirms all of the above
```

Then get real data onto the machine:

```bash
python scripts/echo.py login
python scripts/echo.py pull-data
python scripts/echo.py restore-local
```

## Configuration files

All git-ignored. This repository is **public** — never commit credentials.

| File | Holds | Template |
|---|---|---|
| `.env` (repo root) | Database connection for the backend and ETL. **Decides whether the ETL writes to your laptop or to production.** | `.env.example` |
| `.env.deploy` (repo root) | AWS resource identifiers used by `scripts/echo.py` | `.env.deploy.example` |
| `apps/frontend/.env` | `PUBLIC_API_URL`, `PUBLIC_MAPBOX_TOKEN` | `apps/frontend/.env.example` |
| `apps/backend/.env` | Local backend database URL | `apps/backend/.env.example` |

Production values are **not** in any of these — they are set as environment
variables on the App Runner service. See
[aws-infrastructure.md](aws-infrastructure.md).

## Troubleshooting

**`pg_dump: server version 16, pg_dump version 15`** — your client is older than
production. Install the 16 client and put it first on PATH.

**`ModuleNotFoundError` running an ETL script** — the wrong virtualenv is
active, or none is. Each component has its own; activate the one in
`packages/etl/`.

**A stale `packages/etl/.venv`** — if it exists but has no packages in it,
delete the directory and recreate it with the commands above.

**`preflight` says Docker is installed but not running** — start Docker Desktop
and wait for it to finish starting before re-running.

**Anything AWS returning "explicit deny"** — this account denies almost every
call without a recent MFA token. Run `python scripts/echo.py login`.
