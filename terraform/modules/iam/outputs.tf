output "instance_role_arn" {
  description = "ARN of the EC2 application instance role."
  value       = aws_iam_role.app_instance.arn
}

output "instance_role_name" {
  description = "Name of the EC2 application instance role."
  value       = aws_iam_role.app_instance.name
}

output "instance_profile_arn" {
  description = "ARN of the EC2 application instance profile."
  value       = aws_iam_instance_profile.app.arn
}

output "instance_profile_name" {
  description = "Name of the EC2 application instance profile (for launch templates / ASGs)."
  value       = aws_iam_instance_profile.app.name
}
