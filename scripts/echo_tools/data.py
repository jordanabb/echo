"""Moving ETL inputs and dumps between S3 and this machine.

The raw inputs and generated intermediates are far too large for git —
results.csv alone is about 2.5 GB — so S3 holds the shared copy. Without this,
a new machine cannot rebuild the dataset at all.
"""
from . import aws, transfer
from .config import (CLEAN_DATA_DIR, DUMPS_DIR, RAW_DATA_DIR, S3_CLEAN_PREFIX,
                     S3_DUMP_PREFIX, S3_RAW_PREFIX, load_deploy_config)
from .console import bad, detail, die, ok, say, step, warn

# What each name covers: local directory, S3 prefix, description.
PARTS = {
    'raw':   (RAW_DATA_DIR,   S3_RAW_PREFIX,   "raw source CSVs (ECHO REVAMP)"),
    'clean': (CLEAN_DATA_DIR, S3_CLEAN_PREFIX, "generated intermediates (clean_output_national)"),
    'dumps': (DUMPS_DIR,      S3_DUMP_PREFIX,  "database dumps"),
}


def _local_inventory(local_dir):
    """{relative path: size} for everything under local_dir."""
    inventory = {}
    for path in local_dir.rglob('*'):
        if path.is_file():
            inventory[path.relative_to(local_dir).as_posix()] = path.stat().st_size
    return inventory


def _remote_inventory(config, prefix):
    """{key below prefix: size} for everything in S3 under prefix."""
    listing = aws.run(['s3', 'ls', "s3://{}/{}/".format(config['ECHO_DATA_BUCKET'], prefix),
                       '--recursive'], region=config['AWS_REGION'])
    inventory = {}
    for line in listing.splitlines():
        parts = line.split(None, 3)
        if len(parts) == 4 and parts[2].isdigit():
            key = parts[3]
            if key.startswith(prefix + '/'):
                inventory[key[len(prefix) + 1:]] = int(parts[2])
    return inventory


def _verify(config, local_dir, prefix, description, direction):
    """Confirm the transfer actually finished.

    `aws s3 sync` has been observed exiting 0 with files still outstanding, so
    the exit code alone is not evidence of success. Comparing both sides is —
    and a half-copied dataset that reports success is worse than a loud failure,
    because it gets discovered much later.
    """
    local = _local_inventory(local_dir)
    remote = _remote_inventory(config, prefix)

    # Whichever side is the destination must end up with everything the source
    # has; sizes must match on both.
    source, dest = (remote, local) if direction == 'pull' else (local, remote)
    missing = sorted(set(source) - set(dest))
    truncated = sorted(name for name in set(source) & set(dest)
                       if source[name] != dest[name])

    outstanding = sorted(set(missing) | set(truncated))
    if not outstanding:
        ok("verified: {} files, {:.1f} GB on both sides".format(
            len(source), sum(source.values()) / 1024 ** 3))
        return []

    where = 'this machine' if direction == 'pull' else 'S3'
    bad("{} did NOT transfer completely".format(description))
    if missing:
        detail("{} file(s) missing from {}:".format(len(missing), where))
        for name in missing[:10]:
            detail("  {} ({:.0f} MB)".format(name, source[name] / 1024 ** 2))
        if len(missing) > 10:
            detail("  ... and {} more".format(len(missing) - 10))
    if truncated:
        detail("{} file(s) differ in size:".format(len(truncated)))
        for name in truncated[:10]:
            detail("  {} (local {}, remote {})".format(name, local[name], remote[name]))

    # Report each outstanding file with the size it should be, so the caller can
    # decide which need the chunked path.
    return [(name, source[name]) for name in outstanding]


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

    # --only-show-errors is not cosmetic: the default per-megabyte progress
    # output floods the pipe on multi-GB transfers and can get the process
    # torn down mid-copy. Completion is confirmed by _verify() instead.
    args = ['s3', 'sync', source, destination, '--only-show-errors']
    if dry_run:
        args.append('--dryrun')
    # Deliberately no --delete: a sync must never remove something another
    # machine still depends on. Prune S3 by hand if it genuinely needs it.
    aws.run(args, region=config['AWS_REGION'], capture=False)

    if dry_run:
        return True

    # Re-run until both sides agree. `s3 sync` only moves what is missing, so
    # each pass is cheaper than the last.
    #
    # Anything large that is still outstanding goes through the chunked path
    # instead: `s3 sync` transfers a file in one long-lived operation, so an
    # interruption discards all of it and the next pass starts that file from
    # zero. A multi-GB file on a slow or unreliable link may never finish that
    # way, however many times it is retried.
    attempts = 4
    for attempt in range(attempts):
        outstanding = _verify(config, local_dir, prefix, description, direction)
        if not outstanding:
            return True
        if attempt == attempts - 1:
            break

        large = [(name, size) for name, size in outstanding
                 if size >= transfer.LARGE_FILE_BYTES]
        small = [name for name, size in outstanding
                 if size < transfer.LARGE_FILE_BYTES]

        if large:
            step("Transferring {} large file(s) in chunks".format(len(large)))
            detail("Chunked transfers resume instead of restarting.")
            for name, _size in large:
                key = "{}/{}".format(prefix, name)
                target = local_dir / name
                if direction == 'pull':
                    transfer.download_chunked(config, key, target)
                else:
                    transfer.upload_chunked(config, target, key)

        if small:
            warn("Retrying {} smaller file(s) (pass {} of {})".format(
                len(small), attempt + 2, attempts))
            aws.run(args, region=config['AWS_REGION'], capture=False)

    die("{} is still incomplete.".format(description),
        "Re-run this command — it resumes, so repeated runs make progress even\n"
        "on a slow or unreliable connection.")


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
