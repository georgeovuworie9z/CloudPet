output "repository_url" {
  description = "Registry URL of the repository (account.dkr.ecr.region.amazonaws.com/name)."
  value       = aws_ecr_repository.api.repository_url
}

output "repository_arn" {
  description = "ARN of the ECR repository."
  value       = aws_ecr_repository.api.arn
}

output "repository_name" {
  description = "Name of the ECR repository."
  value       = aws_ecr_repository.api.name
}
