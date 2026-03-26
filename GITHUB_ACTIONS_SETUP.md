# GitHub Actions Setup for IT Team

This document explains what the IT team needs to configure **ONE TIME** to enable automated deployments. Once configured, developers can deploy changes by simply pushing code to the `main` branch.

## Overview

GitHub Actions will automatically:
1. Build Docker images for frontend and backend
2. Push images to Amazon ECR
3. Deploy updated images to ECS Fargate
4. Wait for deployment to stabilize

**No manual intervention needed for routine deployments after initial setup.**

---

## Prerequisites

Before configuring GitHub Actions, ensure:
- ✅ AWS infrastructure is deployed (ECS cluster, ECR repositories, RDS, ALB)
- ✅ ECS services are running
- ✅ ECR repositories exist: `echo-backend` and `echo-frontend`

---

## Step 1: Create IAM User for GitHub Actions

Create a dedicated IAM user with **programmatic access only** (no console access).

### 1.1 Create IAM User

```bash
aws iam create-user --user-name github-actions-echo-deploy
```

### 1.2 Create IAM Policy

Create a policy file `github-actions-policy.json`:

```json
{
  "Version": "2012-10-17",
  "Statement": [
    {
      "Sid": "ECRPushPull",
      "Effect": "Allow",
      "Action": [
        "ecr:GetAuthorizationToken",
        "ecr:BatchCheckLayerAvailability",
        "ecr:GetDownloadUrlForLayer",
        "ecr:BatchGetImage",
        "ecr:PutImage",
        "ecr:InitiateLayerUpload",
        "ecr:UploadLayerPart",
        "ecr:CompleteLayerUpload"
      ],
      "Resource": "*"
    },
    {
      "Sid": "ECSDeployment",
      "Effect": "Allow",
      "Action": [
        "ecs:UpdateService",
        "ecs:DescribeServices",
        "ecs:DescribeTasks",
        "ecs:ListTasks"
      ],
      "Resource": [
        "arn:aws:ecs:*:*:service/echo-cluster/echo-backend",
        "arn:aws:ecs:*:*:service/echo-cluster/echo-frontend"
      ]
    },
    {
      "Sid": "ECSTaskDefinition",
      "Effect": "Allow",
      "Action": [
        "ecs:DescribeTaskDefinition",
        "ecs:RegisterTaskDefinition"
      ],
      "Resource": "*"
    },
    {
      "Sid": "PassRole",
      "Effect": "Allow",
      "Action": "iam:PassRole",
      "Resource": "arn:aws:iam::*:role/ecsTaskExecutionRole"
    }
  ]
}
```

### 1.3 Attach Policy to User

```bash
# Create the policy
aws iam create-policy \
  --policy-name GitHubActionsECHODeployPolicy \
  --policy-document file://github-actions-policy.json

# Attach to user (replace ACCOUNT_ID with your AWS account ID)
aws iam attach-user-policy \
  --user-name github-actions-echo-deploy \
  --policy-arn arn:aws:iam::ACCOUNT_ID:policies/GitHubActionsECHODeployPolicy
```

### 1.4 Create Access Keys

```bash
aws iam create-access-key --user-name github-actions-echo-deploy
```

**Save the output!** You'll need:
- `AccessKeyId`
- `SecretAccessKey`

⚠️ **Security Note:** These credentials will **never be shown again**. Store them securely.

---

## Step 2: Configure GitHub Secrets

GitHub Secrets store sensitive credentials securely. Developers cannot view secret values, only use them in workflows.

### 2.1 Navigate to Repository Settings

1. Go to: `https://github.com/[your-org]/[your-repo]/settings/secrets/actions`
2. Click **"New repository secret"**

### 2.2 Add Required Secrets

Add the following secrets:

| Secret Name | Value | Description |
|------------|-------|-------------|
| `AWS_ACCESS_KEY_ID` | `AKIA...` | Access key from Step 1.4 |
| `AWS_SECRET_ACCESS_KEY` | `wJalr...` | Secret key from Step 1.4 |

### 2.3 Verify Secrets

After adding, you should see:
- ✅ `AWS_ACCESS_KEY_ID`
- ✅ `AWS_SECRET_ACCESS_KEY`

---

## Step 3: Update Workflow Configuration

The workflow file [.github/workflows/deploy.yml](.github/workflows/deploy.yml) needs to be updated with your AWS-specific values.

### 3.1 Update Environment Variables

Edit [.github/workflows/deploy.yml](.github/workflows/deploy.yml) and update:

```yaml
env:
  AWS_REGION: us-east-1              # ← Update with your region (e.g., us-west-2)
  ECR_REPOSITORY_BACKEND: echo-backend    # ← Update if you named it differently
  ECR_REPOSITORY_FRONTEND: echo-frontend  # ← Update if you named it differently
  ECS_CLUSTER: echo-cluster               # ← Update if you named it differently
  ECS_SERVICE_BACKEND: echo-backend       # ← Update if you named it differently
  ECS_SERVICE_FRONTEND: echo-frontend     # ← Update if you named it differently
```

### 3.2 Commit and Push Changes

```bash
git add .github/workflows/deploy.yml
git commit -m "Configure GitHub Actions deployment workflow"
git push origin main
```

---

## Step 4: Test the Deployment

### 4.1 Trigger Initial Deployment

Push any change to the `main` branch to trigger the workflow:

```bash
# Make a small change
echo "# Test" >> README.md
git add README.md
git commit -m "Test GitHub Actions deployment"
git push origin main
```

### 4.2 Monitor Workflow

1. Go to: `https://github.com/[your-org]/[your-repo]/actions`
2. Click on the running workflow
3. Watch the deployment progress

### 4.3 Verify Deployment

**Expected workflow steps:**
1. ✅ Checkout code
2. ✅ Configure AWS credentials
3. ✅ Login to ECR
4. ✅ Build backend Docker image
5. ✅ Push backend image to ECR
6. ✅ Build frontend Docker image
7. ✅ Push frontend image to ECR
8. ✅ Deploy backend to ECS
9. ✅ Deploy frontend to ECS
10. ✅ Wait for services to stabilize

**Verify in AWS:**
```bash
# Check ECS service deployments
aws ecs describe-services \
  --cluster echo-cluster \
  --services echo-backend echo-frontend
```

---

## Step 5: Grant Developer Access (Optional)

If developers need to manually trigger deployments or view workflow runs:

### 5.1 Repository Permissions

Ensure developers have **Write** access to the repository (not just Read).

### 5.2 Manual Workflow Trigger

Developers can manually trigger deployments via GitHub UI:
1. Go to **Actions** tab
2. Select **"Deploy to AWS ECS"** workflow
3. Click **"Run workflow"**
4. Select `main` branch
5. Click **"Run workflow"**

---

## Ongoing Operations

### Developer Workflow (After Setup)

Once configured, developers simply:

```bash
# Make code changes
git add .
git commit -m "Add new feature"
git push origin main
# ← Deployment happens automatically!
```

**Changes go live in 5-10 minutes** (build + deploy time).

### Monitoring Deployments

**GitHub Actions:**
- View workflow runs: `https://github.com/[your-org]/[your-repo]/actions`
- Check logs for each step
- Receive notifications on failures

**AWS CloudWatch:**
- View ECS deployment events
- Monitor container logs
- Set up alarms for failures

### Rollback Procedure

If a deployment causes issues:

**Option 1: Revert the code**
```bash
git revert HEAD
git push origin main
# ← New deployment with previous code
```

**Option 2: Manual ECS rollback**
```bash
# Find previous task definition
aws ecs describe-services --cluster echo-cluster --services echo-backend

# Update to previous task definition
aws ecs update-service \
  --cluster echo-cluster \
  --service echo-backend \
  --task-definition echo-backend:PREVIOUS_REVISION
```

---

## Troubleshooting

### Workflow fails at "Configure AWS credentials"

**Error:** `User: arn:aws:iam::ACCOUNT_ID:user/github-actions-echo-deploy is not authorized`

**Fix:** Verify IAM policy is attached correctly:
```bash
aws iam list-attached-user-policies --user-name github-actions-echo-deploy
```

### Workflow fails at "Push image to ECR"

**Error:** `denied: User is not authorized to perform ecr:PutImage`

**Fix:** Ensure ECR repositories exist and IAM policy allows ECR actions:
```bash
aws ecr describe-repositories --repository-names echo-backend echo-frontend
```

### Workflow succeeds but changes don't appear

**Possible causes:**
1. Browser cache - Hard refresh (Ctrl+Shift+R)
2. CloudFront cache - Invalidate distribution
3. ECS deployment still in progress - Check AWS console

**Check ECS deployment status:**
```bash
aws ecs describe-services \
  --cluster echo-cluster \
  --services echo-backend echo-frontend \
  --query 'services[*].[serviceName,deployments]'
```

### Workflow times out

**Default timeout:** 30 minutes

If deployments consistently take longer:
1. Check ECS task health checks
2. Review CloudWatch logs for startup errors
3. Increase timeout in workflow (add `timeout-minutes: 60` to job)

---

## Security Best Practices

✅ **Do:**
- Rotate IAM access keys every 90 days
- Monitor CloudTrail for API calls from GitHub Actions user
- Use branch protection rules on `main` branch
- Enable MFA for repository administrators
- Review workflow logs for sensitive data leaks

❌ **Don't:**
- Share AWS credentials in code or commit messages
- Give GitHub Actions user more permissions than needed
- Allow force pushes to `main` branch
- Commit `.env` files with production secrets

---

## Summary Checklist

Use this checklist to verify everything is configured:

- [ ] IAM user `github-actions-echo-deploy` created
- [ ] IAM policy attached with ECR and ECS permissions
- [ ] Access keys generated and saved securely
- [ ] GitHub secret `AWS_ACCESS_KEY_ID` added
- [ ] GitHub secret `AWS_SECRET_ACCESS_KEY` added
- [ ] Workflow file updated with correct AWS region and resource names
- [ ] Workflow file committed to `main` branch
- [ ] Test deployment triggered and successful
- [ ] Changes visible on production dashboard
- [ ] Developer team notified of new workflow

---

## Questions or Issues?

If you encounter problems during setup:

1. Check the GitHub Actions workflow logs first
2. Review AWS CloudWatch logs for ECS tasks
3. Verify IAM permissions using AWS Policy Simulator
4. Consult [DEPLOYMENT.md](DEPLOYMENT.md) for AWS infrastructure details

**For GitHub Actions specific issues:**
- GitHub Actions documentation: https://docs.github.com/en/actions
- AWS Actions for GitHub: https://github.com/aws-actions
