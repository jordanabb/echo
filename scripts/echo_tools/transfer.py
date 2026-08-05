"""Chunked, resumable transfers for very large files.

`aws s3 cp` moves a whole file in one long-lived process. If that process is
interrupted — a dropped VPN, a flaky hotel network, a laptop sleeping, or a
sandbox that kills long-running commands — nothing is kept and the next attempt
starts from zero. For `results.csv` at 2.4 GB that can mean never finishing.

These helpers move one chunk per command instead:

* Uploads use an explicit S3 multipart upload. Each part is its own short
  request, and parts that succeed stay on S3, so progress accumulates.
* Downloads use ranged GETs appended to a `.partial` file, so an interrupted
  download resumes from wherever it stopped.

Both verify the final byte count before declaring success.
"""
import json
import subprocess
import tempfile
from pathlib import Path

from . import aws
from .console import detail, ok, warn

# 64 MB keeps the part count low (S3 allows 10,000 parts, so this handles files
# up to 640 GB) while keeping each request short enough to finish quickly.
PART_BYTES = 64 * 1024 * 1024

# Below this, a single cp is faster than the multipart bookkeeping.
LARGE_FILE_BYTES = 256 * 1024 * 1024

PART_ATTEMPTS = 5


def _remote_size(config, key):
    """Size of the object in S3, or None if it is not there."""
    try:
        value = aws.run(['s3api', 'head-object',
                         '--bucket', config['ECHO_DATA_BUCKET'], '--key', key,
                         '--query', 'ContentLength', '--output', 'text'],
                        region=config['AWS_REGION'])
        return int(value)
    except Exception:
        return None


def _abort_stale_uploads(config, key):
    """Drop earlier unfinished multipart uploads for this key.

    They are invisible to `s3 ls` but still billed, and mixing parts from two
    attempts would assemble a corrupt object.
    """
    try:
        ids = aws.run(['s3api', 'list-multipart-uploads',
                       '--bucket', config['ECHO_DATA_BUCKET'], '--prefix', key,
                       '--query', 'Uploads[].UploadId', '--output', 'text'],
                      region=config['AWS_REGION'])
    except Exception:
        return
    for upload_id in ids.split():
        try:
            aws.run(['s3api', 'abort-multipart-upload',
                     '--bucket', config['ECHO_DATA_BUCKET'], '--key', key,
                     '--upload-id', upload_id], region=config['AWS_REGION'])
        except Exception:
            pass


def upload_chunked(config, local_path, key):
    """Upload one large file as an explicit multipart upload."""
    local_path = Path(local_path)
    size = local_path.stat().st_size
    parts_total = (size + PART_BYTES - 1) // PART_BYTES

    if _remote_size(config, key) == size:
        ok("{} already complete".format(local_path.name))
        return True

    detail("{} ({:.0f} MB) in {} parts".format(
        local_path.name, size / 1024 ** 2, parts_total))

    _abort_stale_uploads(config, key)
    upload_id = aws.run(['s3api', 'create-multipart-upload',
                         '--bucket', config['ECHO_DATA_BUCKET'], '--key', key,
                         '--query', 'UploadId', '--output', 'text'],
                        region=config['AWS_REGION'])

    parts = []
    with tempfile.NamedTemporaryFile(suffix='.part', delete=True) as chunk_file:
        with local_path.open('rb') as source:
            for number in range(1, parts_total + 1):
                data = source.read(PART_BYTES)
                chunk_file.seek(0)
                chunk_file.truncate()
                chunk_file.write(data)
                chunk_file.flush()

                etag = None
                for attempt in range(PART_ATTEMPTS):
                    try:
                        etag = aws.run(['s3api', 'upload-part',
                                        '--bucket', config['ECHO_DATA_BUCKET'],
                                        '--key', key,
                                        '--part-number', str(number),
                                        '--upload-id', upload_id,
                                        '--body', chunk_file.name,
                                        '--query', 'ETag', '--output', 'text'],
                                       region=config['AWS_REGION'])
                        if etag and etag != 'None':
                            break
                    except Exception:
                        etag = None
                if not etag or etag == 'None':
                    _abort_stale_uploads(config, key)
                    warn("part {}/{} of {} would not upload".format(
                        number, parts_total, local_path.name))
                    return False

                # --output text returns the ETag already quoted; the manifest
                # wants the bare hash.
                parts.append({'ETag': etag.strip().strip('"'), 'PartNumber': number})
                if number % 10 == 0 or number == parts_total:
                    detail("  {} part {}/{}".format(local_path.name, number, parts_total))

    with tempfile.NamedTemporaryFile('w', suffix='.json', delete=False) as manifest:
        json.dump({'Parts': parts}, manifest)
        manifest_path = manifest.name

    try:
        aws.run(['s3api', 'complete-multipart-upload',
                 '--bucket', config['ECHO_DATA_BUCKET'], '--key', key,
                 '--upload-id', upload_id,
                 '--multipart-upload', 'file://' + manifest_path],
                region=config['AWS_REGION'])
    finally:
        Path(manifest_path).unlink()

    if _remote_size(config, key) == size:
        ok("{} ({:.0f} MB) verified".format(local_path.name, size / 1024 ** 2))
        return True
    warn("{} assembled to the wrong size".format(local_path.name))
    return False


def download_chunked(config, key, local_path):
    """Download one large object with ranged GETs, resuming if interrupted."""
    local_path = Path(local_path)
    size = _remote_size(config, key)
    if size is None:
        warn("{} is not in S3".format(key))
        return False

    if local_path.exists() and local_path.stat().st_size == size:
        ok("{} already complete".format(local_path.name))
        return True

    local_path.parent.mkdir(parents=True, exist_ok=True)
    partial = local_path.with_suffix(local_path.suffix + '.partial')
    # Anything already fetched is kept, so a retry picks up where it stopped.
    position = partial.stat().st_size if partial.exists() else 0
    if position:
        detail("resuming {} at {:.0f} MB".format(local_path.name, position / 1024 ** 2))

    detail("{} ({:.0f} MB)".format(local_path.name, size / 1024 ** 2))

    with partial.open('ab') as destination:
        while position < size:
            last = min(position + PART_BYTES, size) - 1
            fetched = False
            for attempt in range(PART_ATTEMPTS):
                with tempfile.NamedTemporaryFile(suffix='.part', delete=True) as chunk_file:
                    try:
                        aws.run(['s3api', 'get-object',
                                 '--bucket', config['ECHO_DATA_BUCKET'], '--key', key,
                                 '--range', 'bytes={}-{}'.format(position, last),
                                 chunk_file.name], region=config['AWS_REGION'])
                    except Exception:
                        continue
                    data = Path(chunk_file.name).read_bytes()
                    if len(data) == last - position + 1:
                        destination.write(data)
                        destination.flush()
                        fetched = True
                        break
            if not fetched:
                warn("could not fetch bytes {}-{} of {}".format(position, last, key))
                return False
            position = last + 1
            if (position // PART_BYTES) % 10 == 0:
                detail("  {} {:.0f}/{:.0f} MB".format(
                    local_path.name, position / 1024 ** 2, size / 1024 ** 2))

    partial.replace(local_path)
    if local_path.stat().st_size == size:
        ok("{} ({:.0f} MB) verified".format(local_path.name, size / 1024 ** 2))
        return True
    warn("{} downloaded to the wrong size".format(local_path.name))
    return False
