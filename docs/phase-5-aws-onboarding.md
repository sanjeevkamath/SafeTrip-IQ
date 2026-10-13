# Phase 5 AWS onboarding

This is the single-account, low-cost deployment path for SafeTrip IQ. Use `us-east-2` for project resources. The current production website stays on Vercel; the hosted PostgreSQL database stays outside AWS initially. The Python worker is the first AWS workload. Both manual AWS benchmark sizes have now completed successfully using the pinned S3 checkpoint. The owner selected 1 vCPU / 2 GiB, running once a week, on October 13, 2026. Production database integration, delivery, monitoring, and scheduling remain; no schedule is enabled.

## What each service does

```text
Visitor -> Vercel/Next.js -> hosted PostgreSQL (read-only app role)
EventBridge Scheduler -> ECS Fargate one-off task -> hosted PostgreSQL (scoped writer role)
                                         |-> ECR worker image
                                         |-> S3 versioned model artifact
                                         |-> Secrets Manager database URL
                                         |-> CloudWatch logs
GitHub Actions -> OIDC IAM role -> ECR + ECS/Terraform deployment
```

- **AWS account and Region:** the account is the billing/security boundary; `us-east-2` is where regional resources live. IAM and billing are account-wide.
- **IAM:** defines who can act. Use a human identity for the console, a GitHub OIDC role for deployment, an ECS execution role for image/log/secret startup, and a separate ECS task role for only the runtime AWS calls the worker needs. None should use root keys.
- **VPC, subnet, route, security group:** the network. A one-off task can use a public subnet with a public IP for outbound ECR/S3/hosted-Postgres access and a security group with no inbound rules. This avoids an always-on NAT gateway. A public IP alone does not make an inbound service available when inbound traffic is blocked.
- **ECR:** stores immutable versions of the Docker worker image. It does not run the image.
- **S3:** stores the checksum-verified, versioned BERT model files separately from the image. S3 does not execute the model.
- **ECS on Fargate:** starts an isolated container for a refresh, gives it a chosen CPU/memory size, and stops billing for compute when that task ends. It is a scheduled *task*, not an always-running web service.
- **EventBridge Scheduler:** starts the task on a schedule after manual runs have succeeded.
- **Secrets Manager:** holds the PostgreSQL writer connection string. It must never go into GitHub, the Docker image, or frontend environment variables.
- **CloudWatch:** collects bounded task logs and alarms. Database refresh-history/freshness checks prove whether publication succeeded; a launched task is insufficient.
- **Terraform:** records the AWS infrastructure and IAM policies as reviewable code. Protect its state, because state may contain sensitive values.
- **GitHub Actions OIDC:** exchanges a short-lived GitHub identity for an AWS role restricted to this repository and deployment branch/environment; no long-lived AWS access key is stored in GitHub.

## Account foundation before deploying

1. In the AWS Console, confirm whether the account is on the Free or Paid plan, the remaining credit amount, and each credit's expiration date under **Billing and Cost Management > Credits**. Record those dates locally. Do not create an AWS Organization just to set up this project: current AWS Free Tier terms say joining/creating one can end credit eligibility or change the account plan.
2. Protect the governing sign-in identity with MFA and avoid root access keys. The owner reports that this account is accessed through a Builder ID-managed project console rather than independent root credentials; MFA has been enabled on Builder ID. CloudShell reports an assumed `AccountFullAccessRole`. Verify the managed account's permissions and supported access paths before adding IAM identities. For a future standalone account, secure its root identity separately and use a non-root identity for ordinary work.
3. Create a monthly AWS Budget for **gross, unblended cost**, excluding credits so usage remains visible while credits absorb the bill. Start with a small threshold (for example $10) and alerts at 50%, 80%, and 100%. Also monitor remaining credit and expiration on the Billing page. A budget is an alert, not a spending cap, and its data may lag.
4. In the console choose `us-east-2`, open **CloudShell**, and run:

   ```sh
   aws sts get-caller-identity --query Arn --output text
   aws configure get region
   aws ecs list-clusters --region us-east-2 --query 'clusterArns' --output json
   ```

   The first command should show the day-to-day IAM identity, not `:root`. The last command only lists clusters; it creates nothing. Do not paste credentials, access keys, or database URLs into chat or commits. The account ID within an ARN is not itself a secret, but redact it when sharing output.

   Verified on October 12, 2026: CloudShell showed an assumed `AccountFullAccessRole`, and ECS returned an empty cluster list in `us-east-2`. These results verify a usable temporary AWS identity and that no cluster exists there yet; they do not establish the role's exact permissions, the account plan, budget state, or resource inventory in other Regions.

   The owner has confirmed the account plan, active credits, and gross-cost budget alerts. Keep credit balances, expiration dates, notification addresses, and account identifiers in private notes rather than this public repository. Review both gross usage and remaining credits while the project runs.
5. For local development, install AWS CLI v2 and Terraform only when we start using them. CloudShell already has the AWS CLI and is enough for the first read-only checks. The later local CLI access method should use temporary credentials; avoid creating a root access key or committing `~/.aws`.

## Build order

1. **Size and estimate:** use the existing local benchmark as a starting point, then price a short Fargate test in `us-east-2`. The current full-advisory run was measured on an emulated Linux amd64 container on a Mac; AWS native performance and image/model transfer still need measurement. Its 2-CPU/2-GiB Docker limit is **not** a valid Fargate task size: test either 1 vCPU/2 GiB or 2 vCPU/4 GiB and compare total cost and completion time.
2. **Infrastructure:** create a small Terraform stack for ECR, a private S3 model bucket, ECS cluster/task definition, CloudWatch log group, least-privilege IAM roles, and a secret reference. Add state storage with encryption, versioning, and locking before collaborative CI deployment. Keep the schedule disabled.
3. **Model delivery:** package the six verified model files, upload the archive to a versioned S3 bucket, and pin both its object VersionId and archive SHA-256. At task startup, the worker checks that archive and every extracted file against `docs/baseline/artifacts.json` before inference. Implementation, local measurements, and both completed native AWS runs are documented in `docs/phase-5-manual-benchmark.md`; model delivery took 6.689 and 1.732 seconds in the two single AWS observations.
4. **Manual run:** publish an immutable worker image to ECR, launch a read-only or fixture-based ECS run first, inspect CloudWatch, runtime, peak memory, and exit status. Then test a trusted write against an isolated database before any production publication.
5. **Delivery:** add GitHub OIDC with a trust policy limited to this repository and a deployment environment/branch. Have CI test, build once, push by digest, and deploy the digest. Run database migrations separately and compatibly before worker release.
6. **Schedule and observe:** enable a once-weekly EventBridge schedule for the 1-vCPU/2-GiB worker only after manual runs and recovery checks work. Choose the day/time during deployment. Alert on nonzero task exits, stale successful-publication age, and abnormal runtime/cost. Configure the web and monitor freshness thresholds for weekly publication (initially 216 hours, including two days of grace), rather than the earlier 48-hour daily-schedule assumption. Re-score changed advisories; do not retrain BERT on the routine schedule.

## Cost and failure boundaries

Keep Vercel and the hosted database initially; adding RDS, a load balancer, or an always-on NAT gateway would create recurring charges before they teach us anything necessary for the worker. The Fargate task, image storage, model storage, secret, logs, and data transfer still have costs. AWS credits are temporary and may not cover every charge. Set ECR lifecycle rules, S3 retention/version limits appropriate to model recovery, and CloudWatch log retention. Verify current pricing and actual credit applicability in the console before creating resources.

The current `pipeline/Dockerfile` separates the model from the image and now has an S3 bootstrap. The production database also needs an AWS-reachable, TLS-verified connection and a scoped writer credential. The existing PostgreSQL advisory lock requires a session-compatible connection; a transaction-pooling endpoint is unsuitable.
