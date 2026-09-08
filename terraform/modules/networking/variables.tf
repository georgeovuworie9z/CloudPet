variable "name_prefix" {
  description = "Prefix for Name tags / resource identifiers, e.g. \"cloudpet-production\"."
  type        = string
}

variable "aws_region" {
  description = "AWS region (used to build the S3 Gateway endpoint service name)."
  type        = string
}

variable "vpc_cidr" {
  description = "CIDR block for the VPC."
  type        = string
  default     = "10.0.0.0/16"
}

variable "availability_zones" {
  description = "AZs to spread subnets across; index-aligned with the *_subnet_cidrs lists."
  type        = list(string)
  default     = ["eu-north-1a", "eu-north-1b"]
}

variable "public_subnet_cidrs" {
  description = "One CIDR per AZ for the public (ALB / NAT) tier."
  type        = list(string)
  default     = ["10.0.0.0/24", "10.0.1.0/24"]
}

variable "private_app_subnet_cidrs" {
  description = "One CIDR per AZ for the private application (EC2 / ASG) tier."
  type        = list(string)
  default     = ["10.0.10.0/24", "10.0.11.0/24"]
}

variable "private_db_subnet_cidrs" {
  description = "One CIDR per AZ for the private database (RDS) tier."
  type        = list(string)
  default     = ["10.0.20.0/24", "10.0.21.0/24"]
}

variable "create_nat_gateway" {
  description = <<-EOT
    Create the NAT Gateway (its EIP, and the private-app default routes). Set
    false to stand up the VPC skeleton at ~$0/month until the compute milestone
    needs private-subnet egress.
  EOT
  type        = bool
  default     = true
}

variable "single_nat_gateway" {
  description = <<-EOT
    If true, one shared NAT Gateway serves all private-app subnets (cost). If
    false, one NAT Gateway per AZ (HA). Ignored when create_nat_gateway = false.
  EOT
  type        = bool
  default     = true
}

variable "tags" {
  description = "Extra tags merged onto every resource, on top of provider default_tags."
  type        = map(string)
  default     = {}
}
