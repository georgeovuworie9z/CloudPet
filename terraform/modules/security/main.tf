# Three tiers of security group for the ALB -> EC2/app -> RDS path.
#
# Every aws_security_group is created rule-free and each rule is its own
# aws_vpc_security_group_(ingress|egress)_rule resource. This keeps the
# ALB <-> app mutual reference from forming a Terraform dependency cycle
# (the SG resources never reference each other; only the rule resources do).
#
# Terraform revokes the AWS default allow-all egress on every SG it creates,
# so each SG ends up with exactly the rules declared below (the RDS SG has
# no egress at all). This module provisions no ALB, EC2, or RDS resources.

# ------------------------------- ALB SG -----------------------------------
resource "aws_security_group" "alb" {
  name        = "${var.name_prefix}-alb-sg"
  description = "CloudPet ALB: public HTTP/HTTPS in; app port out to EC2."
  vpc_id      = var.vpc_id

  tags = merge(var.tags, {
    Name = "${var.name_prefix}-alb-sg"
    Tier = "public"
  })
}

resource "aws_vpc_security_group_ingress_rule" "alb_http" {
  count             = length(var.alb_ingress_cidrs)
  security_group_id = aws_security_group.alb.id
  description       = "HTTP from the internet"
  cidr_ipv4         = var.alb_ingress_cidrs[count.index]
  ip_protocol       = "tcp"
  from_port         = 80
  to_port           = 80
}

resource "aws_vpc_security_group_ingress_rule" "alb_https" {
  count             = length(var.alb_ingress_cidrs)
  security_group_id = aws_security_group.alb.id
  description       = "HTTPS from the internet"
  cidr_ipv4         = var.alb_ingress_cidrs[count.index]
  ip_protocol       = "tcp"
  from_port         = 443
  to_port           = 443
}

resource "aws_vpc_security_group_egress_rule" "alb_to_app" {
  security_group_id            = aws_security_group.alb.id
  description                  = "Forward to the app container port"
  referenced_security_group_id = aws_security_group.app.id
  ip_protocol                  = "tcp"
  from_port                    = var.app_port
  to_port                      = var.app_port
}

# ----------------------------- EC2 / app SG ------------------------------
resource "aws_security_group" "app" {
  name        = "${var.name_prefix}-app-sg"
  description = "CloudPet app: app port in from ALB; Postgres + HTTPS out."
  vpc_id      = var.vpc_id

  tags = merge(var.tags, {
    Name = "${var.name_prefix}-app-sg"
    Tier = "private-app"
  })
}

resource "aws_vpc_security_group_ingress_rule" "app_from_alb" {
  security_group_id            = aws_security_group.app.id
  description                  = "App port from the ALB only"
  referenced_security_group_id = aws_security_group.alb.id
  ip_protocol                  = "tcp"
  from_port                    = var.app_port
  to_port                      = var.app_port
}

resource "aws_vpc_security_group_egress_rule" "app_to_rds" {
  security_group_id            = aws_security_group.app.id
  description                  = "PostgreSQL to the RDS tier"
  referenced_security_group_id = aws_security_group.rds.id
  ip_protocol                  = "tcp"
  from_port                    = var.postgres_port
  to_port                      = var.postgres_port
}

resource "aws_vpc_security_group_egress_rule" "app_https_out" {
  security_group_id = aws_security_group.app.id
  description       = "HTTPS to AWS service endpoints (ECR, SSM, CloudWatch, S3)"
  cidr_ipv4         = "0.0.0.0/0"
  ip_protocol       = "tcp"
  from_port         = 443
  to_port           = 443
}

# ------------------------------- RDS SG ----------------------------------
resource "aws_security_group" "rds" {
  name        = "${var.name_prefix}-rds-sg"
  description = "CloudPet RDS: PostgreSQL in from the app tier only. No egress."
  vpc_id      = var.vpc_id

  tags = merge(var.tags, {
    Name = "${var.name_prefix}-rds-sg"
    Tier = "private-db"
  })
}

resource "aws_vpc_security_group_ingress_rule" "rds_from_app" {
  security_group_id            = aws_security_group.rds.id
  description                  = "PostgreSQL from the app tier only"
  referenced_security_group_id = aws_security_group.app.id
  ip_protocol                  = "tcp"
  from_port                    = var.postgres_port
  to_port                      = var.postgres_port
}
