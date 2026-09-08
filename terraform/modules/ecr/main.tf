# Private ECR repository for the CloudPet API container image.
#
# Deploy tags are git SHAs and immutable: a tag is pushed once and never
# moved, so the running image is always traceable to an exact commit. No
# "latest" tag. Pull access is granted by the EC2 instance role (3N-4) via an
# identity-based policy -- this module attaches no repository (resource) policy.
# Image push (GitHub Actions / OIDC) is deferred to 3O.

resource "aws_ecr_repository" "api" {
  name                 = "${var.name_prefix}-api"
  image_tag_mutability = var.image_tag_mutability

  image_scanning_configuration {
    scan_on_push = var.scan_on_push
  }

  encryption_configuration {
    encryption_type = "AES256"
  }

  # The production deployment repository: guard against accidental destroy.
  lifecycle {
    prevent_destroy = true
  }

  tags = merge(var.tags, { Name = "${var.name_prefix}-api" })
}

# Bound repository storage:
#   1. expire untagged images 7 days after push
#   2. keep only the most recent 30 images overall (git-SHA tags defeat
#      prefix matching, so the "keep N" rule is tagStatus = "any" and must
#      hold the highest rule priority)
resource "aws_ecr_lifecycle_policy" "api" {
  repository = aws_ecr_repository.api.name

  policy = jsonencode({
    rules = [
      {
        rulePriority = 1
        description  = "Expire untagged images after ${var.untagged_expiry_days} days"
        selection = {
          tagStatus   = "untagged"
          countType   = "sinceImagePushed"
          countUnit   = "days"
          countNumber = var.untagged_expiry_days
        }
        action = { type = "expire" }
      },
      {
        rulePriority = 2
        description  = "Keep only the most recent ${var.max_image_count} images"
        selection = {
          tagStatus   = "any"
          countType   = "imageCountMoreThan"
          countNumber = var.max_image_count
        }
        action = { type = "expire" }
      },
    ]
  })
}
