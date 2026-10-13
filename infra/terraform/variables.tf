variable "benchmark_enabled" {
  description = "Create the two Fargate task definitions only after image and S3 objects are pinned."
  type        = bool
  default     = false
}

variable "image_digest" {
  description = "ECR image manifest digest without sha256:; never deploy a mutable tag."
  type        = string
  default     = ""
  validation {
    condition     = var.image_digest == "" || can(regex("^[0-9a-f]{64}$", var.image_digest))
    error_message = "image_digest must be a 64-character lowercase SHA-256 digest."
  }
}

variable "model_s3_key" {
  type    = string
  default = "models/checkpoint-189.tar"
}

variable "model_s3_version_id" {
  type        = string
  description = "VersionId returned by the model archive S3 upload."
  default     = ""
}

variable "model_archive_sha256" {
  type    = string
  default = ""
  validation {
    condition     = var.model_archive_sha256 == "" || can(regex("^[0-9a-f]{64}$", var.model_archive_sha256))
    error_message = "model_archive_sha256 must be a lowercase SHA-256 digest."
  }
}

variable "benchmark_s3_key" {
  type    = string
  default = "benchmarks/advisories-209.json"
}

variable "benchmark_s3_version_id" {
  type        = string
  description = "VersionId returned by the historical advisory fixture upload."
  default     = ""
}

variable "benchmark_sha256" {
  type    = string
  default = ""
  validation {
    condition     = var.benchmark_sha256 == "" || can(regex("^[0-9a-f]{64}$", var.benchmark_sha256))
    error_message = "benchmark_sha256 must be a lowercase SHA-256 digest."
  }
}
