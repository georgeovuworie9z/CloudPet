# Private PostgreSQL RDS instance for CloudPet.
#
# Lives only in the isolated private-db subnets (no 0.0.0.0/0 route), reachable
# on 5432 solely from the app security group. TLS is enforced server-side
# (rds.force_ssl = 1), matching the application's mandatory sslmode=require in
# production. The master password is generated and rotated by RDS in a managed
# Secrets Manager secret -- it never enters Terraform state or any .tf file.
#
# This module creates no IAM resources: granting the app permission to read the
# master-user secret is a later milestone.

resource "aws_db_subnet_group" "this" {
  name       = "${var.name_prefix}-db"
  subnet_ids = var.subnet_ids

  tags = merge(var.tags, { Name = "${var.name_prefix}-db" })
}

resource "aws_db_parameter_group" "this" {
  name   = "${var.name_prefix}-db"
  family = var.parameter_group_family

  # Reject any non-TLS connection at the server. rds.force_ssl is a static
  # parameter for PostgreSQL, so AWS applies it as pending-reboot; declaring
  # that explicitly avoids a perpetual plan diff against Terraform's default
  # of "immediate".
  parameter {
    name         = "rds.force_ssl"
    value        = "1"
    apply_method = "pending-reboot"
  }

  tags = merge(var.tags, { Name = "${var.name_prefix}-db" })

  lifecycle {
    create_before_destroy = true
  }
}

resource "aws_db_instance" "this" {
  identifier     = "${var.name_prefix}-db"
  engine         = "postgres"
  engine_version = var.engine_version

  instance_class        = var.instance_class
  allocated_storage     = var.allocated_storage
  max_allocated_storage = var.max_allocated_storage
  storage_type          = "gp3"
  storage_encrypted     = true

  db_name                     = var.db_name
  username                    = var.username
  manage_master_user_password = true
  port                        = 5432

  multi_az               = var.multi_az
  db_subnet_group_name   = aws_db_subnet_group.this.name
  vpc_security_group_ids = var.vpc_security_group_ids
  publicly_accessible    = false
  parameter_group_name   = aws_db_parameter_group.this.name

  backup_retention_period     = var.backup_retention_period
  copy_tags_to_snapshot       = true
  auto_minor_version_upgrade  = true
  allow_major_version_upgrade = false
  apply_immediately           = false

  deletion_protection       = var.deletion_protection
  skip_final_snapshot       = var.skip_final_snapshot
  final_snapshot_identifier = var.skip_final_snapshot ? null : "${var.name_prefix}-db-final"

  iam_database_authentication_enabled = false
  performance_insights_enabled        = false
  monitoring_interval                 = 0

  tags = merge(var.tags, { Name = "${var.name_prefix}-db" })

  lifecycle {
    prevent_destroy = true
  }
}
