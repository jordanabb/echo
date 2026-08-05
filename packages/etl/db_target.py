"""
Shared target guard for the ETL scripts in this directory.

Every loader here builds its connection string from the same DB_* variables in
the repo-root .env, and nothing in their output says which database was hit.
That is harmless while .env points at the local Docker Postgres, but the same
scripts are also how production RDS gets updated — so a "quick local test" run
with a production .env silently rewrites live data. Several of these scripts
DELETE before they INSERT, so there is no undo short of a snapshot restore.

confirm_target() prints the resolved target and, when it is not localhost,
requires the operator to type the database name before anything is written.

For automation (CI, cron) where no human is present:

    ETL_ASSUME_YES=1 python3 load_results_direct.py

Set that only where a human has already decided the target is correct.
"""
import os
import sys
from collections import namedtuple

from dotenv import load_dotenv

Target = namedtuple('Target', ['url', 'user', 'host', 'port', 'name', 'is_local'])

LOCAL_HOSTS = {'localhost', '127.0.0.1', '::1', '0.0.0.0'}


def _say(message):
    """Write straight to stderr.

    Deliberately not logging: which database you are about to write to must be
    visible no matter how (or whether) the calling script configured logging.
    """
    print(message, file=sys.stderr)


def resolve_target():
    """Read the repo-root .env and return the resolved connection target.

    Exits with a readable message if any DB_* variable is missing, rather than
    letting the connection string interpolate 'None' and fail obscurely later.
    """
    dotenv_path = os.path.join(os.path.dirname(__file__), '..', '..', '.env')
    load_dotenv(dotenv_path=dotenv_path)

    parts = {name: os.getenv(name) for name in
             ('DB_USER', 'DB_PASSWORD', 'DB_HOST', 'DB_PORT', 'DB_NAME')}
    missing = [name for name, value in parts.items() if not value]
    if missing:
        _say(f"ERROR: missing {', '.join(missing)} in {os.path.abspath(dotenv_path)}")
        sys.exit(1)

    return Target(
        url=("postgresql://{DB_USER}:{DB_PASSWORD}@{DB_HOST}:{DB_PORT}/{DB_NAME}"
             .format(**parts)),
        user=parts['DB_USER'],
        host=parts['DB_HOST'],
        port=parts['DB_PORT'],
        name=parts['DB_NAME'],
        is_local=parts['DB_HOST'] in LOCAL_HOSTS,
    )


def confirm_target(action="write to", dry_run=False):
    """Announce the target database and confirm it before writing.

    Always logs where the script is pointed. On a non-local host, requires the
    operator to type the database name exactly — unless ETL_ASSUME_YES is set,
    or dry_run=True (nothing is written, so there is nothing to confirm).

    Returns the Target so callers can use target.url for create_engine().
    """
    target = resolve_target()
    where = 'LOCAL' if target.is_local else 'REMOTE'
    _say(f"=== Target: {where} — {target.name} on {target.host}:{target.port} "
         f"as {target.user} ===")

    if target.is_local or dry_run:
        return target

    if os.getenv('ETL_ASSUME_YES'):
        _say("Non-local target; proceeding because ETL_ASSUME_YES is set.")
        return target

    if not sys.stdin.isatty():
        _say(f"ERROR: refusing to {action} non-local database '{target.name}' on "
             f"{target.host} without confirmation. Re-run interactively, or set "
             f"ETL_ASSUME_YES=1 if this target is intended.")
        sys.exit(1)

    _say(f"WARNING: this will {action} the REMOTE database '{target.name}' on "
         f"{target.host}.\nThat is not your local Docker Postgres.")
    answer = input(f"Type the database name ({target.name}) to continue, "
                   f"or anything else to abort: ").strip()
    if answer != target.name:
        _say("Aborted — no changes made.")
        sys.exit(1)

    return target
