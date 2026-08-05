"""Deploying the two tiers.

Both deploy by overwriting the live artifact — there is no staging environment.
Each command prints the equivalent raw commands before running, so anyone can
fall back to doing it by hand when something here misbehaves.
"""
import shutil
import subprocess
import time

from . import aws, indicators
from .config import FRONTEND_DIR, BACKEND_DIR, load_deploy_config
from .console import ask_yes_no, confirm, detail, die, ok, say, step, warn


def _run(command, cwd=None, what=None):
    """Run a non-AWS command, streaming its output so long builds show progress."""
    binary = shutil.which(command[0])
    if not binary:
        die("'{}' is not installed or not on your PATH.".format(command[0]),
            {'docker': "Install Docker Desktop: https://docs.docker.com/get-docker/",
             'pnpm': "npm install -g pnpm"}.get(command[0], "Install it and try again."))

    result = subprocess.run([binary] + command[1:], cwd=str(cwd) if cwd else None)
    if result.returncode != 0:
        die("{} failed.".format(what or command[0]),
            "The command's own output is above and usually says why.")


def deploy_backend(skip_checks=False):
    """Build, push, and roll out the FastAPI backend.

    App Runner does not redeploy when a new image is pushed
    (AutoDeploymentsEnabled is false), so the explicit start-deployment is what
    actually makes a change live — forgetting it is the classic mistake.
    """
    config = load_deploy_config('ECR_IMAGE', 'APPRUNNER_SERVICE_ARN')
    aws.require_session()

    image = "{}:latest".format(config['ECR_IMAGE'])
    service_arn = config['APPRUNNER_SERVICE_ARN']
    region = config['AWS_REGION']

    # The backend compiles indicator_config.py into the running service, so a
    # mismatch here ships a dashboard that silently omits data.
    if not skip_checks:
        step("Checking indicator config against the database first")
        try:
            if indicators.check_indicators() != 0:
                say()
                warn("The config and database disagree (details above).")
                if not ask_yes_no("Deploy anyway?", default=False):
                    die("Aborted — nothing was deployed.",
                        "Fix it with: python scripts/echo.py sync-indicators")
        except Exception as exc:  # a local DB being down must not block a deploy
            warn("Could not check indicators ({}).".format(exc))
            detail("Continuing — but confirm the config is right if you changed data.")

    say()
    step("About to deploy the backend to production")
    detail("image:   {}".format(image))
    detail("service: {}".format(service_arn.split('/')[-2] if '/' in service_arn else service_arn))
    detail("There is no staging environment; this replaces what is live.")
    confirm("Deploy the backend now?")

    step("1/4 Authenticating Docker against ECR Public")
    # ECR Public only answers in us-east-1, wherever else the stack may live.
    password = aws.run(['ecr-public', 'get-login-password'], region='us-east-1')
    login = subprocess.run(
        [shutil.which('docker') or 'docker', 'login', '--username', 'AWS',
         '--password-stdin', 'public.ecr.aws'],
        input=password, text=True, stdout=subprocess.PIPE, stderr=subprocess.STDOUT)
    if login.returncode != 0:
        die("docker login failed.\n\n{}".format(login.stdout),
            "Check Docker is running. If the AWS call failed, note that\n"
            "ecr-public also needs the sts:GetServiceBearerToken permission.")
    ok("Docker authenticated")

    step("2/4 Building the image")
    # App Runner runs amd64. On an arm64 machine this is emulated and slow; without
    # the flag the push succeeds and the container then fails to start with an
    # exec-format error that gives no hint about architecture.
    detail("Building for linux/amd64 (required by App Runner)")
    _run(['docker', 'build', '--platform', 'linux/amd64', '-t', image, '.'],
         cwd=BACKEND_DIR, what="docker build")
    ok("Image built")

    step("3/4 Pushing to ECR Public")
    _run(['docker', 'push', image], what="docker push")
    ok("Image pushed")

    step("4/4 Telling App Runner to pull it")
    aws.run(['apprunner', 'start-deployment', '--service-arn', service_arn], region=region)
    ok("Deployment started")

    step("Waiting for the service to come back")
    detail("Usually 3-5 minutes. Safe to interrupt — the rollout continues without you.")
    deadline = time.time() + 900
    while time.time() < deadline:
        time.sleep(20)
        status = aws.run(['apprunner', 'describe-service', '--service-arn', service_arn,
                          '--query', 'Service.Status', '--output', 'text'], region=region)
        detail("status: {}".format(status))
        if status == 'RUNNING':
            ok("Backend is live")
            say()
            detail("If something looks wrong, check the logs:")
            detail("  aws logs tail /aws/apprunner/echo-backend/<id>/application --follow")
            return 0
        if status in ('CREATE_FAILED', 'DELETE_FAILED', 'PAUSED'):
            die("App Runner reports status {}.".format(status),
                "Check the CloudWatch '.../service' log group for this deployment.")

    warn("Still not RUNNING after 15 minutes.")
    detail("Check the App Runner console; the rollout may still be in progress.")
    return 1


def deploy_frontend():
    """Build the SPA, upload it, and invalidate the CDN cache."""
    config = load_deploy_config('S3_FRONTEND_BUCKET', 'CLOUDFRONT_DISTRIBUTION_ID')
    aws.require_session()

    bucket = config['S3_FRONTEND_BUCKET']
    distribution = config['CLOUDFRONT_DISTRIBUTION_ID']
    region = config['AWS_REGION']

    step("About to deploy the frontend to production")
    detail("bucket:       s3://{}".format(bucket))
    detail("distribution: {}".format(distribution))
    detail("The upload uses --delete, and the bucket has no versioning:")
    detail("a bad build can only be undone by building again.")
    confirm("Deploy the frontend now?")

    step("1/3 Building")
    _run(['pnpm', 'build'], cwd=FRONTEND_DIR, what="pnpm build")
    build_dir = FRONTEND_DIR / 'build'
    if not build_dir.exists():
        die("pnpm build did not produce {}".format(build_dir),
            "Check the SvelteKit adapter configuration in apps/frontend/svelte.config.js")
    ok("Built into apps/frontend/build/")

    step("2/3 Uploading to S3")
    aws.run(['s3', 'sync', str(build_dir), "s3://{}".format(bucket), '--delete'],
            region=region, capture=False)
    ok("Uploaded")

    step("3/3 Invalidating CloudFront")
    # Without this, viewers keep getting the cached previous build and the deploy
    # looks like it silently did nothing.
    invalidation = aws.run(['cloudfront', 'create-invalidation',
                            '--distribution-id', distribution,
                            '--paths', '/*',
                            '--query', 'Invalidation.Id', '--output', 'text'],
                           region=region)
    ok("Invalidation {} created".format(invalidation))
    say()
    detail("Edge caches usually catch up within 1-2 minutes.")
    return 0
