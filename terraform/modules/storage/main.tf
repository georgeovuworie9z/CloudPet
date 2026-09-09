# Private S3 bucket for CloudPet pet images.
#
# The application never talks to this bucket directly with long-lived
# credentials: it hands clients short-lived presigned PUT/GET URLs and issues
# delete_object calls, all signed with the EC2 instance role (3N-4), which is
# scoped to s3:GetObject/PutObject/DeleteObject on "<this bucket>/*".
#
# Private only: all four Block Public Access flags are set, there is no bucket
# policy and no ACL (new buckets are BucketOwnerEnforced by default), and no
# website / logging / replication / versioning configuration. Objects are
# encrypted at rest with SSE-S3 (AES256); no KMS.

resource "random_id" "bucket_suffix" {
  byte_length = 4
}

locals {
  bucket_name = "${var.name_prefix}-pet-images-${random_id.bucket_suffix.hex}"
}

resource "aws_s3_bucket" "pet_images" {
  bucket = local.bucket_name

  # User-uploaded images are not reproducible. force_destroy stays at its
  # default (false) so Terraform also cannot delete a non-empty bucket.
  lifecycle {
    prevent_destroy = true
  }

  tags = merge(var.tags, { Name = local.bucket_name })
}

resource "aws_s3_bucket_public_access_block" "pet_images" {
  bucket = aws_s3_bucket.pet_images.id

  block_public_acls       = true
  block_public_policy     = true
  ignore_public_acls      = true
  restrict_public_buckets = true
}

resource "aws_s3_bucket_server_side_encryption_configuration" "pet_images" {
  bucket = aws_s3_bucket.pet_images.id

  rule {
    apply_server_side_encryption_by_default {
      sse_algorithm = "AES256"
    }
  }
}

resource "aws_s3_bucket_lifecycle_configuration" "pet_images" {
  bucket = aws_s3_bucket.pet_images.id

  # Only clean up stalled multipart uploads. No object-expiration rule -- pet
  # images are user data and must persist. No noncurrent-version rule --
  # versioning is disabled, so there are no noncurrent versions.
  rule {
    id     = "abort-incomplete-multipart-uploads"
    status = "Enabled"

    filter {}

    abort_incomplete_multipart_upload {
      days_after_initiation = var.abort_incomplete_multipart_upload_days
    }
  }
}
