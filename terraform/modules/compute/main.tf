# EC2 application compute for CloudPet: a launch template + Auto Scaling
# Group in the private application subnets, registered with the existing ALB
# target group.
#
# No SSH, no public IP: instances are reachable only via SSM Session Manager
# (the instance role already grants this) and receive traffic only from the
# ALB on the app port (the app security group already enforces this). Secrets
# (JWT signing key, RDS master password) are fetched at boot by the instance
# role -- only their identifiers (an SSM parameter name, a Secrets Manager
# ARN) are baked into user_data, never their values. Database migrations are
# NOT run from user_data; they are applied manually via SSM Session Manager.

data "aws_ssm_parameter" "al2023_arm64" {
  name = "/aws/service/ami-amazon-linux-latest/al2023-ami-kernel-default-arm64"
}

locals {
  user_data = templatefile("${path.module}/templates/user_data.sh.tftpl", {
    aws_region                      = var.aws_region
    ecr_repository_url              = var.ecr_repository_url
    image_tag                       = var.image_tag
    app_port                        = var.app_port
    jwt_parameter_name              = var.jwt_parameter_name
    db_master_secret_arn            = var.db_master_secret_arn
    db_address                      = var.db_address
    db_port                         = var.db_port
    db_name                         = var.db_name
    s3_bucket_name                  = var.s3_bucket_name
    log_level                       = var.log_level
    jwt_access_token_expire_minutes = var.jwt_access_token_expire_minutes
  })
}

resource "aws_launch_template" "app" {
  name_prefix   = "${var.name_prefix}-app-"
  image_id      = data.aws_ssm_parameter.al2023_arm64.value
  instance_type = var.instance_type

  iam_instance_profile {
    name = var.instance_profile_name
  }

  vpc_security_group_ids = var.security_group_ids

  # No key_name: SSM Session Manager only, no SSH.

  metadata_options {
    http_endpoint               = "enabled"
    http_tokens                 = "required"
    http_put_response_hop_limit = 2
  }

  block_device_mappings {
    device_name = "/dev/xvda"

    ebs {
      volume_size           = var.root_volume_size
      volume_type           = "gp3"
      encrypted             = true
      delete_on_termination = true
    }
  }

  monitoring {
    enabled = false
  }

  user_data = base64encode(local.user_data)

  tag_specifications {
    resource_type = "instance"
    tags          = merge(var.tags, { Name = "${var.name_prefix}-app" })
  }

  tag_specifications {
    resource_type = "volume"
    tags          = merge(var.tags, { Name = "${var.name_prefix}-app" })
  }

  tags = merge(var.tags, { Name = "${var.name_prefix}-app-lt" })

  lifecycle {
    create_before_destroy = true
  }
}

resource "aws_autoscaling_group" "app" {
  name                = "${var.name_prefix}-app-asg"
  vpc_zone_identifier = var.subnet_ids

  min_size         = var.min_size
  max_size         = var.max_size
  desired_capacity = var.desired_capacity

  launch_template {
    id      = aws_launch_template.app.id
    version = "$Latest"
  }

  target_group_arns         = var.target_group_arns
  health_check_type         = "ELB"
  health_check_grace_period = var.health_check_grace_period

  instance_refresh {
    strategy = "Rolling"
    preferences {
      min_healthy_percentage = 50
    }
  }

  tag {
    key                 = "Name"
    value               = "${var.name_prefix}-app"
    propagate_at_launch = true
  }

  dynamic "tag" {
    for_each = var.tags
    content {
      key                 = tag.key
      value               = tag.value
      propagate_at_launch = true
    }
  }
}
