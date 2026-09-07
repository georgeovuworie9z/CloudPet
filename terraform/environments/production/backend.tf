# Terraform state backend for the CloudPet "production" environment.
#
# 3N-1: state is LOCAL (terraform.tfstate on disk, git-ignored via
# terraform/.gitignore). This is intentional for the foundation milestone:
# the configuration declares no resources, so the local state is empty and
# disposable.
#
# 3N-2 (planned): migrate to a remote S3 backend with native state locking
# (Terraform >= 1.10 `use_lockfile`, no DynamoDB table required):
#
#     terraform {
#       backend "s3" {
#         bucket       = "<cloudpet-tfstate-bucket>"
#         key          = "environments/production/terraform.tfstate"
#         region       = "eu-north-1"
#         encrypt      = true
#         use_lockfile = true
#       }
#     }
#
# Chicken-and-egg: the state bucket is itself infrastructure, so it cannot be
# created by a configuration that already stores its state in that bucket. It
# will be created by a dedicated `terraform/bootstrap/` configuration that
# uses its own LOCAL state. That bootstrap state is also git-ignored and is
# never committed. Once the bucket exists, this file is switched to
# `backend "s3"` and the existing local state is moved with:
#
#     terraform init -migrate-state
#
# Nothing in 3N-1 creates the state bucket or the bootstrap configuration.

terraform {
  backend "local" {}
}
