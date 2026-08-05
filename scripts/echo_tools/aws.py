"""Running AWS CLI commands, and getting an MFA session.

Credentials are written to a named AWS profile rather than exported as
environment variables. Exporting only works in the shell that ran the command,
which is awkward everywhere and impossible from Python; a profile persists,
survives closing the terminal, and behaves identically on Windows, macOS and
Linux.
"""
import shutil
import subprocess

from .console import die, say, step, ok, detail

# Where `login` stores the temporary session credentials.
PROFILE = 'echo-mfa'

# Maximum lifetime of an IAM user session token.
SESSION_SECONDS = 43200  # 12 hours


def _aws_binary():
    found = shutil.which('aws')
    if not found:
        die("The AWS CLI is not installed (no 'aws' on PATH).",
            "Install it: https://aws.amazon.com/cli/\n"
            "On Windows, use the MSI installer and reopen your terminal afterwards.")
    return found


def run(args, profile=PROFILE, capture=True, check=True, region=None):
    """Run an `aws` subcommand.

    Returns stdout as a string when capturing. Raises Abort with the CLI's own
    stderr on failure, since that message is usually the most useful thing
    available.
    """
    command = [_aws_binary()] + list(args)
    if profile:
        command += ['--profile', profile]
    if region:
        command += ['--region', region]

    result = subprocess.run(
        command,
        stdout=subprocess.PIPE if capture else None,
        stderr=subprocess.PIPE,
        text=True,
    )

    if check and result.returncode != 0:
        message = (result.stderr or '').strip() or "aws exited {}".format(result.returncode)
        fix = None
        lowered = message.lower()
        if 'explicit deny' in lowered or 'accessdenied' in lowered:
            fix = ("This account denies almost every call without a recent MFA token.\n"
                   "  python scripts/echo.py login\n\n"
                   "If you are already logged in, your IAM user may not have permission\n"
                   "for this action — check with whoever administers the account.")
        elif 'expiredtoken' in lowered or 'security token' in lowered:
            fix = "Your 12-hour session has expired:\n  python scripts/echo.py login"
        elif 'could not be found' in lowered and 'profile' in lowered:
            fix = "No '{}' profile yet:\n  python scripts/echo.py login".format(PROFILE)
        die("AWS command failed: aws {}\n\n{}".format(' '.join(args[:3]), message), fix)

    return (result.stdout or '').strip() if capture else ''


def current_identity(profile=PROFILE):
    """Return the caller's ARN, or None if the profile has no usable session."""
    try:
        return run(['sts', 'get-caller-identity', '--query', 'Arn', '--output', 'text'],
                   profile=profile)
    except Exception:
        return None


def require_session():
    """Stop early unless an MFA session exists.

    Without this a long operation can fail at its final step, after a multi-GB
    upload or a ten-minute image build.
    """
    if not current_identity():
        die("No active AWS session.",
            "python scripts/echo.py login\n\n"
            "This prompts for your MFA code and sets up a 12-hour session.")


def login():
    """Exchange an MFA code for a 12-hour session stored in the PROFILE."""
    step("Signing in to AWS")

    # get-session-token must be called with the long-term credentials, so use the
    # default profile here rather than the session profile we are about to write.
    identity = current_identity(profile=None)
    if not identity:
        die("No base AWS credentials found.",
            "Configure your access key first:\n"
            "  aws configure\n\n"
            "Use the access key ID and secret for your own IAM user.")
    ok("Base credentials belong to {}".format(identity))

    serial = run(['iam', 'list-mfa-devices',
                  '--query', 'MFADevices[0].SerialNumber', '--output', 'text'],
                 profile=None)

    if not serial or serial == 'None':
        die("Your IAM user has no MFA device registered.",
            "Register one in the AWS console:\n"
            "  IAM > Users > (your user) > Security credentials > Assign MFA device\n\n"
            "Then run this command again.")
    ok("MFA device {}".format(serial))

    code = input("Enter the current 6-digit MFA code: ").strip()
    if not (code.isdigit() and len(code) == 6):
        die("Expected exactly 6 digits.")

    fields = run(['sts', 'get-session-token',
                  '--serial-number', serial,
                  '--token-code', code,
                  '--duration-seconds', str(SESSION_SECONDS),
                  '--query', 'Credentials.[AccessKeyId,SecretAccessKey,SessionToken,Expiration]',
                  '--output', 'text'],
                 profile=None).split()

    if len(fields) != 4:
        die("Unexpected response from AWS while requesting a session token.",
            "MFA codes expire after about 30 seconds. Wait for the next one and retry.")

    access_key, secret_key, token, expires = fields

    step("Storing session in the '{}' profile".format(PROFILE))
    for key, value in (('aws_access_key_id', access_key),
                       ('aws_secret_access_key', secret_key),
                       ('aws_session_token', token)):
        run(['configure', 'set', key, value, '--profile', PROFILE], profile=None)

    ok("Signed in until {}".format(expires))
    say()
    detail("Every other echo.py command uses this profile automatically.")
    detail("To use it with the AWS CLI directly, add: --profile {}".format(PROFILE))
