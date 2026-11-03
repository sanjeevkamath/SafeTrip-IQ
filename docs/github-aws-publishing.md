# GitHub → AWS image publishing

This step publishes tested worker images to the existing ECR repository. It does not deploy a worker, launch Fargate, change Supabase, enable a schedule, or grant access to database secrets.

## What happens

```text
PR -> existing CI (including new mocked Terraform checks)
Merge to main -> CI passes -> publishing workflow checks that exact commit
GitHub OIDC identity -> temporary AWS publisher role -> build/push linux/amd64 worker
                                                -> worker-image.json with immutable digest
```

The role trusts exactly `repo:sanjeevkamath/SafeTrip-IQ:ref:refs/heads/main` with the STS audience. It can obtain an ECR login token and push/read images only in `safetrip-iq-worker`. No AWS access key is stored in GitHub. No environment is attached to the publishing job: attaching one would change the OIDC subject and requires a deliberate trust-policy update.

The workflow runs after successful push CI on main, or manually on main. It verifies the latest CI run for the same repository/commit before AWS authentication. Fork/PR runs cannot authorize publishing. Until both repository variables are configured, publishing is skipped. Images use unique commit/run/attempt tags because ECR tags are immutable; deployments will use the digest, not a moving tag.

## Account access check — November 3, 2026

CLI authentication succeeded in the existing project account. However, `iam:ListOpenIDConnectProviders` was explicitly denied by an organization SCP statement named `DenyIAMRestrictedActions`, despite the role's AdministratorAccess allow. Read-only request-authorization details confirmed that denial. Reading the SCP itself was also denied, so its complete action list and conditions remain unknown. Provider creation and GitHub federation have not been tested; do not infer they are allowed or universally blocked from the listing result alone.

Before following the bootstrap steps, establish whether this managed workspace supports GitHub OIDC or obtain administrator-assisted provisioning. Adding an IAM allow does not override an applicable organization-level explicit deny. No provider, role, or other AWS resource was changed during these checks. The AWS MCP tools were not exposed in this chat; account reads used the local CLI.

## 1. Check your AWS session

Run from the project directory in the terminal where you used AWS for the benchmarks:

```sh
aws sts get-caller-identity --query Account --output text
```

If the session is expired or missing, refresh the temporary login using your working account sign-in method and repeat. Do not paste access keys, session tokens, or connection strings into chat. Credentials exported in your terminal are not automatically available to the agent's shell.

Check whether this account already has the GitHub identity provider:

```sh
aws iam list-open-id-connect-providers \
  --query "OpenIDConnectProviderList[?ends_with(Arn, 'oidc-provider/token.actions.githubusercontent.com')].Arn" \
  --output text
```

## 2. Prepare local Terraform configuration

If the provider check returns **no ARN**, create this Git-ignored file:

```sh
cat > infra/terraform/github-publishing.auto.tfvars <<'VARS'
github_publishing_enabled = true
github_repository = "sanjeevkamath/SafeTrip-IQ"
VARS
```

If a provider ARN already exists, add `existing_github_oidc_provider_arn = "<the returned ARN>"` to that file. AWS permits only one provider per issuer URL per account; reusing it avoids a duplicate-provider error. The existing provider must include the `sts.amazonaws.com` audience; inspect its configuration rather than modifying other applications' shared settings blindly. Provider ARN and repository variables are identifiers, not credentials.

The file is separate from the existing benchmark inputs. Do not replace `benchmark.auto.tfvars.json` or remove its pinned values. Check for an existing GitHub configuration file before overwriting one on repeat setup.

```sh
mkdir -p .local/aws
terraform -chdir=infra/terraform init -input=false
terraform -chdir=infra/terraform plan -out=../../.local/aws/github-publishing.tfplan
```

Review the plan. With unchanged benchmark inputs and no drift, expect three additions: identity provider, publisher role, and role policy. Reusing a provider means two additions. There should be no application deployment or destructive changes. Unexpected modifications need investigation before applying.

Apply the exact reviewed plan:

```sh
terraform -chdir=infra/terraform apply ../../.local/aws/github-publishing.tfplan
```

This is the one-time human bootstrap. GitHub cannot create its own initial AWS trust, and the publisher role intentionally has no Terraform-management permissions. Terraform state remains local in this step; a future infrastructure deployment workflow needs a secure remote backend and a separate role.

## 3. Configure GitHub repository variables

With GitHub CLI authenticated:

```sh
SAFETRIP_PUBLISH_ROLE="$(terraform -chdir=infra/terraform output -raw github_publisher_role_arn)"
gh variable set AWS_PUBLISH_ROLE_ARN --repo sanjeevkamath/SafeTrip-IQ --body "$SAFETRIP_PUBLISH_ROLE"
gh variable set AWS_ECR_REPOSITORY --repo sanjeevkamath/SafeTrip-IQ --body safetrip-iq-worker
```

These are **repository variables**, not AWS key secrets. Region is fixed to `us-east-2` in the workflow, matching Terraform.

## 4. Commit only this implementation

The working tree also contains earlier, uncommitted model/research changes. Keep this PR focused; do not use `git add .`.

If still on the existing development branch, create a branch for this change:

```sh
git switch -c aws-image-publishing
git add .github/workflows/ci.yml .github/workflows/publish-worker.yml \
  infra/terraform/github-publishing.tf infra/terraform/tests/github-publishing.tftest.hcl \
  scripts/check_publish_ci.py tests/test_publish_ci.py docs/github-aws-publishing.md
git diff --cached --stat
git diff --cached --check
```

Inspect the staged diff before committing. It should contain those seven files only. Local Terraform variable files/state/plans, credentials, private `.local/` artifacts, and the earlier research changes should not be staged.

```sh
git commit -m "Add GitHub OIDC and tested worker image publishing"
git push -u origin aws-image-publishing
gh pr create --repo sanjeevkamath/SafeTrip-IQ --base main --head aws-image-publishing --fill
```

The current branch was two merge commits behind `origin/main` when checked; their tracked file trees matched. Refresh/review branch divergence before making unrelated changes; do not reset or stash the existing uncommitted research work merely to publish this PR.

## 5. Verify the first published image

After review, CI passing, and merge, the next successful main push CI triggers publishing. In GitHub Actions, inspect **Publish worker image** for a successful run and its immutable image reference. Download the `worker-image-<run>-<attempt>` artifact containing `worker-image.json` and retain the digest for the later task definition.

For a deliberate retry after configuration is ready:

```sh
gh workflow run publish-worker.yml --ref main --repo sanjeevkamath/SafeTrip-IQ
```

Manual dispatch also requires successful latest CI on that exact main commit. A successful publishing run proves GitHub authentication and image delivery, not runtime correctness or database publication. No Fargate task should start as part of it.

## Verification performed locally

- Terraform configuration validation succeeded with the installed AWS provider.
- Three mocked Terraform tests passed: disabled-by-default behavior, exact main-branch trust/repository-scoped permissions, and reuse of an existing provider. Mock tests make no AWS calls.
- actionlint passed for CI and publishing workflows.
- All 75 Python unit tests passed, including exact-commit CI authorization and rejection of PRs, forks, failed/pending/latest runs, and invalid SHAs.
- Formatting and diff whitespace checks passed. No Dockerfile/runtime change was made in this step; the first real GitHub publish and AWS OIDC exchange remain to be verified.

References: [GitHub OIDC for AWS](https://docs.github.com/en/actions/how-tos/secure-your-work/security-harden-deployments/oidc-in-aws), [AWS ECR push permissions](https://docs.aws.amazon.com/AmazonECR/latest/userguide/image-push-iam.html), [AWS OIDC provider creation](https://docs.aws.amazon.com/IAM/latest/UserGuide/id_roles_providers_create_oidc.html).
