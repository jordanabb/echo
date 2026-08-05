"""Moving ETL inputs and dumps between S3 and this machine.

The raw inputs and generated intermediates are far too large for git —
results.csv alone is about 2.5 GB — so S3 holds the shared copy. Without this,
a new machine cannot rebuild the dataset at all.
"""
from . import aws
from .config import (CLEAN_DATA_DIR, DUMPS_DIR, RAW_DATA_DIR, S3_CLEAN_PREFIX,
                     S3_DUMP_PREFIX, S3_RAW_PREFIX, load_deploy_config)
from .console import detail, die, ok, say, step, warn

# What each name covers: local directory, S3 prefix, description.
PARTS = {
    'raw':   (RAW_DATA_DIR,   S3_RAW_PREFIX,   "raw source CSVs (ECHO REVAMP)"),
    'clean': (CLEAN_DATA_DIR, S3_CLEAN_PREFIX, "generated intermediates (clean_output_national)"),
    'dumps': (DUMPS_DIR,      S3_DUMP_PREFIX,  "database dumps"),
}


def _sync(config, direction, part, dry_run):
    local_dir, prefix, description = PARTS[part]
    remote = "s3://{}/{}".format(config['ECHO_DATA_BUCKET'], prefix)

    if direction == 'pull':
        step("Pulling {}".format(description))
        detail("{}  ->  {}".format(remote, local_dir))
        local_dir.mkdir(parents=True, exist_ok=True)
        source, destination = remote, str(local_dir)
    else:
        if not local_dir.exists():
            warn("Skipping {} — {} does not exist here".format(part, local_dir))
            return
        step("Pushing {}".format(description))
        detail("{}  ->  {}".format(local_dir, remote))
        source, destination = str(local_dir), remote

    args = ['s3', 'sync', source, destination]
    if dry_run:
        args.append('--dryrun')
    # Deliberately no --delete: a sync must never remove something another
    # machine still depends on. Prune S3 by hand if it genuinely needs it.
    aws.run(args, region=config['AWS_REGION'], capture=False)
    ok("{} done".format(description))


def sync_data(direction, what='all', dry_run=False):
    """Pull or push the shared data. `what` is all, raw, clean or dumps."""
    # Validate arguments before asking for credentials or config, so a typo does
    # not send anyone off to run `login` first.
    if what not in list(PARTS) + ['all']:
        die("Unknown data set '{}'.".format(what),
            "Choose one of: all, raw, clean, dumps")

    if direction == 'push' and what in ('all', 'dumps'):
        if what == 'dumps':
            die("Use dump-db --upload to publish a dump.",
                "python scripts/echo.py dump-db --upload")
        warn("Dumps are not pushed by 'push-data' — use dump-db --upload for those.")

    config = load_deploy_config('ECHO_DATA_BUCKET')
    aws.require_session()

    if dry_run:
        warn("Dry run — nothing will actually transfer.")

    parts = list(PARTS) if what == 'all' else [what]
    if direction == 'push':
        parts = [p for p in parts if p != 'dumps']

    for part in parts:
        _sync(config, direction, part, dry_run)

    say()
    if direction == 'pull':
        step("Done.")
        detail("Load a dump into your local database with:")
        detail("  python scripts/echo.py restore-local")
    else:
        step("Done.")
    return 0
