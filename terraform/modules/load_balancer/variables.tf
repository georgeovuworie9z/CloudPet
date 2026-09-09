variable "name_prefix" {
  description = "Prefix for load-balancer resource names / Name tags, e.g. \"cloudpet-production\"."
  type        = string
}

variable "vpc_id" {
  description = "ID of the VPC the target group belongs to."
  type        = string
}

variable "subnet_ids" {
  description = "Public subnet IDs (>= 2, in >= 2 AZs) the internet-facing ALB is placed in."
  type        = list(string)
}

variable "security_group_ids" {
  description = "Security group IDs to attach to the ALB (the ALB SG from the security module)."
  type        = list(string)
}

variable "app_port" {
  description = "TCP port the application listens on; the target-group port and the ALB SG egress port."
  type        = number
  default     = 8000
}

variable "health_check_path" {
  description = "HTTP path the target group health check requests."
  type        = string
  default     = "/health"
}

variable "certificate_arn" {
  description = <<-EOT
    ACM certificate ARN for HTTPS. When empty (the default) the module creates
    only an HTTP listener that forwards to the target group. When supplied, the
    HTTP listener becomes an HTTP -> HTTPS redirect and an HTTPS listener on 443
    forwards to the target group.
  EOT
  type        = string
  default     = ""
}

variable "enable_deletion_protection" {
  description = "Block deletion of the ALB via the API/console until disabled."
  type        = bool
  default     = true
}

variable "tags" {
  description = "Extra tags merged onto every resource, on top of provider default_tags."
  type        = map(string)
  default     = {}
}
