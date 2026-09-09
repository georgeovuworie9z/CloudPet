output "alb_arn" {
  description = "ARN of the Application Load Balancer."
  value       = aws_lb.this.arn
}

output "alb_dns_name" {
  description = "DNS name of the Application Load Balancer."
  value       = aws_lb.this.dns_name
}

output "alb_zone_id" {
  description = "Route 53 hosted-zone ID of the Application Load Balancer (for alias records)."
  value       = aws_lb.this.zone_id
}

output "alb_arn_suffix" {
  description = "ARN suffix of the ALB, for CloudWatch metric dimensions."
  value       = aws_lb.this.arn_suffix
}

output "target_group_arn" {
  description = "ARN of the application target group (the ASG attaches to this)."
  value       = aws_lb_target_group.app.arn
}

output "target_group_arn_suffix" {
  description = "ARN suffix of the target group, for CloudWatch metric dimensions."
  value       = aws_lb_target_group.app.arn_suffix
}

output "http_listener_arn" {
  description = "ARN of the HTTP (:80) listener."
  value       = aws_lb_listener.http.arn
}
