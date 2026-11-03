# Image publishing only. Task execution and infrastructure changes use separate roles.
variable "github_publishing_enabled" {
  description = "Create the GitHub OIDC publisher role; does not deploy or run tasks."
  type        = bool
  default     = false
}

variable "github_repository" {
  description = "Exact GitHub owner/repository allowed to publish from main."
  type        = string
  default     = "sanjeevkamath/SafeTrip-IQ"
  validation {
    condition     = can(regex("^[A-Za-z0-9_.-]+/[A-Za-z0-9_.-]+$", var.github_repository))
    error_message = "Use an exact owner/repository, without wildcards."
  }
}

variable "existing_github_oidc_provider_arn" {
  description = "Reuse the account's GitHub provider if one already exists; otherwise create one."
  type        = string
  default     = null
  validation {
    condition = var.existing_github_oidc_provider_arn == null ? true : can(regex(
      "^arn:aws:iam::[0-9]{12}:oidc-provider/token\\.actions\\.githubusercontent\\.com$",
      var.existing_github_oidc_provider_arn
    ))
    error_message = "Expected an IAM ARN for token.actions.githubusercontent.com."
  }
}

resource "aws_iam_openid_connect_provider" "github" {
  count          = var.github_publishing_enabled && var.existing_github_oidc_provider_arn == null ? 1 : 0
  url            = "https://token.actions.githubusercontent.com"
  client_id_list = ["sts.amazonaws.com"]
  # AWS retrieves the CA thumbprint when creating a provider; no hard-coded certificate.
}

locals {
  github_subject = "repo:${var.github_repository}:ref:refs/heads/main"
  github_provider_arn = !var.github_publishing_enabled ? null : (
    var.existing_github_oidc_provider_arn != null ? var.existing_github_oidc_provider_arn : aws_iam_openid_connect_provider.github[0].arn
  )
  github_publisher_trust = jsonencode({
    Version = "2012-10-17"
    Statement = [{
      Effect    = "Allow"
      Action    = "sts:AssumeRoleWithWebIdentity"
      Principal = { Federated = local.github_provider_arn }
      Condition = {
        StringEquals = {
          "token.actions.githubusercontent.com:aud" = "sts.amazonaws.com"
          "token.actions.githubusercontent.com:sub" = local.github_subject
        }
      }
    }]
  })
  github_publisher_permissions = jsonencode({
    Version = "2012-10-17"
    Statement = [
      {
        Sid      = "RegistryLogin"
        Effect   = "Allow"
        Action   = ["ecr:GetAuthorizationToken"]
        Resource = "*"
      },
      {
        Sid    = "PublishWorkerRepositoryOnly"
        Effect = "Allow"
        Action = [
          "ecr:BatchCheckLayerAvailability", "ecr:InitiateLayerUpload",
          "ecr:UploadLayerPart", "ecr:CompleteLayerUpload", "ecr:PutImage",
          "ecr:BatchGetImage", "ecr:GetDownloadUrlForLayer", "ecr:DescribeImages"
        ]
        Resource = aws_ecr_repository.worker.arn
      }
    ]
  })
}

resource "aws_iam_role" "github_publisher" {
  count                = var.github_publishing_enabled ? 1 : 0
  name                 = "safetrip-iq-github-publisher"
  max_session_duration = 3600
  assume_role_policy   = local.github_publisher_trust
}

resource "aws_iam_role_policy" "github_publisher" {
  count  = var.github_publishing_enabled ? 1 : 0
  name   = "publish-worker-image-only"
  role   = aws_iam_role.github_publisher[0].id
  policy = local.github_publisher_permissions
}

output "github_publisher_role_arn" {
  value = var.github_publishing_enabled ? aws_iam_role.github_publisher[0].arn : null
}
