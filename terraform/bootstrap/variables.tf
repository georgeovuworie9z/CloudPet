variable "aws_region" {
  description = "AWS region for the Terraform remote-state bucket."
  type        = string
  default     = "eu-north-1"
}

variable "aws_profile" {
  description = "Local AWS CLI profile used to authenticate (IAM Identity Center / SSO)."
  type        = string
  default     = "cloudpet"
}
