output "state_bucket_name" {
  description = "Name of the S3 bucket holding Terraform remote state. Copy into environments/*/backend.tf."
  value       = aws_s3_bucket.tfstate.id
}

output "state_bucket_arn" {
  description = "ARN of the Terraform remote-state bucket."
  value       = aws_s3_bucket.tfstate.arn
}

output "state_bucket_region" {
  description = "Region the remote-state bucket lives in."
  value       = var.aws_region
}
