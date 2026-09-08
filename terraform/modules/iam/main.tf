# EC2 application instance role for CloudPet.
#
# Least-privilege identity for the future EC2/ASG app instances (3N-10):
#   - SSM Session Manager (no SSH, no port 22) via the AWS-managed policy
#   - ECR image pull
#   - CloudWatch Logs stream writes (the log group is created by 3N-11)
#   - S3 object access on the pet-images bucket (3N-6)
#
# No ALB/EC2/RDS/ECR/S3/log-group resources are created here; nothing consumes
# the instance profile until the compute milestone.

data "aws_caller_identity" "current" {}

data "aws_region" "current" {}

locals {
  ecr_repository_arn = var.ecr_repository_arn != "" ? var.ecr_repository_arn : "arn:aws:ecr:${data.aws_region.current.region}:${data.aws_caller_identity.current.account_id}:repository/${var.name_prefix}-*"

  log_group_arn = "arn:aws:logs:${data.aws_region.current.region}:${data.aws_caller_identity.current.account_id}:log-group:${var.log_group_name}:*"

  pet_images_object_arn = var.pet_images_bucket_arn != "" ? "${var.pet_images_bucket_arn}/*" : "arn:aws:s3:::${var.name_prefix}-pet-images-*/*"
}

resource "aws_iam_role" "app_instance" {
  name = "${var.name_prefix}-app-instance-role"

  assume_role_policy = jsonencode({
    Version = "2012-10-17"
    Statement = [
      {
        Effect    = "Allow"
        Principal = { Service = "ec2.amazonaws.com" }
        Action    = "sts:AssumeRole"
      },
    ]
  })

  tags = merge(var.tags, { Name = "${var.name_prefix}-app-instance-role" })
}

# SSM Session Manager (agent registration + sessions). The only AWS-managed
# policy used in this milestone.
resource "aws_iam_role_policy_attachment" "ssm" {
  role       = aws_iam_role.app_instance.name
  policy_arn = "arn:aws:iam::aws:policy/AmazonSSMManagedInstanceCore"
}

resource "aws_iam_policy" "app_instance" {
  name        = "${var.name_prefix}-app-instance-policy"
  description = "CloudPet EC2 app: ECR pull, CloudWatch Logs write, pet-images S3 object access."

  policy = jsonencode({
    Version = "2012-10-17"
    Statement = [
      {
        Sid      = "EcrAuthToken"
        Effect   = "Allow"
        Action   = "ecr:GetAuthorizationToken"
        Resource = "*"
      },
      {
        Sid    = "EcrImagePull"
        Effect = "Allow"
        Action = [
          "ecr:BatchCheckLayerAvailability",
          "ecr:GetDownloadUrlForLayer",
          "ecr:BatchGetImage",
        ]
        Resource = local.ecr_repository_arn
      },
      {
        Sid    = "CloudWatchLogsWrite"
        Effect = "Allow"
        Action = [
          "logs:CreateLogStream",
          "logs:PutLogEvents",
          "logs:DescribeLogStreams",
        ]
        Resource = local.log_group_arn
      },
      {
        Sid    = "PetImagesObjectAccess"
        Effect = "Allow"
        Action = [
          "s3:GetObject",
          "s3:PutObject",
          "s3:DeleteObject",
        ]
        Resource = local.pet_images_object_arn
      },
    ]
  })

  tags = merge(var.tags, { Name = "${var.name_prefix}-app-instance-policy" })
}

resource "aws_iam_role_policy_attachment" "app_instance" {
  role       = aws_iam_role.app_instance.name
  policy_arn = aws_iam_policy.app_instance.arn
}

resource "aws_iam_instance_profile" "app" {
  name = "${var.name_prefix}-app-instance-profile"
  role = aws_iam_role.app_instance.name

  tags = merge(var.tags, { Name = "${var.name_prefix}-app-instance-profile" })
}
