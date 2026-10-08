# SafeTrip IQ production roadmap

## Objective and scope

Evolve the current Next.js/Vercel and Supabase application into a reproducible, tested application with a versioned Python data pipeline. Learn Docker, PostgreSQL, CI/CD, and AWS within a student budget. Keep each milestone independently useful.

This is a plan, not a record of implemented changes. Live database permissions, deployment configuration, and model artifacts still need verification.

## Target architecture

- Public website: existing Next.js application on Vercel.
- Database: PostgreSQL, initially Supabase; Neon migration is optional to address free-tier pausing. Direct PostgreSQL access does not prevent Supabase pausing.
- Local environment: Docker Compose with web, PostgreSQL, and an on-demand worker.
- Pipeline: packaged Python, uv lockfile, Pydantic validation, SQLAlchemy persistence, CPU-only PyTorch inference initially.
- Schema: one Alembic migration history shared across environments. Next.js uses a server-only PostgreSQL query layer and a scoped read role.
- AWS: scheduled ECS Fargate worker, ECR images, S3 data/model artifacts, EventBridge Scheduler, IAM, Secrets Manager, and CloudWatch.
- Delivery: GitHub Actions with AWS OIDC; Terraform for infrastructure.
- Optional lab: Next.js on ECS, HTTPS load balancer, and private RDS, provisioned temporarily.

## Phase 0 — Verify and close the possible live write exposure

The scripts read ANON_KEY and the web client reads NEXT_PUBLIC_SUPABASE_ANON_KEY. Variable names do not prove their values or privileges. A public anon key is intended to be public; successful writes using that actual role would indicate excessive permissions. RLS may be disabled or permissive.

1. Inspect deployed key types, table grants, RLS status/policies, exposed views, and callable functions without logging credentials. Do not test destructive operations against production data.
2. Back up schema/policies and arrange a controlled writer transition.
3. Give trusted scripts a backend-only secret/service-role credential as an interim measure. Never expose it through NEXT_PUBLIC variables, browser bundles, logs, or Git. It bypasses RLS; replace it with a scoped database writer role during the direct-Postgres refactor.
4. Enable RLS on exposed application tables and retain only intended public SELECT policies. Revoke anonymous INSERT, UPDATE, and DELETE grants; audit authenticated and function-based write paths as well. Avoid blanket read access to internal tables.
5. Verify public site reads still work and unauthorized writes fail using safe test fixtures or rolled-back tests in an isolated environment. Verify the trusted writer separately.
6. Rotate privileged credentials if exposure is discovered. A public anon key alone is not a leaked secret.

Exit: documented evidence that public access cannot modify scores and trusted writes still work. This is an immediate security priority, before broad restructuring.

## Phase 1 — Capture a reproducible baseline

1. Export application schema/data, including views, functions, triggers, and final-score logic.
2. Locate the deployed BERT checkpoint, tokenizer, label mapping, training configuration, and source datasets.
3. Record representative input/output fixtures and the existing scoring behavior. Treat existing scores as regression fixtures, not proof of scientific validity.
4. Replace laptop-specific paths with configuration; replace local Conda paths and development dependency pins with portable dependencies and a lockfile.
5. Document setup, environment variables, data sources, and the path from inputs to published scores.

Exit: a documented baseline can reproduce a representative score and build the existing application.

## Phase 2 — Add basic CI before restructuring

1. Establish a green baseline workflow: TypeScript checking, lint, Next.js build, Python import/configuration smoke test, and a small pure scoring test. Fix baseline failures explicitly rather than hiding them.
2. Keep CI independent of the live database, production credentials, model downloads, and training jobs.
3. Organize into apps/web, pipeline/src/safetrip, research, db/migrations, db/seeds, infra/terraform, docs, and .github/workflows. Move in small reviewable changes and update the Vercel root when moving the frontend.
4. Separate ingestion, preprocessing, inference, scoring, and persistence. Add explicit ingest, score, and refresh commands.
5. Introduce typed server-side queries and distinguish missing-country responses from database failures.
6. Remove tracked .idea and .DS_Store files from Git; retain local IDE settings as needed. Remove the experience_level joke block.
7. Consolidate environment definitions into the verified portable setup before removing envs/*.yml and the root environment file. Preserve unique dependency information until replacement is validated.
8. Replace the placeholder README with setup, architecture, development, tests, limitations, and deployment instructions.

Exit: basic CI protects every subsequent refactor and the app still works on Vercel.

## Phase 3 — Docker and portable PostgreSQL

1. Create Alembic migrations and deterministic development seeds from the inspected application schema.
2. Add separate web and worker Dockerfiles, non-root runtime users, .dockerignore, health checks, and Compose PostgreSQL with a persistent volume.
3. Use a server-only PostgreSQL driver in Next.js and SQLAlchemy in Python. Configure pooling appropriate to Vercel and use a migration connection suitable for DDL.
4. Define separate read, write, and migration roles; avoid using an owner/bypass-RLS role for normal application access.
5. Start the worker with CPU-only PyTorch and required inference dependencies. Exclude training tools, notebooks, CUDA packages, and unused audio/vision packages.
6. Benchmark compressed image size, download/startup time, peak memory, inference duration, and complete task duration on the target CPU architecture. Pin model artifacts and verify checksums.

Exit: a fresh clone starts locally with PostgreSQL, reproduces a verified score, and passes CI. ONNX is optional only after measuring a need and testing output parity; quantization requires evaluation for accuracy regressions.

## Phase 4 — Reliable, separately scheduled data updates

Advisory refresh:

- Fetch advisories on a configurable schedule, initially daily; use source timestamps and content hashes to skip unchanged text.
- Re-score changed advisories; a model/tokenizer/scoring version change also invalidates cached results.
- Use bounded retries, timeouts, run records, and overlap prevention.
- Validate and publish a complete result transactionally. Retain the last successful dataset if a run fails.
- Record fetched time separately from source publication time and show data age in the UI.

Index/model refresh:

- Treat GPI, GTI, and PPI as versioned annual releases, with explicit handling for revisions and release availability. Verify cadence independently for other sources such as PVI.
- Rebuild clustering when an approved input release or methodology changes, rather than on each advisory refresh.
- Persist feature order, imputer, scaler, fitted centroids, dataset version, and cluster-to-risk mapping together.
- Define a documented safety axis with explicit feature direction and weights. Rank centroids along it with deterministic tie handling; cluster IDs themselves carry no risk meaning.
- Assess how rankings change across model versions. A stable mapping within one version does not guarantee equivalent tiers after retraining or establish that the safety axis is valid.
- Preserve immutable raw inputs. Add missing-data and score-bound checks.

CI expansion:

- Test rerun idempotence, failed/partial publication, mappings, and missing data.
- Run integration tests against PostgreSQL created from migrations.
- Add a small Playwright suite for search, map, and country pages; build both images.

Exit: repeated inputs yield consistent outputs, failures preserve published data, and every score is traceable to its sources and versions.

## Optional database migration — Supabase to Neon

This can happen after Phase 3 or later. Reliability work takes priority. Supabase supports direct PostgreSQL, so migration is not a prerequisite for the AWS worker. Remaining on its free tier retains its inactivity-pause limitation.

Export/import application data, compare constraints and representative queries/results, test a Vercel preview against staging, pause old writers for final synchronization, switch production configuration, smoke-test, and keep the original backup until verification completes. Keep previews and integration tests away from production data.

## Phase 5 — AWS worker and repeatable delivery

1. Verify credit eligibility, expiration, account plan, and service availability. Pick one region and estimate costs after local benchmarks.
2. Use Terraform for ECR, S3, ECS task definition, IAM roles, secrets, logging, and scheduling. Protect remote state with access controls, encryption, versioning, and locking.
3. Run the worker manually first. For the low-cost design, use a public subnet/public IP with no inbound access, avoiding a permanent NAT gateway. Connect to hosted PostgreSQL over verified TLS.
4. Add GitHub OIDC restricted to the repository and deployment environment. Build once, deploy immutable image digests, run staging validation, then promote the same artifact.
5. Use explicit backward-compatible migration steps. Verify old application compatibility before rollout; image rollback does not reverse database changes.
6. Enable scheduling after measured runs succeed. Monitor task failures and last-successful-refresh age; a successful task launch is not proof of successful processing.
7. Retain bounded logs, snapshots, and image versions. Review gross usage and credit balance weekly; budget alerts are not a hard cap.

Exit: a commit can be tested and deployed reproducibly, and a scheduled AWS container updates data with observable results.

## Phase 6 — Operational evidence and portfolio presentation

- Demonstrate a failed refresh, image rollback, and database restore into an isolated database.
- Record measured deployment time, worker runtime/memory, monthly cost, and recovery time.
- Document architecture decisions, source/model limitations, and a reproducible demo.
- Add resume claims only for completed work and measured outcomes.

Exit: another person can understand, deploy, and troubleshoot the system using the repository.

## Optional full AWS lab

Temporarily deploy Next.js on ECS behind an HTTPS load balancer with private RDS, using copied data and the same migrations/images. Practice networking, health checks, rolling deployment, and rollback. Record evidence and tear down resources, including retained items reviewed separately. Keep this outside the critical path.

## Scope checkpoints and credit exit

- Core milestone: Phases 0–4, including CI. This already demonstrates substantial engineering work.
- Cloud milestone: Phase 5 plus recovery exercises in Phase 6.
- Stretch: Neon migration when needed, ONNX optimization, and the full AWS lab.
- Work in small sessions: implement a concept, explain it, deliberately trigger a failure, and document recovery. Advance by acceptance criteria rather than a fixed eight-phase deadline.
- Reserve credits for measured worker usage and short labs. Do not leave RDS/load balancers/NAT gateways running merely to preserve a demo.
- Before account/credit expiry, export essential artifacts and data. Move the same worker container to an appropriately sized GitHub Actions runner within applicable limits if AWS costs are no longer affordable. Test this fallback and retain an off-AWS model artifact source before it is needed.

## References

- Supabase security: https://supabase.com/docs/guides/database/secure-data
- Supabase RLS: https://supabase.com/docs/guides/database/postgres/row-level-security
- CPU PyTorch installation: https://pytorch.org/get-started/locally/
- ONNX quantization evaluation: https://onnxruntime.ai/docs/performance/model-optimizations/quantization.html
- AWS credit terms: https://aws.amazon.com/free/free-tier-faqs/
- ECS networking: https://docs.aws.amazon.com/AmazonECS/latest/developerguide/networking-outbound.html
