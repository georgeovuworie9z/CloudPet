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
