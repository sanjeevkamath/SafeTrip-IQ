# Phase 5 pre-commit review

Reviewed October 13, 2026, before committing the AWS benchmark implementation.

## Scope and findings

Checked tracked working-tree files and non-ignored untracked files, including the pending Terraform, worker, scripts, tests, documentation, and dependency changes. No real credentials were found in the files eligible for this commit. No existing commits were ahead of the configured upstream at the time of review. This is a working-tree review, not a complete historical Git audit or a guarantee against every possible secret format.

The scan checked AWS access-key IDs, private keys, GitHub tokens, Supabase secret keys, JWTs, credential-bearing URLs, credential-like assignments, account identifiers, and email addresses. Findings were reviewed without printing credential values. Connection strings belong to local development or example/test fixtures. Account numbers in new tests are synthetic. Emails in existing advisory datasets are public State Department contacts; the generated research map contains a library attribution address and API URL templates. The actual AWS account number does not appear in commit candidates. Personal billing details have been removed from the onboarding document.

No tracked private environment files, AWS credential directories, local exports/reports, Terraform state, or variable files were found. Git ignore rules now also cover `.env.production` and other `.env.*` files (retaining `.env.example`), `.aws/`, custom Terraform state names, temporary variable files, and Terraform crash logs. Ignore rules do not protect a file already tracked or explicitly added with `git add -f`.

## What belongs in the commit

- Terraform source and `.terraform.lock.hcl`: infrastructure declarations and provider versions/checksums, without credential values or local resource identifiers.
- Worker code and Dockerfile: checksum-verified S3 model bootstrap, benchmark inference, and model provenance.
- Helper scripts: package/upload immutable inputs, prepare local task configuration, and launch/monitor manual benchmarks using the AWS credential provider.
- Tests: fixture-based checks for artifact pinning, integrity, and safe diagnostics.
- Documentation and Python dependency files: setup instructions, measured benchmark results, and reproducible dependencies.
- `.gitignore`: exclusions for private local configuration and generated artifacts.

Keep `.local/`, `results/`, `.env*` secrets, `.aws/`, Terraform state/cache/plans, and `benchmark.auto.tfvars.json` local. Both actual benchmark reports and the generated artifact configuration were verified to be ignored. The Docker build context uses an allowlist and excludes local credentials, Terraform files, and model weights. AWS CLI failure handling reports fixed advice and recognized error codes instead of raw diagnostics.

## Deployment decision

Use 1 vCPU / 2 GiB and refresh once weekly. Keep model delivery pinned to S3 object versions and checksums. No production schedule is enabled yet. Before scheduling, validate the hosted database writer and complete refresh, then configure both website freshness status and operational monitoring for the weekly cadence rather than the earlier daily threshold. Routine refreshes do not retrain BERT.
