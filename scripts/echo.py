#!/usr/bin/env python3
"""ECHO dashboard operations.

    python scripts/echo.py <command>

Start with `preflight` on a new machine, and see docs/adding-a-dataset.md for
the full workflow. Every command that writes to production says so first and
asks before doing it.

Nothing here is magic — each command runs the same aws/docker/psql commands you
would type by hand, and the runbook lists those alongside each step so you can
always fall back to doing it manually.
"""
import argparse
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

from echo_tools import aws, data, database, deploy, indicators, preflight  # noqa: E402
from echo_tools.console import Abort, BOLD, NC, bad, detail, say  # noqa: E402


def build_parser():
    parser = argparse.ArgumentParser(
        prog='echo.py',
        description=__doc__,
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="Full workflow: docs/adding-a-dataset.md",
    )
    subcommands = parser.add_subparsers(dest='command', metavar='<command>')

    def add(name, help_text, description=None):
        return subcommands.add_parser(
            name, help=help_text, description=description or help_text,
            formatter_class=argparse.RawDescriptionHelpFormatter)

    add('preflight', "check this machine is set up (changes nothing)")

    login_cmd = add(
        'login', "start a 12-hour AWS session using your MFA code",
        "Exchanges an MFA code for temporary credentials, stored in the\n"
        "'echo-mfa' AWS profile. Every other command uses it automatically.\n"
        "Required because this account denies most API calls without MFA.\n\n"
        "Your MFA device is found automatically. Pass --serial only if that\n"
        "lookup is denied, or set MFA_SERIAL in your environment.")
    login_cmd.add_argument('--serial', metavar='ARN',
                           help="MFA device ARN, e.g. arn:aws:iam::<account>:mfa/<name>")

    pull = add('pull-data', "download ETL inputs and dumps from S3",
               "Fetches the shared source data. Run this first on a new machine —\n"
               "the inputs are several GB and are not in git.")
    pull.add_argument('what', nargs='?', default='all',
                      choices=['all', 'raw', 'clean', 'dumps'])
    pull.add_argument('--dry-run', action='store_true', help="show what would transfer")

    push = add('push-data', "upload ETL inputs to S3",
               "Publishes source data you have updated, so others get it too.\n"
               "Use dump-db --upload for database dumps.")
    push.add_argument('what', nargs='?', default='all', choices=['all', 'raw', 'clean'])
    push.add_argument('--dry-run', action='store_true', help="show what would transfer")

    dump = add('dump-db', "copy a database into dumps/ as a .sql.gz file",
               "Reads the database that .env points at and writes a compressed dump.\n"
               "Never writes to a database. Use it to back up before a change, or to\n"
               "produce the seed dump others restore locally.")
    dump.add_argument('--upload', action='store_true', help="also upload it to S3")
    dump.add_argument('--schema-only', action='store_true',
                      help="structure without data (regenerates a truthful schema file)")

    restore = add('restore-local', "load a dump into your local Postgres",
                  "Refuses to run unless .env points at a local database.")
    restore.add_argument('dump', nargs='?', help="filename in dumps/ (default: newest)")

    add('verify', "run the data-quality checks against the current target",
        "Runs scripts/verify_data.sql against whichever database .env points at.")

    add('snapshot-db', "take an RDS snapshot before changing production",
        "The undo button. Restoring a snapshot creates a NEW instance with a new\n"
        "endpoint, so App Runner's DATABASE_URL must be repointed afterwards.")

    add('check-indicators', "compare the database against indicator_config.py",
        "Read-only. Finds data with no config entry (invisible in the dashboard),\n"
        "config entries with no data, and years loaded but not selectable.")

    add('sync-indicators', "add missing indicators and years to indicator_config.py",
        "Interactive. Derives available_years from the data and offers exact display\n"
        "names from the database so nothing has to be retyped.")

    backend = add('deploy-backend', "build, push and roll out the backend",
                  "Builds a linux/amd64 image, pushes to ECR Public, then explicitly\n"
                  "tells App Runner to pull it — pushing alone does not deploy.")
    backend.add_argument('--skip-checks', action='store_true',
                         help="do not compare indicator config against the database first")

    add('deploy-frontend', "build the SPA, upload to S3 and invalidate CloudFront",
        "The upload uses --delete and the bucket is not versioned, so a bad build\n"
        "is undone by building again rather than by rolling back.")

    return parser


def dispatch(args):
    if args.command == 'preflight':
        return preflight.run_preflight()
    if args.command == 'login':
        aws.login(serial=args.serial)
        return 0
    if args.command == 'pull-data':
        return data.sync_data('pull', args.what, args.dry_run)
    if args.command == 'push-data':
        return data.sync_data('push', args.what, args.dry_run)
    if args.command == 'dump-db':
        database.dump_db(schema_only=args.schema_only, upload=args.upload)
        return 0
    if args.command == 'restore-local':
        database.restore_local(args.dump)
        return 0
    if args.command == 'verify':
        database.verify()
        return 0
    if args.command == 'snapshot-db':
        database.snapshot_db()
        return 0
    if args.command == 'check-indicators':
        return indicators.check_indicators()
    if args.command == 'sync-indicators':
        return indicators.sync_indicators()
    if args.command == 'deploy-backend':
        return deploy.deploy_backend(skip_checks=args.skip_checks)
    if args.command == 'deploy-frontend':
        return deploy.deploy_frontend()
    return 1


def main():
    parser = build_parser()
    args = parser.parse_args()

    if not args.command:
        parser.print_help()
        return 0

    try:
        return dispatch(args)
    except Abort as exc:
        say()
        bad(str(exc))
        if exc.fix:
            say()
            say("{}How to fix:{}".format(BOLD, NC))
            for line in str(exc.fix).splitlines():
                detail(line)
        say()
        return 1
    except KeyboardInterrupt:
        say()
        say("Interrupted.")
        return 130


if __name__ == '__main__':
    sys.exit(main())
