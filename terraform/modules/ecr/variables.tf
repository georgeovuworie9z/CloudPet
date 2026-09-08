variable "name_prefix" {
  description = "Prefix for the repository name / Name tag, e.g. \"cloudpet-production\"."
  type        = string
}

variable "image_tag_mutability" {
  description = "ECR tag mutability. IMMUTABLE means a tag can be pushed once and never moved (git-SHA deploy tags)."
  type        = string
  default     = "IMMUTABLE"
}

variable "scan_on_push" {
  description = "Run ECR basic vulnerability scanning automatically on each image push."
  type        = bool
  default     = true
}

variable "untagged_expiry_days" {
  description = "Expire untagged images this many days after they were pushed."
  type        = number
  default     = 7
}

variable "max_image_count" {
  description = "Keep at most this many images in the repository; older ones are expired."
  type        = number
  default     = 30
}

variable "tags" {
  description = "Extra tags merged onto the repository, on top of provider default_tags."
  type        = map(string)
  default     = {}
}
