"""Paths, deployment configuration, and database target resolution.

The database target deliberately comes from packages/etl/db_target.py rather
than being reimplemented here. The ETL scripts and these commands must never
disagree about what counts as production.
"""
import os
import sys
from pathlib import Path

from .console import die

REPO_ROOT = Path(__file__).resolve().parents[2]
ETL_DIR = REPO_ROOT / 'packages' / 'etl'
BACKEND_DIR = REPO_ROOT / 'apps' / 'backend'
FRONTEND_DIR = REPO_ROOT / 'apps' / 'frontend'
DUMPS_DIR = REPO_ROOT / 'dumps'
INDICATOR_CONFIG = BACKEND_DIR / 'indicator_config.py'
VERIFY_SQL = REPO_ROOT / 'scripts' / 'verify_data.sql'
DEPLOY_ENV = REPO_ROOT / '.env.deploy'

# Raw ETL inputs. Defaults to "ECHO REVAMP" beside the repo root, but
# ECHO_RAW_DIR overrides it — the same variable packages/etl/create_national.py
# honours, so the loader and the S3 sync always read the same folder. They must
# not diverge: a sync that quietly pushed a different directory than the one
# just loaded would be invisible until someone else pulled the wrong data.
RAW_DATA_DIR = Path(os.environ.get('ECHO_RAW_DIR') or (REPO_ROOT / 'ECHO REVAMP'))
CLEAN_DATA_DIR = ETL_DIR / 'clean_output_national'

# S3 layout inside ECHO_DATA_BUCKET.
S3_RAW_PREFIX = 'source/echo-revamp'
S3_CLEAN_PREFIX = 'source/clean_output_national'
S3_DUMP_PREFIX = 'dumps'

sys.path.insert(0, str(ETL_DIR))


def resolve_db_target():
    """Return the target described by the repo-root .env.

    db_target.resolve_target() exits the process when configuration is missing,
    which is right for the ETL scripts but not here, where callers may want to
    report the problem alongside others. Translate it into an Abort.
    """
    try:
        import db_target
    except ImportError as exc:
        die("Could not import packages/etl/db_target.py ({}).".format(exc),
            "Run commands from a checkout with packages/etl/ present.")

    try:
        return db_target.resolve_target()
    except SystemExit:
        die("The repo-root .env is missing or incomplete.",
            "cp .env.example .env, then fill in the DB_* values.")


def describe_target(target):
    return "{} on {}:{} as {}".format(
        target.name, target.host, target.port, target.user)


def connection_url(target):
    """Return a libpq URL for this target.

    RDS requires TLS; the local Docker container does not offer it, so sslmode
    is added only for remote hosts.
    """
    url = target.url
    if not target.is_local:
        url += '&sslmode=require' if '?' in url else '?sslmode=require'
    return url


def load_deploy_config(*required):
    """Read .env.deploy and return it as a dict, checking required keys.

    Infrastructure identifiers (account, ARNs, buckets, RDS endpoint) live in
    this git-ignored file because the repository is public.
    """
    if not DEPLOY_ENV.exists():
        die("No .env.deploy found at {}".format(DEPLOY_ENV),
            "cp .env.deploy.example .env.deploy\n\n"
            "Then fill in the values. They are not secret, but they are kept out\n"
            "of this public repository. Ask whoever administers the AWS account,\n"
            "or read them from docs/aws-infrastructure.md.")

    config = {}
    for raw in DEPLOY_ENV.read_text(encoding='utf-8').splitlines():
        line = raw.strip()
        if not line or line.startswith('#') or '=' not in line:
            continue
        key, _, value = line.partition('=')
        config[key.strip()] = value.strip().strip('"').strip("'")

    # Environment wins, so a one-off override does not need a file edit.
    for key in list(config):
        if os.environ.get(key):
            config[key] = os.environ[key]

    missing = [key for key in required if not config.get(key)]
    if missing:
        die("Missing in .env.deploy: {}".format(', '.join(missing)),
            "Add the listed values. See .env.deploy.example for what each one means.")

    config.setdefault('AWS_REGION', 'us-east-1')
    return config
