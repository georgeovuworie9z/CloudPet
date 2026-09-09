variable "parameter_name" {
  description = "Name (path) of the SSM SecureString parameter holding the application JWT secret."
  type        = string
  default     = "/cloudpet/production/JWT_SECRET_KEY"
}

variable "tags" {
  description = "Extra tags merged onto the parameter, on top of provider default_tags."
  type        = map(string)
  default     = {}
}
