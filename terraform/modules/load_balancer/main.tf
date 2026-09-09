# Internet-facing Application Load Balancer for CloudPet.
#
# Spans the two public subnets, uses the ALB security group from the security
# module (public 80/443 in, app port out to the app SG), and forwards to an
# instance target group on the application port. No targets are registered
# here -- the ASG attaches instances to this target group in a later milestone.
#
# HTTPS is deferred: with certificate_arn = "" (the default) the module creates
# a single HTTP listener that forwards to the target group. When a certificate
# is supplied later, the HTTP listener switches to an HTTP -> HTTPS redirect and
# a count-gated HTTPS listener on 443 forwards to the target group.

resource "aws_lb" "this" {
  name               = "${var.name_prefix}-alb"
  load_balancer_type = "application"
  internal           = false

  subnets         = var.subnet_ids
  security_groups = var.security_group_ids

  enable_deletion_protection = var.enable_deletion_protection
  drop_invalid_header_fields = true
  idle_timeout               = 60
  enable_http2               = true

  tags = merge(var.tags, { Name = "${var.name_prefix}-alb" })
}

resource "aws_lb_target_group" "app" {
  name        = "${var.name_prefix}-app-tg"
  target_type = "instance"
  port        = var.app_port
  protocol    = "HTTP"
  vpc_id      = var.vpc_id

  deregistration_delay = 60

  health_check {
    path                = var.health_check_path
    protocol            = "HTTP"
    matcher             = "200"
    interval            = 30
    timeout             = 5
    healthy_threshold   = 3
    unhealthy_threshold = 3
  }

  tags = merge(var.tags, { Name = "${var.name_prefix}-app-tg" })
}

resource "aws_lb_listener" "http" {
  load_balancer_arn = aws_lb.this.arn
  port              = 80
  protocol          = "HTTP"

  # No certificate yet: HTTP forwards straight to the target group.
  dynamic "default_action" {
    for_each = var.certificate_arn == "" ? [1] : []
    content {
      type             = "forward"
      target_group_arn = aws_lb_target_group.app.arn
    }
  }

  # Certificate supplied: HTTP permanently redirects to HTTPS.
  dynamic "default_action" {
    for_each = var.certificate_arn == "" ? [] : [1]
    content {
      type = "redirect"
      redirect {
        port        = "443"
        protocol    = "HTTPS"
        status_code = "HTTP_301"
      }
    }
  }

  tags = merge(var.tags, { Name = "${var.name_prefix}-http" })
}

resource "aws_lb_listener" "https" {
  count = var.certificate_arn == "" ? 0 : 1

  load_balancer_arn = aws_lb.this.arn
  port              = 443
  protocol          = "HTTPS"
  ssl_policy        = "ELBSecurityPolicy-TLS13-1-2-2021-06"
  certificate_arn   = var.certificate_arn

  default_action {
    type             = "forward"
    target_group_arn = aws_lb_target_group.app.arn
  }

  tags = merge(var.tags, { Name = "${var.name_prefix}-https" })
}
