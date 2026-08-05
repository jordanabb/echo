# ECHO Dashboard — Why Each AWS Service

A short companion to [aws-infrastructure.md](aws-infrastructure.md) explaining *why* each AWS service was chosen, what it replaces, and the tradeoff accepted.

The overall design goal was **the smallest amount of infrastructure that meets the requirements** — every component is a fully-managed service so there are no servers to patch, scale, or monitor.

---

### S3 — Static asset hosting

The frontend compiles to a fully static bundle (HTML, JS, CSS, fonts, PDFs). S3 is the standard place to put static content on AWS: durable, effectively infinite capacity, billed per GB and per request at fractions of a cent, no servers to run.

**Alternatives considered:** EC2 + nginx (requires a server to manage), Amplify Hosting (more opinionated, harder to script deploys against).

**Tradeoff:** S3 alone doesn't terminate TLS or do edge caching, which is why CloudFront sits in front of it.

---

### CloudFront — CDN, TLS, and single entry point

The frontend is delivered globally, so CloudFront edge-caches the static bundle close to users. It also terminates TLS for the custom domains (`echodashboard.org`, `www.echodashboard.org`) using a free ACM certificate. A second behavior on `/api/*` proxies API traffic to the backend, which means external clients only need to know one hostname.

**Alternatives considered:** Cloudflare (would have worked, but means a second vendor for billing and DNS).

**Tradeoff:** Cache invalidations take 1–2 minutes to propagate, so changes aren't *instantly* visible. Acceptable for a dashboard that ships infrequently.

---

### App Runner — Backend runtime

The backend is a containerized FastAPI service. App Runner runs the container, terminates TLS, gives it a public URL, and autoscales on request volume — all without any task-definition or networking setup. It's a good fit for a low-to-moderate-traffic API where you'd rather not manage anything.

**Alternatives considered:**
- **EC2** — always-on cost; have to patch and monitor a server.
- **Lambda + API Gateway** — would require restructuring the FastAPI app, plus cold starts on a Python container with GDAL would be painful.
- **ECS on Fargate** — closest in spirit, but requires task definitions, target groups, an ALB, and IAM roles you don't need at this scale.

**Tradeoff:** App Runner is more expensive per active hour than a small EC2 instance and has fewer knobs (no VPC peering by default, no per-request billing). Acceptable for current traffic.

---

### RDS PostgreSQL — Database

PostgreSQL was chosen over MySQL / DynamoDB because the data is inherently relational (geographies, indicators, years, results all join heavily) and the dashboard runs analytical SQL with aggregates and pivots that suit Postgres well. Picking *RDS* over self-hosted Postgres gets automated backups (14-day point-in-time recovery), patching, and encrypted storage for free.

**Alternatives considered:**
- **DynamoDB** — wrong shape for joins and aggregations.
- **Aurora Serverless v2** — autoscaling Postgres-compatible DB, but more expensive at this size and adds cold-start delay.
- **Self-managed Postgres on EC2** — backups, failover, patching become your problem.

**Tradeoff:** A single instance (no Multi-AZ) means a brief outage if the AZ fails. Multi-AZ is a one-line change to enable later if needed.

---

### ECR Public — Container image registry

App Runner pulls its image from `public.ecr.aws/z3b9s2z7/echo-backend:latest`. The image isn't actually sensitive (it contains no secrets — those are injected as env vars at runtime), and using ECR Public means App Runner doesn't need an access role to pull, which keeps the IAM setup simpler.

**Alternatives considered:** Private ECR (would need an IAM role for App Runner to pull), Docker Hub (rate limits on free tier).

**Tradeoff:** The image is technically world-readable. Anyone who knows the URL can pull it. Since it contains no secrets and the source is essentially open, this is fine — but if proprietary code shipped in the image, this would need to move to private ECR.

---

### ACM — TLS certificates

Custom domains served by CloudFront need a TLS certificate. ACM issues these for free, auto-renews them, and integrates with CloudFront with one line of config.

**Alternatives considered:** None worth taking seriously — buying a cert and rotating it manually is strictly worse.

**Tradeoff:** None.

---

### CloudWatch Logs — Backend logs

App Runner automatically ships container stdout/stderr to CloudWatch. No setup required. Good enough for the volume of logs the backend produces; queryable via `aws logs tail` / filter expressions.

**Alternatives considered:** Datadog / Grafana Loki / etc. would give better dashboards and alerts, but are extra cost and complexity not currently justified.

**Tradeoff:** Built-in alerting via CloudWatch Alarms exists but isn't currently configured. Adding it is a small task if needed.

---

### IAM with enforced MFA — Access control

A single IAM user (`AbbottJ`) handles all administration, with an attached policy that denies most API calls unless the caller has a recent MFA token. This is appropriate for a one-engineer-managed project — adding role-based access (e.g. a dev role, a read-only role) is straightforward when the team grows.

**Alternatives considered:** AWS SSO / Identity Center would be the right answer for a team. Overkill for a single administrator.

**Tradeoff:** Day-to-day CLI use requires entering an MFA code to get a session token (12-hour lifetime). Mildly annoying but a good security default.
