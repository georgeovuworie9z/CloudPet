variable "aws_region" {
  description = "AWS region for all CloudPet production infrastructure."
  type        = string
  default     = "eu-north-1"
}

variable "aws_profile" {
  description = <<-EOT
    Local AWS CLI profile used to authenticate (IAM Identity Center / SSO).
    CI/CD (3O) overrides this with "" so the default credential provider chain
    / GitHub OIDC role assumption is used instead of a named profile.
  EOT
  type        = string
  default     = "cloudpet"
}

variable "project" {
  description = "Project name; used in resource name prefixes and default tags."
  type        = string
  default     = "cloudpet"
}

variable "environment" {
  description = "Environment name for this Terraform root."
  type        = string
  default     = "production"
}

variable "vpc_cidr" {
  description = "CIDR block for the production VPC."
  type        = string
  default     = "10.0.0.0/16"
}

variable "availability_zones" {
  description = "Availability zones for the production VPC (>= 2)."
  type        = list(string)
  default     = ["eu-north-1a", "eu-north-1b"]
}

variable "create_nat_gateway" {
  description = "Create the NAT Gateway now. Kept false until the compute milestone needs private-subnet egress."
  type        = bool
  default     = false
}

variable "single_nat_gateway" {
  description = "One shared NAT Gateway (true, cost-optimized) vs one per AZ (false, HA)."
  type        = bool
  default     = true
}
