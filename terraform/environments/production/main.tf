terraform {
  required_version = ">= 1.10.0"

  required_providers {
    aws = {
      source  = "hashicorp/aws"
      version = "~> 6.0"
    }
  }
}

# Explicit region and named AWS CLI profile. No static credentials and no
# access keys are configured here: credentials resolve through the IAM
# Identity Center (SSO) session that backs `var.aws_profile`.
#
# CI/CD (3O) will override `aws_profile` with an empty string so the default
# credential provider chain / GitHub OIDC role assumption is used instead of a
# named profile.
provider "aws" {
  region  = var.aws_region
  profile = var.aws_profile
}

# 3N-1 (Terraform Foundation) declares no resources and no data sources.
# `terraform validate` runs fully offline. `terraform plan` (not run in 3N-1)
# would report "No changes" and make only a read-only sts:GetCallerIdentity
# call while configuring the provider. Resources are introduced incrementally
# in later 3N milestones.
