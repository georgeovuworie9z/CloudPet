output "jwt_secret_key_parameter_name" {
  description = "Name (path) of the SSM SecureString parameter holding the JWT secret."
  value       = aws_ssm_parameter.jwt_secret_key.name
}

output "jwt_secret_key_parameter_arn" {
  description = "ARN of the SSM SecureString parameter holding the JWT secret."
  value       = aws_ssm_parameter.jwt_secret_key.arn
}
