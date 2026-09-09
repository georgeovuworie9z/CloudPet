terraform {
  required_version = ">= 1.16.0, < 2.0.0"

  required_providers {
    aws = {
      source  = "hashicorp/aws"
      version = "~> 6.0"
    }
    random = {
      source  = "hashicorp/random"
      version = "~> 3.6"
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

# --------------------------------------------------------------------------
# 3N-5 ECR: private repository for the CloudPet API image (immutable git-SHA
# tags, scan-on-push, AES256, lifecycle-bounded). No image is pushed here;
# push (GitHub OIDC) is deferred to 3O.
# --------------------------------------------------------------------------
module "ecr" {
  source      = "../../modules/ecr"
  name_prefix = "${var.project}-${var.environment}"
}

# --------------------------------------------------------------------------
# 3N-6 Storage: private S3 bucket for pet images (Block Public Access, SSE-S3
# AES256, no versioning, abort-incomplete-MPU lifecycle). The application
# reaches it only via presigned URLs signed by the EC2 instance role.
# --------------------------------------------------------------------------
module "storage" {
  source      = "../../modules/storage"
  name_prefix = "${var.project}-${var.environment}"
}

# --------------------------------------------------------------------------
# 3N-4 IAM: EC2 application instance role + instance profile (SSM, ECR pull,
# CloudWatch Logs, pet-images S3). No EC2 resource consumes this yet.
# --------------------------------------------------------------------------
module "iam" {
  source                = "../../modules/iam"
  name_prefix           = "${var.project}-${var.environment}"
  ecr_repository_arn    = module.ecr.repository_arn
  pet_images_bucket_arn = module.storage.bucket_arn
}
