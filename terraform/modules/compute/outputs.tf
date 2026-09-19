output "asg_name" {
  description = "Name of the application Auto Scaling Group."
  value       = aws_autoscaling_group.app.name
}

output "asg_arn" {
  description = "ARN of the application Auto Scaling Group."
  value       = aws_autoscaling_group.app.arn
}

output "launch_template_id" {
  description = "ID of the application launch template."
  value       = aws_launch_template.app.id
}

output "launch_template_latest_version" {
  description = "Latest version number of the application launch template."
  value       = aws_launch_template.app.latest_version
}
