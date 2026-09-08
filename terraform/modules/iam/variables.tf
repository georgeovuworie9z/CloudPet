variable "name_prefix" {
  description = "Prefix for IAM resource names / Name tags, e.g. \"cloudpet-production\"."
  type        = string
}

variable "pet_images_bucket_arn" {
  description = <<-EOT
    Exact ARN of the pet-images S3 bucket (3N-6). When non-empty the S3 object
    policy targets "<arn>/*". When empty it falls back to the naming pattern
    "arn:aws:s3:::<name_prefix>-pet-images-*/*" so this module can land before
    the bucket exists.
  EOT
  type        = string
  default     = ""
}

variable "ecr_repository_arn" {
  description = <<-EOT
    Exact ARN of the ECR repository (3N-5). When non-empty the ECR pull policy
    targets it directly. When empty it falls back to
    "arn:aws:ecr:<region>:<account>:repository/<name_prefix>-*".
  EOT
  type        = string
  default     = ""
}

variable "log_group_name" {
  description = "CloudWatch Logs group name the instance may write streams into (group itself is created by the 3N-11 monitoring module)."
  type        = string
  default     = "/cloudpet/production"
}

variable "tags" {
  description = "Extra tags merged onto every resource, on top of provider default_tags."
  type        = map(string)
  default     = {}
}
