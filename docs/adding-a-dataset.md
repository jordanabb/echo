# Adding or updating a dataset

How new data gets into the ECHO dashboard. Written for someone who has not used
AWS before. Follow it top to bottom the first time.

Every command below is `python scripts/echo.py <something>`. Each one prints what
it is about to do and which database it is pointed at, and asks before changing
anything in production. The raw commands each step runs are listed too, so you can
always do it by hand.

---

## The one thing to understand first

**Loading data into the database is not enough to make it appear.**

The backend has a hardcoded list of indicators in
[`apps/backend/indicator_config.py`](../apps/backend/indicator_config.py). The API
builds its indicator list from that file, so anything in the database without an
entry there is invisible in the dashboard — no error, no empty chart, nothing.

That list also declares which years each indicator has. Adding 2024 data to an
indicator that only lists years up to 2023 loads fine and stays unselectable.

So a dataset change is **four** things, not one:

1. Rows into the database
2. An entry (or a year) in `indicator_config.py`
3. A backend deploy, because that file is compiled into the running service
4. Verification

`check-indicators` and `sync-indicators` exist to make step 2 impossible to forget.

---

## What counts as what

**Not a schema change** — these are just rows, and are the normal case:

- a new indicator
- a new year of an existing indicator
- new geographies, or even a whole new geography level

`results_data` is long format — `(geo_id, geo_level, year, indicator_id, value)`.
Indicators are *rows*, not columns. Your source CSVs are wide (`hs_edu`, `college`
as columns); the ETL melts them into rows. **A new column in a source CSV becomes
new rows, not a new database column.**

**A real schema change** — rare, and not covered here: a new attribute for every
observation (a margin-of-error alongside `value`), or changing a column's type.
Talk to whoever maintains the backend first.

## Three ways to load data — pick the right one

| | When | How |
|---|---|---|
| **Upsert** | Adding new rows, or correcting values | Run the loader with a CSV of just the new/changed rows |
| **Surgical replace** | Replacing an indicator whose new version covers *fewer* rows | `packages/etl/swap_indicator.py` |
| **Full rebuild** | Schema changes only | Not part of a normal update |

**Upsert is the default.** `load_data_to_db.py` inserts with
`ON CONFLICT (geo_id, geo_level, year, indicator_id) DO UPDATE`, so matching rows
are updated, new rows are added, and **everything else is left alone**. A new year
for one indicator is a few thousand rows — you do not reload 2.5 GB.

**The trap:** upsert can add and change, but never *remove*. If a revised vintage
covers fewer geographies than the one it replaces, the old rows stay behind and the
dashboard shows a mix of both. When data is being *replaced* rather than extended,
use `swap_indicator.py` — it deletes the indicator's rows and reinserts them in a
single transaction.

**Order matters:** `geographies` rows must exist before the `results_data` rows that
reference them. Load boundaries first.

---

## First-time setup

Do this once on a new machine.

```bash
python scripts/echo.py preflight
```

It checks Docker, Python packages, `psql`, AWS access and your config files, and
prints the fix for anything missing. Change nothing else until it passes.

You will need two config files, both git-ignored:

```bash
cp .env.example .env                 # database connection (starts local)
cp .env.deploy.example .env.deploy   # AWS resource names
```

Fill in `.env.deploy` from `docs/aws-infrastructure.md` or from whoever administers
the AWS account.

Then sign in and fetch the shared data:

```bash
python scripts/echo.py login          # prompts for your MFA code, lasts 12 hours
python scripts/echo.py pull-data      # several GB — grab a coffee
```

> `login` has to be re-run once a day, and in each new terminal only if the session
> has expired. Everything else refuses to run without it and tells you so.

---

## The workflow

### 1. Get the new data in place

Raw CSVs go in the `ECHO REVAMP/` folder beside the repo. If you changed them, share
them: `python scripts/echo.py push-data raw`.

### 2. Test locally first

Never test against production. Bring up a local database with real data in it:

```bash
docker-compose up -d
python scripts/echo.py restore-local
```

Confirm `.env` still has `DB_HOST=localhost`, then run the ETL:

```bash
cd packages/etl
python load_data_to_db.py          # upsert
# or, to replace an indicator outright:
python swap_indicator.py --dry-run # check first
python swap_indicator.py
```

`swap_indicator.py` needs editing before it runs — `INDICATORS_TO_SWAP` maps a source
CSV column to the exact display name stored in the database, and `SOURCE_FILES` says
which CSV each geography level comes from.

Then check what you loaded:

```bash
python scripts/echo.py verify
python scripts/echo.py check-indicators
```

`check-indicators` tells you whether the config needs updating. It almost always does.

### 3. Update the indicator config

```bash
python scripts/echo.py sync-indicators
```

- **New year of an existing indicator:** nothing to type. It sees the new year in the
  data and offers to add it.
- **New indicator:** it lists the indicator names found in the database so you pick
  from a list rather than retyping an exact string, then asks for a short id, a theme
  and a description. The years come from the data.

It backs the file up, edits it, and re-checks that it still loads. Review the change
with `git diff apps/backend/indicator_config.py`.

### 4. Test the whole thing locally

```bash
cd apps/backend && uvicorn main:app --reload --port 8000
cd apps/frontend && pnpm run dev
```

Open http://localhost:5175 and confirm the new data appears, for the right years, in
the right theme.

### 5. Back up production

```bash
python scripts/echo.py snapshot-db
```

**Do not skip this.** There is no staging environment and no second copy. This is
your only undo.

### 6. Load into production

Point `.env` at production — change `DB_HOST`, `DB_NAME`, `DB_USER`, `DB_PASSWORD` to
the RDS values — and run the same loader you ran in step 2.

The ETL scripts will show the target and make you type the database name before they
write. That prompt is the last thing standing between you and production; read it.

```bash
python scripts/echo.py verify
python scripts/echo.py check-indicators
```

**Then put `.env` back to localhost.** Leaving it pointed at production is how
accidents happen later.

### 7. Deploy the backend

The config from step 3 is not live until you do this:

```bash
python scripts/echo.py deploy-backend
```

It re-checks the config against the database, builds the image, pushes it, tells App
Runner to pull it, and waits until the service is running again. Five to ten minutes.

### 8. Confirm

Open https://echodashboard.org, find your indicator, check the years and a few values
against the source. Done.

You only need `deploy-frontend` if you changed something in `apps/frontend/`.

---

## When something goes wrong

**Data looks wrong in the dashboard.** Restore the snapshot from step 5 — but note it
creates a *new* RDS instance with a *new* endpoint, so App Runner's `DATABASE_URL`
must be repointed afterwards. See
[aws-infrastructure.md](aws-infrastructure.md).

**The indicator does not appear at all.** Almost always step 3 or step 7 — either the
config entry is missing, or the backend was never redeployed. Run
`python scripts/echo.py check-indicators`.

**The indicator appears but is empty.** The display name in `indicator_config.py` does
not exactly match `results_data.indicator_id`. `check-indicators` reports this as
"in config with no data".

**The year cannot be selected.** It is missing from `available_years`. Run
`sync-indicators`.

**The deploy finished but nothing changed.** For the frontend, CloudFront is still
serving the cached build — wait two minutes. For the backend, confirm the App Runner
status reached `RUNNING`.

**`deploy-backend` fails at `docker login`.** Your AWS session expired
(`python scripts/echo.py login`), or your IAM user is missing the
`sts:GetServiceBearerToken` permission that ECR Public needs.

---

## Doing it by hand

If a command misbehaves, these are what it runs. All need an active session
(`login`), and the identifiers come from your `.env.deploy`.

**Backend deploy:**

```bash
aws ecr-public get-login-password --region us-east-1 --profile echo-mfa \
  | docker login --username AWS --password-stdin public.ecr.aws
cd apps/backend
docker build --platform linux/amd64 -t $ECR_IMAGE:latest .
docker push $ECR_IMAGE:latest
aws apprunner start-deployment --service-arn $APPRUNNER_SERVICE_ARN \
  --region us-east-1 --profile echo-mfa
```

`--platform linux/amd64` is not optional. Without it the push succeeds and the
container then fails to start with an error that says nothing about architecture.
Pushing alone does not deploy — App Runner only pulls when told to.

**Frontend deploy:**

```bash
cd apps/frontend && pnpm build
aws s3 sync build/ s3://$S3_FRONTEND_BUCKET --delete --profile echo-mfa
aws cloudfront create-invalidation --distribution-id $CLOUDFRONT_DISTRIBUTION_ID \
  --paths "/*" --profile echo-mfa
```

Skip the invalidation and viewers keep the old build.

**Snapshot:**

```bash
aws rds create-db-snapshot --db-instance-identifier $RDS_INSTANCE_ID \
  --db-snapshot-identifier manual-$(date +%Y%m%d-%H%M%S) --profile echo-mfa
```
