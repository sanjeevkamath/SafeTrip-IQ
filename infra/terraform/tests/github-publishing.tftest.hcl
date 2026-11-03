# All AWS operations are mocked. These tests never create real resources.
mock_provider "aws" {
  mock_data "aws_availability_zones" {
    defaults = { names = ["us-east-2a"] }
  }
  mock_data "aws_iam_policy_document" {
    defaults = { json = "{\"Version\":\"2012-10-17\",\"Statement\":[]}" }
  }
  mock_resource "aws_ecr_repository" {
    defaults = { arn = "arn:aws:ecr:us-east-2:123456789012:repository/safetrip-iq-worker" }
  }
  mock_resource "aws_iam_openid_connect_provider" {
    defaults = { arn = "arn:aws:iam::123456789012:oidc-provider/token.actions.githubusercontent.com" }
  }
}

variables {
  benchmark_enabled = false
}

run "disabled_by_default" {
  command = apply
  variables { github_publishing_enabled = false }
  assert {
    condition     = length(aws_iam_role.github_publisher) == 0 && length(aws_iam_openid_connect_provider.github) == 0
    error_message = "Publishing must be opt-in."
  }
}

run "main_only_and_repository_scoped" {
  command = apply
  variables { github_publishing_enabled = true }
  assert {
    condition = (
      jsondecode(aws_iam_role.github_publisher[0].assume_role_policy).Statement[0].Condition.StringEquals["token.actions.githubusercontent.com:sub"] == "repo:sanjeevkamath/SafeTrip-IQ:ref:refs/heads/main" &&
      jsondecode(aws_iam_role.github_publisher[0].assume_role_policy).Statement[0].Condition.StringEquals["token.actions.githubusercontent.com:aud"] == "sts.amazonaws.com"
    )
    error_message = "Trust must require the exact repository, main branch, and STS audience."
  }
  assert {
    condition = (
      jsondecode(aws_iam_role_policy.github_publisher[0].policy).Statement[0].Action == ["ecr:GetAuthorizationToken"] &&
      jsondecode(aws_iam_role_policy.github_publisher[0].policy).Statement[1].Resource == aws_ecr_repository.worker.arn &&
      toset(jsondecode(aws_iam_role_policy.github_publisher[0].policy).Statement[1].Action) == toset([
        "ecr:BatchCheckLayerAvailability", "ecr:InitiateLayerUpload", "ecr:UploadLayerPart",
        "ecr:CompleteLayerUpload", "ecr:PutImage", "ecr:BatchGetImage",
        "ecr:GetDownloadUrlForLayer", "ecr:DescribeImages"
      ])
    )
    error_message = "The publisher must have only registry login and the exact worker-repository image permissions."
  }
}

run "reuse_existing_provider" {
  command = apply
  variables {
    github_publishing_enabled         = true
    existing_github_oidc_provider_arn = "arn:aws:iam::123456789012:oidc-provider/token.actions.githubusercontent.com"
  }
  assert {
    condition = (
      length(aws_iam_openid_connect_provider.github) == 0 &&
      jsondecode(aws_iam_role.github_publisher[0].assume_role_policy).Statement[0].Principal.Federated == var.existing_github_oidc_provider_arn
    )
    error_message = "An existing GitHub provider must be reused rather than duplicated."
  }
}
