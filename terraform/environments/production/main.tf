terraform {
  required_version = ">= 1.16.0, < 2.0.0"

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

  default_tags {
    tags = {
      Project     = var.project
      Environment = var.environment
      ManagedBy   = "terraform"
    }
  }
}

# --------------------------------------------------------------------------
# 3N-2 Networking: VPC, subnets, IGW, route tables, S3 Gateway endpoint.
# The NAT Gateway is disabled for now (create_nat_gateway = false) so the
# VPC skeleton costs ~$0/month; it is enabled in the compute milestone when
# private-subnet egress is actually needed.
# --------------------------------------------------------------------------
module "networking" {
  source = "../../modules/networking"

  name_prefix        = "${var.project}-${var.environment}"
  aws_region         = var.aws_region
  vpc_cidr           = var.vpc_cidr
  availability_zones = var.availability_zones
  create_nat_gateway = var.create_nat_gateway
  single_nat_gateway = var.single_nat_gateway
}

# --------------------------------------------------------------------------
# 3N-3 Security Groups: ALB -> app -> RDS. No ALB/EC2/RDS resources are
# created here; later 3N milestones consume these SG IDs.
# --------------------------------------------------------------------------
module "security" {
  source = "../../modules/security"

  name_prefix = "${var.project}-${var.environment}"
  vpc_id      = module.networking.vpc_id
}
