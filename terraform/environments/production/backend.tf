# Terraform state backend for the CloudPet "production" environment.
#
# Remote state lives in the S3 bucket created by terraform/bootstrap/. State
# locking uses Terraform's native S3 lockfile (`use_lockfile = true`) — no
# DynamoDB table is required. The bucket has versioning + SSE + Block Public
# Access + a TLS-only policy (see terraform/bootstrap/main.tf).
#
# Backend config values must be literals (no variables), so the bucket name is
# hard-coded here. It is the terraform/bootstrap `state_bucket_name` output.

terraform {
  backend "s3" {
    bucket       = "cloudpet-tfstate-c0a81be9"
    key          = "environments/production/terraform.tfstate"
    region       = "eu-north-1"
    encrypt      = true
    use_lockfile = true
  }
}
