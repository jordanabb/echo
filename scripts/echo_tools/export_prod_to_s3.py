"""Export geographies.csv / results.csv from production and publish them to S3.

Reads the live tables, writes CSVs in the same column layout create_national.py
produces, checks them against the database, then uploads them to the 'clean'
prefix. Read-only against the database. The previous S3 copies are kept under
'<clean prefix>_prev/' so they are not pulled by `pull-data clean`.
"""
import os
import pathlib

from dotenv import find_dotenv, load_dotenv
from sqlalchemy import create_engine, text
from sqlalchemy.engine import URL

from . import aws, transfer
from .config import CLEAN_DATA_DIR, S3_CLEAN_PREFIX, load_deploy_config
from .console import detail, die, ok, say, step, warn

# Same columns, same order as create_national.py writes, so load_data_to_db.py
# and merge_year.py accept the export unchanged. geo_level is cast to text in
# case production stores it as an enum.
EXPORTS = {
    'geographies.csv': (
        "SELECT geo_id, geo_name, geo_level::text AS geo_level, year FROM geographies",
        "SELECT COUNT(*) FROM geographies"),
    'results.csv': (
        "SELECT geo_id, geo_level::text AS geo_level, year, indicator_id, value FROM results_data",
        "SELECT COUNT(*) FROM results_data"),
}


def _engine():
    """Build an engine from .env, the same variables the ETL scripts use."""
    load_dotenv(find_dotenv(usecwd=True))
    names = ['DB_USER', 'DB_PASSWORD', 'DB_HOST', 'DB_PORT', 'DB_NAME']
    values = {n: os.getenv(n) for n in names}
    missing = [n for n, v in values.items() if not v]
    if missing:
        die("Missing {} in .env".format(', '.join(missing)),
            "Check that .env is in the project root and defines these variables.")
    url = URL.create('postgresql', username=values['DB_USER'],
                     password=values['DB_PASSWORD'], host=values['DB_HOST'],
                     port=int(values['DB_PORT']), database=values['DB_NAME'])
    engine = create_engine(url, connect_args={
        'keepalives': 1, 'keepalives_idle': 30,
        'keepalives_interval': 10, 'keepalives_count': 5})
    return engine, url


def _count_data_rows(path):
    """Line count minus the header, read in big blocks so 2.5 GB is fine."""
    lines = 0
    with open(path, 'rb') as f:
        for block in iter(lambda: f.read(1 << 24), b''):
            lines += block.count(b'\n')
    return lines - 1


def _export_table(engine, name, query, count_query, out_dir):
    final = out_dir / name
    part = out_dir / (name + '.part')

    # REPEATABLE READ: the count and the COPY see the same snapshot, so a load
    # running in the background cannot make them disagree.
    with engine.connect().execution_options(isolation_level="REPEATABLE READ") as conn:
        expected = conn.execute(text(count_query)).scalar()
        step("{}: {:,} rows in production, exporting".format(name, expected))
        cur = conn.connection.cursor()
        with open(part, 'w', newline='', encoding='utf-8') as f:
            cur.copy_expert("COPY ({}) TO STDOUT WITH (FORMAT csv, HEADER true)".format(query), f)

    actual = _count_data_rows(part)
    if actual != expected:
        part.unlink()
        die("{}: wrote {:,} rows but production has {:,}. Nothing was kept.".format(
            name, actual, expected),
            "A text field containing a line break would cause this. Tell whoever "
            "maintains the script; the export is not safe to use as-is.")
    os.replace(part, final)    # only a verified file ever gets the real name
    ok("{}: verified {:,} rows, {:.2f} GB".format(name, actual, final.stat().st_size / 1024 ** 3))
    return final


def _remote_size(config, key):
    """Size of one object in S3, or None."""
    listing = aws.run(['s3', 'ls', "s3://{}/{}".format(config['ECHO_DATA_BUCKET'], key)],
                      region=config['AWS_REGION'])
    for line in listing.splitlines():
        parts = line.split(None, 3)
        if len(parts) == 4 and parts[3] == key.rsplit('/', 1)[-1] and parts[2].isdigit():
            return int(parts[2])
    return None


def _upload(config, path):
    bucket = config['ECHO_DATA_BUCKET']
    key = "{}/{}".format(S3_CLEAN_PREFIX, path.name)
    uri = "s3://{}/{}".format(bucket, key)
    local_size = path.stat().st_size

    # Keep whatever S3 had. A sibling prefix, NOT clean/, so pull-data never fetches it.
    if _remote_size(config, key) is not None:
        prev = "s3://{}/{}_prev/{}".format(bucket, S3_CLEAN_PREFIX, path.name)
        detail("Keeping the current S3 copy at {}".format(prev))
        aws.run(['s3', 'cp', uri, prev, '--only-show-errors'],
                region=config['AWS_REGION'], capture=False)

    step("Uploading {}".format(path.name))
    detail("{}  ->  {}".format(path, uri))
    if local_size >= transfer.LARGE_FILE_BYTES:
        transfer.upload_chunked(config, path, key)     # resumes if the link drops
    else:
        aws.run(['s3', 'cp', str(path), uri, '--only-show-errors'],
                region=config['AWS_REGION'], capture=False)

    uploaded = _remote_size(config, key)
    if uploaded != local_size:
        die("{}: S3 has {} bytes, expected {}.".format(path.name, uploaded, local_size),
            "Re-run this command; the chunked upload resumes.")
    ok("{}: verified in S3 ({:.2f} GB)".format(path.name, local_size / 1024 ** 3))


# Short names for the --geographies-only / --results-only flags.
PARTS = {'geographies': 'geographies.csv', 'results': 'results.csv'}


def run(dry_run=False, upload=True, out_dir=None, only=None):
    """Export from production. `only` is None (both files), 'geographies' or 'results'."""
    if only is not None and only not in PARTS:
        die("Unknown part '{}'.".format(only), "Choose geographies or results.")
    exports = {name: EXPORTS[name] for name in
               ([PARTS[only]] if only else EXPORTS)}

    engine, url = _engine()
    say()
    step("Exporting FROM this database:")
    detail("host: {}".format(url.host))
    detail("name: {}".format(url.database))
    detail("files: {}".format(', '.join(exports)))

    if dry_run:
        with engine.connect() as conn:
            for name, (_, count_query) in exports.items():
                detail("{}: {:,} rows".format(name, conn.execute(text(count_query)).scalar()))
        warn("Dry run - nothing written.")
        return 0

    config = None
    if upload:
        config = load_deploy_config('ECHO_DATA_BUCKET')
        aws.require_session()          # fail now, not after a 2.5 GB export
        warn("This will REPLACE the shared {} in S3.".format(' and '.join(exports)))
    if input("Type the database name to continue: ").strip() != url.database:
        die("Cancelled.", "Run the command again and type the database name exactly.")

    out = pathlib.Path(out_dir) if out_dir else CLEAN_DATA_DIR.parent / 'prod_export'
    out.mkdir(parents=True, exist_ok=True)
    files = [_export_table(engine, n, q, c, out) for n, (q, c) in exports.items()]

    if not upload:
        step("Exported to {} (S3 untouched).".format(out))
        return 0
    for path in files:
        _upload(config, path)
    step("Done. S3 'clean' now has {} from production.".format(' and '.join(exports)))
    return 0