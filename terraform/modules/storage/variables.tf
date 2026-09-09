variable "name_prefix" {
  description = "Prefix for the bucket name / Name tag, e.g. \"cloudpet-production\"."
  type        = string
}

variable "abort_incomplete_multipart_upload_days" {
  description = "Abort (and stop billing for) incomplete multipart uploads this many days after they were initiated."
  type        = number
  default     = 7
}

variable "tags" {
  description = "Extra tags merged onto the bucket, on top of provider default_tags."
  type        = map(string)
  default     = {}
}
