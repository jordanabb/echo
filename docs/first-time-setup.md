# First-time setup

Getting a new machine from nothing to a working local copy of the ECHO
dashboard. Commands are shown for Windows PowerShell; macOS and Linux notes are
in the margins where they differ.

The goal of your first session is **a verified local replica of production on
your own machine**. You will not touch production, and nothing here can affect
the live site.

Two things must come from whoever currently runs ECHO — ask for them before you
start, because you will be blocked without them:

1. The contents of `.env.deploy` (seven lines of AWS resource identifiers).
2. An AWS IAM user: a console password, and permission to create your own access
   keys.

---

## 1. Install the tools

```powershell
winget install Git.Git
winget install Python.Python.3.12
winget install Amazon.AWSCLI
winget install PostgreSQL.PostgreSQL.16
winget install Docker.DockerDesktop
```

**Close and reopen PowerShell afterwards** — installers change `PATH`, and open
terminals do not pick that up.

Three things the installers get wrong on their own:

- **Python must be 3.12**, not the newest. The pinned dependencies have no wheels
  for 3.13, so `pip` would try to compile them from source and fail.
- **PostgreSQL must be 16**, to match production, and its installer does not add
  itself to `PATH`. Add `C:\Program Files\PostgreSQL\16\bin` manually
  (Settings → System → About → Advanced system settings → Environment Variables).
- **Docker Desktop must be running**, not merely installed. Launch it once and
  let it finish starting.

> macOS: `brew install git python@3.12 awscli postgresql@16` and Docker Desktop
> from docker.com.

### If `python` prints "Python was not found"

Windows ships Microsoft Store placeholder shortcuts that hijack the command.
Use the `py` launcher instead — it ignores them and is used throughout this
guide:

```powershell
py --version
```

To fix it properly: Settings → Apps → Advanced app settings → App execution
aliases → turn off `python.exe` and `python3.exe`.

---

## 2. Get the code

```powershell
cd $HOME
git clone https://github.com/jordanabb/echo.git
cd echo
py -m pip install -r packages\etl\requirements.txt
```

You clone once, but you need `cd echo` in every new terminal.

---

## 3. Create the two config files

Neither is in the repository — they hold machine-specific and
infrastructure-specific values, and the repository is public.

```powershell
cp .env.example .env
cp .env.deploy.example .env.deploy
notepad .env.deploy
```

Paste in the seven lines you were given, then save.

Copy the example **first** rather than creating a new file in Notepad: Notepad
silently appends `.txt` to a filename it created, and nothing will find
`.env.deploy.txt`.

Leave `.env` exactly as copied. It points at a local database, which is what you
want. Production credentials are a separate, deliberate handover later.

---

## 4. Set up AWS access

This account denies almost every API call without a recent MFA token, so there
is an order to it: **console first, command line second.**

1. Sign in at the console URL you were given, with your username and temporary
   password. Set a real password when prompted.
2. **Security credentials → Multi-factor authentication → Assign MFA device.**
   Choose *Authenticator app*, scan the QR code, and enter **two consecutive
   codes** — wait for the code to roll over between them.
3. **Sign out and back in**, entering an MFA code this time. Your session now
   carries MFA, which the next step needs.
4. **Security credentials → Access keys → Create access key →
   Command line interface (CLI).** The secret is shown **once** — save it to a
   password manager immediately.

Then, in PowerShell:

```powershell
aws configure
```

It asks for four things: your access key ID, your secret access key,
`us-east-1`, and `json`.

Finally:

```powershell
py scripts\echo.py login
```

This swaps your MFA code for a 12-hour session. Run it again whenever a command
says your session has expired. Everything else picks it up automatically.

> If it cannot find your MFA device, pass it explicitly:
> `py scripts\echo.py login --serial arn:aws:iam::<account>:mfa/<device>`
> The ARN is on the same console page where you registered it.

---

## 5. Check the machine

```powershell
py scripts\echo.py preflight
```

This changes nothing — it only looks, and reports every problem with its fix.
Do not continue until it says **Ready**. A missing piece here becomes a much
harder-to-read failure later.

A warning about `pnpm` is fine to ignore. It only builds the frontend, which
adding data never touches.

---

## 6. Download the data

```powershell
py scripts\echo.py pull-data
```

About 10 GB, so allow time. It verifies both sides afterwards and retries
anything that did not arrive. On a slow or metered connection, `pull-data dumps`
fetches only the database dump (~1 GB), which is enough for the next step.

---

## 7. Build your local database

Docker Desktop must be running.

```powershell
docker-compose up -d
py scripts\echo.py restore-local
py scripts\echo.py verify
py scripts\echo.py check-indicators
```

- `docker-compose up -d` starts PostgreSQL on port 5433.
- `restore-local` loads the production dump into it. It refuses to run against
  anything that is not a local database.
- `verify` prints row counts and coverage.
- `check-indicators` compares the database against the dashboard's configuration.

When `check-indicators` reports that the config and database agree, you have a
complete working copy of production on your machine. **That is the finish line
for setup.**

---

## What next

[adding-a-dataset.md](adding-a-dataset.md) is the workflow for loading new data.

Before doing it for real, do it once entirely locally: load something into your
local database, watch `check-indicators` flag it as missing from the config, and
fix it with `sync-indicators`. You will have seen the whole shape of the job,
including what the failure looks like, without any risk.

Two things to leave alone until you have done that and someone is watching:
pointing `.env` at production, and `deploy-backend`.
