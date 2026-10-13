# Manual AWS worker benchmark (no schedule or database writes)

Status: both manual AWS benchmark runs completed successfully and stopped with exit code zero. The owner has applied the 19 base AWS resources, uploaded the verified checkpoint and 209 historical advisory inputs to versioned S3 objects, pushed the worker image to ECR, and registered both benchmark task definitions. The local reports pin both S3 object versions, hashes, and the image digest. The manual cloud benchmark milestone is complete; production database integration, durable delivery, monitoring, and scheduling remain.

## AWS results and sizing decision

One native Linux x86_64 Fargate run per size, in `us-east-2`, using the same immutable image, model files, S3 object versions, and 209 historical advisory descriptions:

| Measurement | 1 vCPU / 2 GiB | 2 vCPU / 4 GiB |
| --- | ---: | ---: |
| Container exit code / final task status | 0 / STOPPED | 0 / STOPPED |
| Image pull | 15.345 s | 8.307 s |
| Model download, archive check, extraction, and file checks | 6.689 s | 1.732 s |
| Model loading and inference | 110.550 s | 56.884 s |
| Image-pull start to task stopped | 160.123 s | 96.767 s |
| Peak process RSS | 974.10 MiB | 988.11 MiB |
| Gross compute + public IPv4 estimate per run | $0.002447 | $0.002812 |
| Same measured workload once weekly for 52 runs/year (compute + IPv4 only) | $0.12724/year | $0.14622/year |

Both reports confirm the same model fingerprint and input hash, and both produced class counts `{0: 83, 1: 80, 2: 26, 3: 20}`. The reports contain aggregate counts, not individual predictions: matching counts do not prove country-by-country equality or predictive accuracy. The raw reports are ignored at `.local/aws/benchmark-small.json` and `.local/aws/benchmark-large.json`.

**Decision (owner confirmed October 13, 2026):** retain the version-pinned S3 checkpoint delivery path and use 1 vCPU / 2 GiB, once a week, after production integration passes. Speed is not a priority. It completed this full batch in under three minutes with about 1 GiB of process RSS and a lower estimated cost. The 2-vCPU task reduced pull-to-stop time by 39.6% at a 14.9% higher per-run compute/IPv4 estimate. Both benchmark definitions remain available for comparison; registering them does not run them. No schedule has been created or enabled.

The weekly job refreshes advisories and re-scores changed text; it does not retrain BERT or rebuild clustering. Configure production freshness monitoring for the weekly cadence (initially 216 hours: seven days plus two days of grace), replacing the earlier 48-hour daily-schedule assumption. Verify both the web status and operational monitor use the same threshold before enabling the schedule. Publication age measures refresh success, not advisory validity; visitors can see data up to a week behind the source. Choose the schedule day/time during deployment.

This is one observation per size, not a latency guarantee. The image-pull and S3 timings vary with network conditions, caching, and host capacity; do not attribute their differences entirely to CPU allocation. A container's full memory footprint can exceed process RSS. These runs exclude the production feed fetch and database writes, so final production sizing still needs a complete refresh test.

No S3-to-Fargate cross-Region transfer or NAT gateway is used. The per-run numbers exclude persistent ECR/model storage, S3 requests, CloudWatch logs, other transfer, taxes, and credits; actual gross billing has not yet been reconciled. The yearly values above extrapolate these single benchmark observations and are not the entire application bill.

## Why this path is safe to test

The image excludes the 439 MB baseline checkpoint. `scripts/package_model.py` creates a deterministic tar file containing only the six files pinned in `docs/baseline/artifacts.json`. The cloud entrypoint requests a specific S3 object `VersionId`, verifies the whole archive SHA-256, extracts only the expected filenames into temporary storage, verifies each file against the image-bundled manifest, and then exposes the model directory. On failure, inference never begins. The benchmark command downloads a separately pinned historical advisory fixture and runs inference without opening a database connection. It logs timings, model fingerprint, S3 version, input hash, result counts, and peak process RSS, but not advisory text.

The normal `refresh --write` path continues to record the model content fingerprint and now also records the S3 object version ID in its run metadata. The S3 object version is provenance; the content fingerprint controls prediction-cache reuse.

## Local measurements

- The existing full-advisory Docker benchmark: 209 rows, 208.77 seconds in a 2-CPU/2-GiB Linux amd64 container emulated on an Apple Silicon Mac; about 1 GB reported peak memory.
- Deterministic archive: 438,917,120 bytes, SHA-256 `877404f62d77395935a480b86f8e376fafde4cbb43cd5ad34990446cf3e5798d`.
- Local copy plus archive hash, safe extraction, and per-file verification: 1.368 seconds; local file copy alone 0.387 seconds. The report is ignored at `.local/benchmarks/model-bootstrap-local-01.json`.

These are local observations. They exclude S3 transfer, ECR image pull, Fargate provisioning, and AWS CPU performance. Do not treat the 1.368-second local copy as an S3 download estimate.

## Account access

The owner reports a Builder ID-managed project console that supplies an assumed `AccountFullAccessRole` session. The attempted IAM Identity Center CLI login returned no assigned AWS accounts, so the previous SSO instructions do not apply to the current account-access path. The owner has enabled MFA on Builder ID and authenticated the local terminal using temporary session credentials. These credentials expire and are not a permanent deployment mechanism.

In the terminal where temporary credentials are already exported, use the environment credential provider:

```sh
unset AWS_PROFILE AWS_DEFAULT_PROFILE
export AWS_REGION=us-east-2 AWS_DEFAULT_REGION=us-east-2
aws sts get-caller-identity --query Arn --output text
terraform -chdir=infra/terraform plan -no-color
```

Do not save credential values in project files, shell startup files, or Git, and do not paste them into chat. Exports in the owner's terminal are not automatically available to Codex's separate process. Redact the account number from any shared ARN. Successful identity lookup proves authentication; the Terraform plan is the next check for account policy restrictions and resource-read permissions. Durable local login and GitHub OIDC still need verification before automated delivery.

## Resource and cost review before apply

`infra/terraform` defines a benchmark-only stack: a private versioned S3 bucket, immutable-tag ECR repository, ECS cluster, two task definitions (1 vCPU/2 GiB and 2 vCPU/4 GiB), seven-day log retention, least-privilege S3 read task role, execution role, one public subnet, and a security group with no inbound rule. There is **no** EventBridge schedule, database secret, database access, NAT gateway, load balancer, or RDS instance.

Terraform defaults to `benchmark_enabled = false`. The initial apply would create the base resources only. After the image and both S3 objects have immutable digests/version IDs, a second reviewed plan would add the two task definitions. Terraform state is local and ignored for this single-person benchmark; move it to protected, locked remote state before CI manages infrastructure.

The public subnet gives each running Fargate task a temporary public IPv4 address and HTTPS egress to ECR/S3/CloudWatch. AWS currently prices in-use public IPv4 at $0.005 per hour with a 60-second minimum. An always-on Ohio NAT gateway is $0.045 per hour plus $0.045 per GB processed, so it is excluded. Fargate compute, ECR storage, S3 storage/requests, CloudWatch logs, and any applicable transfer are additional; check current `us-east-2` rates in the AWS Pricing Calculator and actual Cost Explorer usage. Budget alerts are not a cap.

Before any `terraform apply`, review `terraform -chdir=infra/terraform plan` using the verified temporary session and confirm only these expected resources appear. Do not add an EventBridge rule until both manual task runs pass and their total time/cost is compared.

## Manual benchmark sequence

1. Verify the temporary local session and run a **read-only** Terraform plan. Confirm the account and Region; review the resource list and cost implications.
2. Apply the base stack once approved. Save the Terraform state; note the bucket and ECR repository outputs.
3. In the authenticated local terminal, run `uv run --frozen python -m scripts.upload_benchmark_inputs`. It reads the actual Terraform outputs, checks that the session account matches the ECR account, verifies and packages the checkpoint, and uploads it and a minimal historical fixture to content-addressed keys under `models/` and `benchmarks/`. It saves S3 `VersionId` values and SHA-256 hashes in ignored `.local/aws/benchmark-inputs.json`, with progress saved after each upload so rerunning resumes completed work. `--dry-run` validates local inputs without AWS calls. The historical fixture is a benchmark, not current travel guidance. Keep both objects private.
4. Build the worker for `linux/amd64`, push an immutable tag to ECR, then read back its **image digest**. Run `uv run --frozen python -m scripts.prepare_benchmark_tasks` to validate that both reports belong to the current Terraform bucket/repository/account and create ignored `infra/terraform/benchmark.auto.tfvars.json`. This sets `benchmark_enabled = true` and pins the actual object keys, version IDs, checksums, and image digest. Review and apply the second Terraform plan.
5. Run the `small` task once with `assignPublicIp=ENABLED`, wait for it to stop, check its container exit code and CloudWatch `MODEL_BOOTSTRAP_JSON` / `BENCHMARK_JSON` lines. Repeat with `large`. Neither task receives a database URL.
6. Compare S3 download/verification time, inference time, task pull-to-stop time, peak process memory, output class counts, and estimated gross per-run cost. Validate actual gross usage in Billing later because cost data lags. A smaller task wins only if it completes reliably and its longer runtime does not erase savings.
7. If S3 startup cost or operational complexity is excessive, make a separate image that bundles the same pinned model and benchmark that alternative with the same inputs. Keep whichever approach is simpler and cheaper based on measured results.

This is a benchmark sequence, not a production deployment procedure. A production refresh also needs a scoped PostgreSQL writer, TLS, secrets injection, output handling, alarms, and rollback.

## Upload the worker image

Run these in the repository, in the same local terminal with valid temporary credentials and Docker running. Read the registry URL from Terraform rather than entering redacted values:

```sh
SAFETRIP_REPO=$(terraform -chdir=infra/terraform output -raw ecr_repository_url)
SAFETRIP_REGISTRY="${SAFETRIP_REPO%%/*}"
SAFETRIP_TAG="benchmark-$(date -u +%Y%m%dT%H%M%SZ)-${RANDOM}"

aws ecr get-login-password --region us-east-2 | docker login --username AWS --password-stdin "$SAFETRIP_REGISTRY"
```

Wait for `Login Succeeded`, then build the current source for Linux x86_64 and push its unique tag. The checkpoint remains in S3, and the allowlisted Docker build context excludes local state, credentials, and model weights:

```sh
docker buildx build --platform linux/amd64 --file pipeline/Dockerfile --target worker --provenance=false --tag "${SAFETRIP_REPO}:${SAFETRIP_TAG}" --push .
```

After the build and push succeed, read the immutable digest back from ECR and save its metadata locally:

```sh
aws ecr describe-images --region us-east-2 --repository-name safetrip-iq-worker --image-ids "imageTag=${SAFETRIP_TAG}" --output json > .local/aws/benchmark-image.json
```

This step uploads an image; it does not start Fargate. The next Terraform plan will use its image digest and the pinned values from `.local/aws/benchmark-inputs.json` to create both task definitions. A unique tag supports exploration; GitHub CI will later attach commit/build provenance and promote a tested digest.

## Register both benchmark task definitions

The prepared `benchmark.auto.tfvars.json` is automatically loaded by Terraform in this directory, including on later plans. Keep it locally so omitting an explicit `-var-file` cannot accidentally revert `benchmark_enabled` to false. It is ignored by Git and contains artifact identifiers, not AWS credentials.

```sh
terraform -chdir=infra/terraform plan -no-color
```

Expected change: two `aws_ecs_task_definition.benchmark` resources (`small` and `large`), with no changes or deletions to the base resources. These are launch recipes with the same image/model/input and different CPU/memory allocations; registration does not run a container.

After reviewing that plan:

```sh
terraform -chdir=infra/terraform apply
terraform -chdir=infra/terraform output benchmark_task_arns
```

Launching a task is still a separate manual operation. No scheduler is configured.

## Run one task at a time

In the local terminal with active temporary credentials:

```sh
uv run --frozen python -m scripts.run_aws_benchmark --size small
```

Keep this terminal running while it monitors the task. The runner verifies the registered definition against the pinned artifacts, rejects database credentials or another command, launches one Fargate task, records its ARN immediately, waits for a stopped task with exit code zero, and validates the structured CloudWatch metrics. It saves `.local/aws/benchmark-small.json`. After the small run succeeds:

```sh
uv run --frozen python -m scripts.run_aws_benchmark --size large
```

The large report is `.local/aws/benchmark-large.json`. Repeating a command uses the saved task/report rather than launching a duplicate. Use an explicit new `--report .local/aws/benchmark-small-repeat.json` only when deliberately starting a new measured run. The AWS client token also makes a launch retry idempotent within AWS's token lifetime.

The default watchdog requests a stop after 20 minutes from the initial launch request, including provisioning time; Ctrl-C also requests a stop. If the terminal closes abruptly, connectivity fails, or credentials expire, the runner cannot guarantee a stop. It saves the task ARN and tells you when manual stopping is required. Stop that task through the ECS console and confirm `STOPPED` before retrying or launching another run.

The report separates image-pull time, model download-plus-verification time, inference time (including model loading), and pull-to-stop duration. It includes peak process RSS, prediction counts, and a gross Ohio compute/public-IPv4 cost estimate. Storage, API requests, logs, transfer, taxes, and credits are excluded from that per-run estimate; IPv4 lifetime is approximated with creation-to-stop duration. Verify actual gross usage later in Billing. The benchmark does not measure a production feed fetch or database publication.
