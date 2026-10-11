# Stage 4 verification and handoff

Stage 4 implements a locally verified publication pipeline: atomic final scores, missing-component handling, run and input history, incremental inference, full-refresh locks, missing-advisory clearing, bounded fetch retries, and freshness reporting. The frozen full dataset is available in a separate local database. Clustering is frozen; BERT retraining is a future manually triggered, evaluated workflow.

## Reproduce the release checks

From the repository root, with Docker running:

```sh
bash scripts/check_ci.sh
bash scripts/check_database.sh
cd frontend && npm run test:postgres && cd ..
bash scripts/check_containers.sh
cd frontend
npx playwright install chromium
npm run test:browser
```

The CI container job installs Chromium and its system dependencies, then runs the same browser checks against the production web image on port 3001. Tests use real seeded Postgres reads; external map geometry is replaced with a small synthetic polygon so CI does not depend on a third-party geometry download. Browser tests cover search navigation, score display, map color/tooltip/navigation, clustering-only details, a missing-country 404, API error states, and refresh status. This does not validate the external geography dataset's availability or completeness.

The verification set comprises 63 Python/database tests, eight frontend query tests, five browser tests, production dependency audit, TypeScript, lint, production build, and web/worker container smoke checks. The 212 captured scores must match exactly; the full local import separately verified 250 catalog entries, 212 numeric scores, and 38 blank scores through the website reader. Existing image-optimization lint warnings and the documented development-only dependency advisory remain.

## Deployment boundary

Local completion is separate from GitHub CI and the Vercel preview for the new commit. Merge only after those checks pass. The hosted website continues using the legacy Supabase adapter; its refresh time is unknown. Do not apply the empty-database migration chain directly to existing production tables. Hosted adoption requires schema comparison, backup, role provisioning, TLS/pooling configuration, staging validation, and a controlled cutover.

No hosted refresh, scheduling, model training, or AWS deployment has been performed. Private snapshots, model weights, environment files, generated reports, and local database contents remain outside Git. The full local baseline is historical data, not a live advisory update.

## Next: Stage 5

Measure the worker image size, CPU runtime, peak memory, and startup time on the intended deployment architecture. Then confirm the AWS account/credit plan and region, provision ECR/S3/ECS/IAM/logging with Terraform, and use GitHub OIDC for delivery. Validate a manual cloud run before enabling the daily schedule. Database hosting and production cutover remain explicit decisions; the existing Supabase inactivity behavior is not fixed by local Postgres work.

Remaining operational limitations include retention of history/raw inputs, investigation of overdue run receipts, detecting suspicious but syntactically valid partial feeds, and an off-AWS fallback before credits expire. These are documented deployment/operations work, not evidence that source data or model accuracy has been independently validated.
