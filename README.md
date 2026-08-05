# ECHO Dashboard

An interactive dashboard of community indicators across US counties, census tracts,
school districts, congressional districts and state legislative districts.

Live at **https://echodashboard.org**

## What's here

| Path | What it is |
|---|---|
| [`apps/frontend/`](apps/frontend/) | SvelteKit single-page app, built to static files |
| [`apps/backend/`](apps/backend/) | FastAPI service that queries Postgres and serves the API |
| [`packages/etl/`](packages/etl/) | Python scripts that turn source CSVs and shapefiles into database rows |
| [`scripts/echo.py`](scripts/echo.py) | Operations tool — setup, data movement, deploys |
| [`docs/`](docs/) | How the deployed system works and how to change it |

## How it runs in production

```
Browser -> CloudFront -> S3            (the frontend, static files)
                      -> App Runner    (the backend, a Docker container)
                             -> RDS Postgres
```

No servers to manage; every piece is an AWS managed service. Details in
[docs/aws-infrastructure.md](docs/aws-infrastructure.md), and the reasoning behind
each choice in [docs/aws-rationale.md](docs/aws-rationale.md).

## Where to start

**Adding or updating data** — [docs/adding-a-dataset.md](docs/adding-a-dataset.md).
Read this before touching anything. Loading rows into the database is not enough on
its own to make data appear in the dashboard.

**Running it locally** — [QUICK_START.md](QUICK_START.md).

**Setting up a new machine** — [docs/environment.md](docs/environment.md) lists every
tool and package version, with install commands per platform. The short version:

```bash
cp .env.example .env
cp .env.deploy.example .env.deploy    # fill in from docs/aws-infrastructure.md
python scripts/echo.py preflight      # tells you what is still missing
```

## The operations tool

```bash
python scripts/echo.py --help
```

| Command | |
|---|---|
| `preflight` | Check this machine is set up. Changes nothing. |
| `login` | Start a 12-hour AWS session with your MFA code. |
| `pull-data` / `push-data` | Move ETL source data and dumps between S3 and here. |
| `dump-db` | Copy a database to a `.sql.gz` file. Never writes to a database. |
| `restore-local` | Load a dump into local Postgres. Refuses non-local targets. |
| `verify` | Run the data-quality checks against local or production. |
| `snapshot-db` | RDS snapshot before a production change. The undo button. |
| `check-indicators` | Find data the dashboard cannot see, and years it cannot select. |
| `sync-indicators` | Fix the above by updating `indicator_config.py`. |
| `deploy-backend` | Build, push, and roll out the API. |
| `deploy-frontend` | Build the SPA, upload it, and clear the CDN cache. |

These wrap the same `aws`, `docker` and `psql` commands you would type by hand;
[docs/adding-a-dataset.md](docs/adding-a-dataset.md) lists the raw equivalents so you
are never dependent on the wrapper.

## Things worth knowing

- **There is no staging environment.** Both tiers deploy by overwriting what is live.
  Take a snapshot before production data changes.
- **Nothing deploys from git.** Pushing to a branch does not release anything; a
  deploy only happens when someone runs a deploy command.
- **The indicator list is hardcoded** in `apps/backend/indicator_config.py`, and is
  compiled into the running backend. Data without an entry there is invisible, and
  updating it requires a backend deploy.
- **Secrets are not in this repository.** `.env` and `.env.deploy` are git-ignored,
  and this repo is public — keep credentials out of it.
