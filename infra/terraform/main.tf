data "aws_availability_zones" "available" {
  state = "available"
}

data "aws_iam_policy_document" "ecs_assume" {
  statement {
    actions = ["sts:AssumeRole"]
    principals {
      type        = "Service"
      identifiers = ["ecs-tasks.amazonaws.com"]
    }
  }
}

resource "aws_vpc" "worker" {
  cidr_block           = "10.42.0.0/16"
  enable_dns_support   = true
  enable_dns_hostnames = true
  tags                 = { Name = "safetrip-iq-worker" }
}

resource "aws_subnet" "worker" {
  vpc_id            = aws_vpc.worker.id
  cidr_block        = "10.42.1.0/24"
  availability_zone = data.aws_availability_zones.available.names[0]
  tags              = { Name = "safetrip-iq-worker-public" }
}

resource "aws_internet_gateway" "worker" {
  vpc_id = aws_vpc.worker.id
  tags   = { Name = "safetrip-iq-worker" }
}

resource "aws_route_table" "worker" {
  vpc_id = aws_vpc.worker.id
  route {
    cidr_block = "0.0.0.0/0"
    gateway_id = aws_internet_gateway.worker.id
  }
}

resource "aws_route_table_association" "worker" {
  subnet_id      = aws_subnet.worker.id
  route_table_id = aws_route_table.worker.id
}

resource "aws_security_group" "worker" {
  name_prefix = "safetrip-iq-worker-"
  description = "Outbound-only scheduled worker"
  vpc_id      = aws_vpc.worker.id
  tags        = { Name = "safetrip-iq-worker" }
}

resource "aws_vpc_security_group_egress_rule" "worker_https" {
  security_group_id = aws_security_group.worker.id
  cidr_ipv4         = "0.0.0.0/0"
  ip_protocol       = "tcp"
  from_port         = 443
  to_port           = 443
}

resource "aws_ecr_repository" "worker" {
  name                 = "safetrip-iq-worker"
  image_tag_mutability = "IMMUTABLE"
  force_delete         = false
  image_scanning_configuration {
    scan_on_push = true
  }
}

resource "aws_ecr_lifecycle_policy" "worker" {
  repository = aws_ecr_repository.worker.name
  policy = jsonencode({
    rules = [{
      rulePriority = 1
      description  = "Keep the five most recent worker images"
      selection = {
        tagStatus   = "any"
        countType   = "imageCountMoreThan"
        countNumber = 5
      }
      action = { type = "expire" }
    }]
  })
}

resource "aws_s3_bucket" "models" {
  bucket_prefix = "safetrip-iq-models-"
  force_destroy = false
  lifecycle { prevent_destroy = true }
}

resource "aws_s3_bucket_public_access_block" "models" {
  bucket                  = aws_s3_bucket.models.id
  block_public_acls       = true
  block_public_policy     = true
  ignore_public_acls      = true
  restrict_public_buckets = true
}

resource "aws_s3_bucket_versioning" "models" {
  bucket = aws_s3_bucket.models.id
  versioning_configuration { status = "Enabled" }
}

resource "aws_s3_bucket_server_side_encryption_configuration" "models" {
  bucket = aws_s3_bucket.models.id
  rule {
    apply_server_side_encryption_by_default { sse_algorithm = "AES256" }
  }
}

resource "aws_cloudwatch_log_group" "worker" {
  name              = "/safetrip-iq/worker"
  retention_in_days = 7
}

resource "aws_ecs_cluster" "worker" {
  name = "safetrip-iq-worker"
}

resource "aws_iam_role" "execution" {
  name               = "safetrip-iq-ecs-execution"
  assume_role_policy = data.aws_iam_policy_document.ecs_assume.json
}

resource "aws_iam_role_policy_attachment" "execution" {
  role       = aws_iam_role.execution.name
  policy_arn = "arn:aws:iam::aws:policy/service-role/AmazonECSTaskExecutionRolePolicy"
}

resource "aws_iam_role" "task" {
  name               = "safetrip-iq-benchmark-task"
  assume_role_policy = data.aws_iam_policy_document.ecs_assume.json
}

data "aws_iam_policy_document" "task_s3" {
  statement {
    actions = ["s3:GetObjectVersion"]
    resources = [
      "${aws_s3_bucket.models.arn}/models/*",
      "${aws_s3_bucket.models.arn}/benchmarks/*",
    ]
  }
}

resource "aws_iam_role_policy" "task_s3" {
  name   = "read-pinned-model-and-benchmark"
  role   = aws_iam_role.task.id
  policy = data.aws_iam_policy_document.task_s3.json
}

locals {
  benchmark_environment = [
    { name = "SAFETRIP_MODEL_S3_BUCKET", value = aws_s3_bucket.models.bucket },
    { name = "SAFETRIP_MODEL_S3_KEY", value = var.model_s3_key },
    { name = "SAFETRIP_MODEL_S3_VERSION_ID", value = var.model_s3_version_id },
    { name = "SAFETRIP_MODEL_S3_SHA256", value = var.model_archive_sha256 },
    { name = "SAFETRIP_BENCHMARK_S3_BUCKET", value = aws_s3_bucket.models.bucket },
    { name = "SAFETRIP_BENCHMARK_S3_KEY", value = var.benchmark_s3_key },
    { name = "SAFETRIP_BENCHMARK_S3_VERSION_ID", value = var.benchmark_s3_version_id },
    { name = "SAFETRIP_BENCHMARK_SHA256", value = var.benchmark_sha256 },
  ]
}

resource "aws_ecs_task_definition" "benchmark" {
  for_each                 = var.benchmark_enabled ? { small = ["1024", "2048"], large = ["2048", "4096"] } : {}
  family                   = "safetrip-iq-benchmark-${each.key}"
  requires_compatibilities = ["FARGATE"]
  network_mode             = "awsvpc"
  cpu                      = each.value[0]
  memory                   = each.value[1]
  execution_role_arn       = aws_iam_role.execution.arn
  task_role_arn            = aws_iam_role.task.arn
  runtime_platform {
    operating_system_family = "LINUX"
    cpu_architecture        = "X86_64"
  }
  container_definitions = jsonencode([{
    name        = "worker"
    image       = "${aws_ecr_repository.worker.repository_url}@sha256:${var.image_digest}"
    essential   = true
    command     = ["benchmark"]
    environment = local.benchmark_environment
    logConfiguration = {
      logDriver = "awslogs"
      options = {
        awslogs-group         = aws_cloudwatch_log_group.worker.name
        awslogs-region        = "us-east-2"
        awslogs-stream-prefix = "benchmark"
      }
    }
  }])
  lifecycle {
    precondition {
      condition = (
        length(var.image_digest) == 64 &&
        length(var.model_s3_version_id) > 0 &&
        length(var.model_archive_sha256) == 64 &&
        length(var.benchmark_s3_version_id) > 0 &&
        length(var.benchmark_sha256) == 64
      )
      error_message = "Pin the image digest and both S3 object versions and SHA-256 hashes before enabling benchmark tasks."
    }
  }
}
