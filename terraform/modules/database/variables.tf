variable "name_prefix" {
  description = "Prefix for RDS resource names / Name tags, e.g. \"cloudpet-production\"."
  type        = string
}

variable "subnet_ids" {
  description = "Private database subnet IDs (>= 2, in >= 2 AZs) for the DB subnet group."
  type        = list(string)
}

variable "vpc_security_group_ids" {
  description = "Security group IDs to attach to the DB instance (the RDS SG from the security module)."
  type        = list(string)
}

variable "engine_version" {
  description = "PostgreSQL engine version. Major-only (\"17\") lets AWS pick the latest supported minor."
  type        = string
  default     = "17"
}

variable "parameter_group_family" {
  description = "DB parameter group family; must match the engine major version."
  type        = string
  default     = "postgres17"
}

variable "instance_class" {
  description = "RDS instance class. Graviton/ARM64 (t4g) by project convention."
  type        = string
  default     = "db.t4g.micro"
}

variable "allocated_storage" {
  description = "Initial storage in GiB."
  type        = number
  default     = 20
}

variable "max_allocated_storage" {
  description = "Upper bound (GiB) for storage autoscaling. Set equal to allocated_storage to disable."
  type        = number
  default     = 100
}

variable "multi_az" {
  description = "Run a synchronous standby in a second AZ. Off by default for cost."
  type        = bool
  default     = false
}

variable "db_name" {
  description = "Name of the initial database."
  type        = string
  default     = "cloudpet"
}

variable "username" {
  description = "Master username. The password is managed by RDS (Secrets Manager), never by Terraform."
  type        = string
  default     = "cloudpet"
}

variable "backup_retention_period" {
  description = "Days to retain automated backups."
  type        = number
  default     = 7
}

variable "deletion_protection" {
  description = "Block deletion of the instance via the API/console until disabled."
  type        = bool
  default     = true
}

variable "skip_final_snapshot" {
  description = "Skip the final snapshot on deletion. Kept false for a production posture."
  type        = bool
  default     = false
}

variable "tags" {
  description = "Extra tags merged onto every resource, on top of provider default_tags."
  type        = map(string)
  default     = {}
}
