variable "name_prefix" {
  description = "Prefix for Name tags / resource identifiers, e.g. \"cloudpet-production\"."
  type        = string
}

variable "vpc_id" {
  description = "ID of the VPC the security groups belong to."
  type        = string
}

variable "app_port" {
  description = "TCP port the FastAPI container listens on behind the ALB."
  type        = number
  default     = 8000
}

variable "postgres_port" {
  description = "TCP port PostgreSQL / RDS listens on."
  type        = number
  default     = 5432
}

variable "alb_ingress_cidrs" {
  description = "IPv4 CIDRs allowed to reach the ALB on 80/443. Public by default."
  type        = list(string)
  default     = ["0.0.0.0/0"]
}

variable "tags" {
  description = "Extra tags merged onto every resource, on top of provider default_tags."
  type        = map(string)
  default     = {}
}
