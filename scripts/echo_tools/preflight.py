"""Check this machine can do a dataset update. Changes nothing.

Reports every problem it finds rather than stopping at the first, because
setting up a new machine usually means fixing several things at once.
"""
import platform
import shutil
import subprocess

from . import aws
from .config import DEPLOY_ENV, REPO_ROOT, describe_target, resolve_db_target
from .console import Abort, bad, detail, ok, say, step, warn

TOOLS = [
    ('python', "Python", "https://www.python.org/downloads/"),
    ('aws', "AWS CLI", "https://aws.amazon.com/cli/  (on Windows use the MSI installer)"),
    ('docker', "Docker", "https://docs.docker.com/get-docker/"),
    ('psql', "psql / pg_dump", "Windows: https://www.postgresql.org/download/windows/\n"
                               "       macOS:   brew install libpq && brew link --force libpq"),
    ('pnpm', "pnpm", "npm install -g pnpm"),
]

ETL_PACKAGES = ['pandas', 'sqlalchemy', 'dotenv', 'psycopg2', 'shapely']


def run_preflight():
    failures = []

    def fail(message, fix=None):
        bad(message)
        if fix:
            detail(fix)
        failures.append(message)

    step("Tools")
    for command, label, hint in TOOLS:
        # 'python' resolves differently across platforms; we are already running,
        # so report the interpreter actually in use.
        if command == 'python':
            ok("{} {}".format(label, platform.python_version()))
            continue
        if shutil.which(command):
            ok(label)
        else:
            fail("{} — not found".format(label), hint)

    step("Docker")
    if shutil.which('docker'):
        running = subprocess.run(['docker', 'info'], stdout=subprocess.DEVNULL,
                                 stderr=subprocess.DEVNULL).returncode == 0
        if running:
            ok("Docker daemon is running")
            names = subprocess.run(['docker', 'ps', '--format', '{{.Names}}'],
                                   stdout=subprocess.PIPE, text=True).stdout
            if 'echo_db' in names.split():
                ok("Local Postgres container (echo_db) is up")
            else:
                warn("Local Postgres container is not running")
                detail("Start it with: docker-compose up -d")
                detail("Needed to test a dataset change before touching production.")
        else:
            fail("Docker is installed but not running", "Start Docker Desktop, then re-run this.")

    machine = platform.machine().lower()
    if machine in ('arm64', 'aarch64'):
        warn("This machine is arm64 — backend image builds are emulated and slow.")
        detail("Correct, just slow. The deploy always targets linux/amd64.")
    else:
        ok("Backend image builds are native on this machine ({})".format(machine or 'x86_64'))

    step("Python packages for the ETL")
    missing = []
    for package in ETL_PACKAGES:
        try:
            __import__(package)
        except ImportError:
            missing.append(package)
    if missing:
        fail("Missing: {}".format(', '.join(missing)),
             "cd packages/etl && pip install -r requirements.txt")
    else:
        ok("All ETL packages importable")

    step("Configuration")
    if (REPO_ROOT / '.env').exists():
        try:
            target = resolve_db_target()
            if target.is_local:
                ok(".env points at local Postgres ({}:{})".format(target.host, target.port))
            else:
                warn(".env points at PRODUCTION — {}".format(describe_target(target)))
                detail("Fine if deliberate. Writes will ask you to confirm.")
        except Abort as exc:
            fail(str(exc), exc.fix)
    else:
        fail("No .env at the repo root", "cp .env.example .env, then fill in the values")

    if DEPLOY_ENV.exists():
        ok(".env.deploy present")
    else:
        fail("No .env.deploy at the repo root",
             "cp .env.deploy.example .env.deploy, then fill in the values")

    step("AWS access")
    if shutil.which('aws'):
        identity = aws.current_identity()
        if identity:
            ok("Signed in as {}".format(identity))
        else:
            fail("No active AWS session", "python scripts/echo.py login")

    say()
    if failures:
        step("{} problem(s) need fixing before you can deploy.".format(len(failures)))
        return 1

    step("Ready.")
    detail("The dataset workflow is in docs/adding-a-dataset.md")
    return 0
