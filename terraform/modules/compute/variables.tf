variable "name_prefix" {
  description = "Prefix for compute resource names / Name tags, e.g. \"cloudpet-production\"."
  type        = string
}

variable "subnet_ids" {
  description = "Private application subnet IDs (>= 2, in >= 2 AZs) the ASG launches instances into."
  type        = list(string)
}

variable "security_group_ids" {
  description = "Security group IDs to attach to instances (the app SG from the security module)."
  type        = list(string)
}

variable "instance_profile_name" {
  description = "Name of the EC2 instance profile (from the iam module)."
  type        = string
}

variable "target_group_arns" {
  description = "ALB target group ARN(s) the ASG registers instances with."
  type        = list(string)
}

variable "aws_region" {
  description = "AWS region; used by the boot script for AWS CLI calls (SSM, Secrets Manager, ECR)."
  type        = string
}

variable "ecr_repository_url" {
  description = "URL of the ECR repository holding the application image (registry/repository, no tag)."
  type        = string
}

variable "image_tag" {
  description = <<-EOT
    Immutable image tag (git SHA) to pull and run. Required -- there is no
    "latest" fallback. Must already exist in the ECR repository before any
    instance can boot successfully (a manually pushed image is a prerequisite
    of this milestone; image publishing is not automated until a later
    milestone).
  EOT
  type        = string
}

variable "jwt_parameter_name" {
  description = "Name (path) of the SSM SecureString parameter holding the JWT secret. Not the value -- fetched at boot."
  type        = string
}

variable "db_master_secret_arn" {
  description = "ARN of the RDS-managed Secrets Manager secret holding the master password. Not the value -- fetched at boot."
  type        = string
}

variable "db_address" {
  description = "RDS connection hostname."
  type        = string
}

variable "db_port" {
  description = "RDS connection port."
  type        = number
  default     = 5432
}

variable "db_name" {
  description = "Name of the application database."
  type        = string
}

variable "s3_bucket_name" {
  description = "Name of the pet-images S3 bucket (the application's S3_BUCKET_NAME)."
  type        = string
}

variable "app_port" {
  description = "TCP port the application container listens on / is published on."
  type        = number
  default     = 8000
}

variable "log_level" {
  description = "CloudPet application log level."
  type        = string
  default     = "INFO"
}

variable "jwt_access_token_expire_minutes" {
  description = "Access token lifetime in minutes."
  type        = number
  default     = 30
}

variable "instance_type" {
  description = "EC2 instance type. Graviton/ARM64 per project convention."
  type        = string
  default     = "t4g.small"
}

variable "root_volume_size" {
  description = "Root EBS volume size in GiB."
  type        = number
  default     = 20
}

variable "min_size" {
  description = "ASG minimum capacity."
  type        = number
  default     = 1
}

variable "desired_capacity" {
  description = "ASG desired capacity. A value of 1 does not provide application-level high availability."
  type        = number
  default     = 1
}

variable "max_size" {
  description = "ASG maximum capacity."
  type        = number
  default     = 2
}

variable "health_check_grace_period" {
  description = "Seconds to wait after instance launch before ELB health checks can fail it out of service (covers image pull + boot)."
  type        = number
  default     = 300
}

variable "tags" {
  description = "Extra tags merged onto every resource, on top of provider default_tags."
  type        = map(string)
  default     = {}
}
