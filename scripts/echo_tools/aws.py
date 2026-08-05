"""Running AWS CLI commands, and getting an MFA session.

Credentials are written to a named AWS profile rather than exported as
environment variables. Exporting only works in the shell that ran the command,
which is awkward everywhere and impossible from Python; a profile persists,
survives closing the terminal, and behaves identically on Windows, macOS and
Linux.
"""
import os
import shutil
import subprocess

from .console import Abort, choose, die, say, step, ok, detail

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


def _mfa_help(account_hint=''):
    return ("Find it in the AWS console under\n"
            "  IAM > Users > (your user) > Security credentials > Multi-factor authentication\n"
            "It looks like arn:aws:iam::{}:mfa/<device-name>\n\n"
            "Then pass it explicitly:\n"
            "  python scripts/echo.py login --serial <arn>\n\n"
            "Or set it once so you never type it again:\n"
            "  MFA_SERIAL=<arn>   (an environment variable)"
            .format(account_hint or '<account-id>'))


def _find_mfa_serial(explicit=None):
    """Work out which MFA device to use.

    Order: an explicitly passed ARN, then the MFA_SERIAL environment variable,
    then whatever is registered against the calling user. Discovery is the happy
    path, but it can fail — the policy on this account denies most calls without
    an MFA token, and whether it carves out iam:ListMFADevices depends on how it
    was written. When discovery fails there must still be a way in, or the user
    is locked out of the one command that would unlock their account.
    """
    if explicit:
        return explicit
    if os.environ.get('MFA_SERIAL'):
        return os.environ['MFA_SERIAL']

    say("Looking up your MFA device...")
    try:
        listed = run(['iam', 'list-mfa-devices',
                      '--query', 'MFADevices[].SerialNumber', '--output', 'text'],
                     profile=None)
    except Abort:
        die("Could not look up your MFA device — the account denied the request.",
            "This is expected if the IAM policy does not allow iam:ListMFADevices\n"
            "before you have an MFA session.\n\n" + _mfa_help())

    devices = [d for d in listed.split() if d and d != 'None']

    if not devices:
        die("No MFA device is registered against your IAM user.",
            "Register one first, in the AWS console:\n"
            "  IAM > Users > (your user) > Security credentials > Assign MFA device\n"
            "  Choose 'Authenticator app', scan the QR code, then enter two\n"
            "  consecutive codes.\n\n"
            "Then run this command again.")

    if len(devices) == 1:
        return devices[0]

    # More than one device (a phone authenticator and a hardware key, say). Only
    # the one whose code is being typed will work, so it has to be chosen.
    return choose("You have several MFA devices — which are you using?", devices)


def login(serial=None):
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

    serial = _find_mfa_serial(serial)
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
