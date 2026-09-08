# -----------------------------------------------------------------------------
# CloudPet Terraform remote-state backend — one-time bootstrap.
#
# Creates the S3 bucket that holds Terraform state for every environment.
# State locking uses Terraform's native S3 lockfile (`use_lockfile = true` in
# each environment's backend block) — no DynamoDB table is required.
#
# Run once:
#   cd terraform/bootstrap
#   terraform init && terraform validate && terraform plan && terraform apply
#
# Then copy the `state_bucket_name` output into environments/*/backend.tf and
# run `terraform init -migrate-state` there.
# -----------------------------------------------------------------------------

provider "aws" {
  region  = var.aws_region
  profile = var.aws_profile

  default_tags {
    tags = {
      Project   = "cloudpet"
      ManagedBy = "terraform"
      Component = "tfstate-backend"
    }
  }
}

resource "random_id" "suffix" {
  byte_length = 4
}

locals {
  bucket_name = "cloudpet-tfstate-${random_id.suffix.hex}"
}

resource "aws_s3_bucket" "tfstate" {
  bucket = local.bucket_name

  # Guard against a stray `terraform destroy` in this directory deleting the
  # bucket while it still holds every environment's state.
  lifecycle {
    prevent_destroy = true
  }

  tags = { Name = local.bucket_name }
}

resource "aws_s3_bucket_versioning" "tfstate" {
  bucket = aws_s3_bucket.tfstate.id

  versioning_configuration {
    status = "Enabled"
  }
}

resource "aws_s3_bucket_server_side_encryption_configuration" "tfstate" {
  bucket = aws_s3_bucket.tfstate.id

  rule {
    apply_server_side_encryption_by_default {
      sse_algorithm = "AES256"
    }
    bucket_key_enabled = true
  }
}

resource "aws_s3_bucket_public_access_block" "tfstate" {
  bucket = aws_s3_bucket.tfstate.id

  block_public_acls       = true
  block_public_policy     = true
  ignore_public_acls      = true
  restrict_public_buckets = true
}

resource "aws_s3_bucket_policy" "tfstate_tls_only" {
  bucket = aws_s3_bucket.tfstate.id

  policy = jsonencode({
    Version = "2012-10-17"
    Statement = [
      {
        Sid       = "DenyInsecureTransport"
        Effect    = "Deny"
        Principal = "*"
        Action    = "s3:*"
        Resource = [
          aws_s3_bucket.tfstate.arn,
          "${aws_s3_bucket.tfstate.arn}/*",
        ]
        Condition = {
          Bool = { "aws:SecureTransport" = "false" }
        }
      },
    ]
  })
}

resource "aws_s3_bucket_lifecycle_configuration" "tfstate" {
  bucket = aws_s3_bucket.tfstate.id

  # Bound the storage cost of state history: expire superseded state versions
  # after 90 days and clean up any aborted multipart uploads.
  rule {
    id     = "expire-noncurrent-state-versions"
    status = "Enabled"

    filter {}

    noncurrent_version_expiration {
      noncurrent_days = 90
    }

    abort_incomplete_multipart_upload {
      days_after_initiation = 7
    }
  }
}
