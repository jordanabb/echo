"""Database commands: dump, restore, verify, snapshot.

Which database these act on is decided by DB_HOST in the repo-root .env — the
same rule the ETL scripts follow. Every command prints its target first.
"""
import gzip
import re
import shutil
import subprocess
import tempfile
from datetime import datetime
from pathlib import Path

from . import aws
from .config import (DUMPS_DIR, ETL_DIR, VERIFY_SQL, connection_url,
                     describe_target, load_deploy_config, resolve_db_target)
from .console import confirm, detail, die, ok, say, step, warn


def _tool(name):
    found = shutil.which(name)
    if not found:
        die("'{}' is not installed or not on your PATH.".format(name),
            "macOS:   brew install libpq && brew link --force libpq\n"
            "Windows: install PostgreSQL from https://www.postgresql.org/download/windows/\n"
            "         then add its bin\\ folder to your PATH\n"
            "Linux:   apt install postgresql-client")
    return found


def _major_version(text):
    match = re.search(r'(\d+)', text)
    return int(match.group(1)) if match else 0


def _server_version(url):
    """Return the server's major version, proving we can connect at the same time."""
    result = subprocess.run([_tool('psql'), url, '-tAc', 'SHOW server_version;'],
                            stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True)
    if result.returncode != 0:
        message = (result.stderr or '').strip()
        fix = ("Check the DB_* values in .env.\n"
               "If this is production, confirm your network can reach RDS on port 5432.")
        if 'could not translate host name' in message.lower():
            fix = "The hostname in .env does not resolve. Check DB_HOST for a typo."
        elif 'password authentication failed' in message.lower():
            fix = "DB_USER/DB_PASSWORD in .env are not accepted by this server."
        die("Could not connect to the database.\n\n{}".format(message), fix)
    return _major_version(result.stdout)


def _announce(target, verb):
    where = 'PRODUCTION' if not target.is_local else 'local'
    step("{} {} database".format(verb, where))
    detail(describe_target(target))
    return where


def dump_db(schema_only=False, upload=False):
    """Copy a database into dumps/ as a gzipped SQL file. Never writes to a database."""
    pg_dump = _tool('pg_dump')
    target = resolve_db_target()
    _announce(target, "Dumping")

    url = connection_url(target)
    server = _server_version(url)
    client = _major_version(subprocess.run([pg_dump, '--version'],
                                           stdout=subprocess.PIPE, text=True).stdout)

    # pg_dump refuses to dump a server newer than itself. Production runs
    # Postgres 16 while docker-compose runs 15, so installing the "obvious"
    # client version fails only when pointed at production — catch it here
    # rather than after a long-running command.
    if client < server:
        die("pg_dump is version {} but the server is version {}.".format(client, server),
            "pg_dump cannot dump a newer server. Install a matching client:\n"
            "  macOS:   brew install postgresql@{v}\n"
            "  Windows: install PostgreSQL {v} and put its bin\\ folder first on PATH"
            .format(v=server))
    ok("Server Postgres {}, client {}".format(server, client))

    if not target.is_local:
        warn("Reading the full dataset puts real load on the production instance.")
        detail("Prefer off-peak hours. This is read-only and cannot change any data.")

    DUMPS_DIR.mkdir(exist_ok=True)
    stamp = datetime.now().strftime('%Y%m%d_%H%M%S')
    kind = 'schema' if schema_only else 'full'
    outfile = DUMPS_DIR / "echo_{}_{}_{}.sql.gz".format(target.name, kind, stamp)

    # --no-owner/--no-acl keep production role names out of the dump, so it can be
    # restored into a local database where the 'root' role does not exist.
    args = [pg_dump, url, '--no-owner', '--no-acl']
    if schema_only:
        args.append('--schema-only')

    step("Writing {}".format(outfile.name))
    if not schema_only:
        detail("This takes a while — the dataset is several GB uncompressed.")

    with tempfile.TemporaryFile(mode='w+') as errors:
        process = subprocess.Popen(args, stdout=subprocess.PIPE, stderr=errors)
        with gzip.open(str(outfile), 'wb') as compressed:
            shutil.copyfileobj(process.stdout, compressed)
        process.stdout.close()
        code = process.wait()
        if code != 0:
            errors.seek(0)
            outfile.unlink(missing_ok=True)
            die("pg_dump failed.\n\n{}".format(errors.read().strip()))

    size_mb = outfile.stat().st_size / (1024 * 1024)
    ok("Wrote {} ({:.1f} MB compressed)".format(outfile.name, size_mb))

    if upload:
        config = load_deploy_config('ECHO_DATA_BUCKET')
        aws.require_session()
        step("Uploading to S3")
        destination = "s3://{}/dumps/{}".format(config['ECHO_DATA_BUCKET'], outfile.name)
        aws.run(['s3', 'cp', str(outfile), destination], region=config['AWS_REGION'],
                capture=False)
        ok("Uploaded to {}".format(destination))

    say()
    detail("Restore it into your local database with:")
    detail("  python scripts/echo.py restore-local {}".format(outfile.name))
    return outfile


def restore_local(dump_name=None):
    """Load a dump into the local Docker Postgres.

    Refuses to run against anything non-local. Restoring is destructive, and the
    whole point of this command is to populate a scratch database.
    """
    # The safety check comes before the tool check on purpose: if .env points at
    # production, that is what the operator needs told, not a missing psql.
    target = resolve_db_target()

    if not target.is_local:
        die("Refusing to restore into {} — that is not a local database."
            .format(target.host),
            "This command only ever writes to local Postgres.\n"
            "Point DB_HOST in .env back at localhost before running it.\n\n"
            "To move data into production, load it with the ETL scripts instead.")

    psql = _tool('psql')

    if dump_name:
        candidate = Path(dump_name)
        dump_file = candidate if candidate.is_absolute() else DUMPS_DIR / candidate.name
        if not dump_file.exists():
            die("No such dump: {}".format(dump_file),
                "List what you have: python scripts/echo.py restore-local")
    else:
        available = sorted(DUMPS_DIR.glob('*.sql.gz'), reverse=True) if DUMPS_DIR.exists() else []
        if not available:
            die("No dumps found in {}".format(DUMPS_DIR),
                "Fetch the shared one:  python scripts/echo.py pull-data\n"
                "Or create one:         python scripts/echo.py dump-db")
        dump_file = available[0]
        detail("Using the most recent dump. Pass a filename to choose another.")

    _announce(target, "Restoring into")
    detail("from {}".format(dump_file.name))

    confirm("This REPLACES the contents of your local '{}' database.".format(target.name))

    url = connection_url(target)
    _server_version(url)  # fail early if the container is not running

    step("Restoring")
    detail("Errors about existing objects are normal on a non-empty database.")
    with tempfile.TemporaryFile(mode='w+') as errors:
        process = subprocess.Popen([psql, url], stdin=subprocess.PIPE, stdout=errors,
                                   stderr=subprocess.STDOUT)
        with gzip.open(str(dump_file), 'rb') as compressed:
            shutil.copyfileobj(compressed, process.stdin)
        process.stdin.close()
        code = process.wait()
        if code != 0:
            errors.seek(0)
            die("Restore failed.\n\n{}".format(errors.read()[-2000:]))

    ok("Restored {}".format(dump_file.name))
    say()
    detail("Check it: python scripts/echo.py verify")


def verify():
    """Run scripts/verify_data.sql against the current target, local or production."""
    psql = _tool('psql')
    target = resolve_db_target()
    _announce(target, "Verifying")

    if not VERIFY_SQL.exists():
        die("Missing {}".format(VERIFY_SQL))

    url = connection_url(target)
    _server_version(url)

    result = subprocess.run([psql, url, '-f', str(VERIFY_SQL)],
                            stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True)
    # The report itself goes to stdout so it can be redirected to a file.
    print(result.stdout)
    if result.returncode != 0:
        die("Verification query failed.\n\n{}".format((result.stderr or '').strip()))
    ok("Verification complete — review the counts above.")


def snapshot_db():
    """Take a manual RDS snapshot. The undo button before any production change."""
    config = load_deploy_config('RDS_INSTANCE_ID')
    aws.require_session()

    instance = config['RDS_INSTANCE_ID']
    stamp = datetime.now().strftime('%Y%m%d-%H%M%S')
    snapshot_id = "{}-manual-{}".format(instance, stamp)

    step("Snapshotting RDS instance {}".format(instance))
    detail("Manual snapshots are kept until deleted, unlike the 14-day automatic ones.")

    aws.run(['rds', 'create-db-snapshot',
             '--db-instance-identifier', instance,
             '--db-snapshot-identifier', snapshot_id,
             '--output', 'text', '--query', 'DBSnapshot.DBSnapshotIdentifier'],
            region=config['AWS_REGION'])
    ok("Started snapshot {}".format(snapshot_id))

    step("Waiting for it to complete")
    detail("Usually a few minutes. Safe to interrupt — the snapshot continues without you.")
    aws.run(['rds', 'wait', 'db-snapshot-available',
             '--db-snapshot-identifier', snapshot_id],
            region=config['AWS_REGION'], capture=False)

    ok("Snapshot {} is available".format(snapshot_id))
    say()
    detail("Restoring it creates a NEW instance with a NEW endpoint, so App Runner's")
    detail("DATABASE_URL has to be repointed afterwards. See docs/aws-infrastructure.md.")
