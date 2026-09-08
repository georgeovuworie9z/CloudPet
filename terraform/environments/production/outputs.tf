output "vpc_id" {
  description = "The production VPC ID."
  value       = module.networking.vpc_id
}

output "vpc_cidr" {
  description = "The production VPC CIDR block."
  value       = module.networking.vpc_cidr
}

output "public_subnet_ids" {
  description = "Public subnet IDs (ALB, NAT), ordered by AZ."
  value       = module.networking.public_subnet_ids
}

output "private_app_subnet_ids" {
  description = "Private application subnet IDs (EC2 / ASG), ordered by AZ."
  value       = module.networking.private_app_subnet_ids
}

output "private_db_subnet_ids" {
  description = "Private database subnet IDs (RDS), ordered by AZ."
  value       = module.networking.private_db_subnet_ids
}

output "internet_gateway_id" {
  description = "ID of the Internet Gateway."
  value       = module.networking.internet_gateway_id
}

output "s3_gateway_endpoint_id" {
  description = "ID of the S3 Gateway VPC endpoint."
  value       = module.networking.s3_gateway_endpoint_id
}

output "nat_gateway_public_ips" {
  description = "NAT Gateway public IP(s); empty until create_nat_gateway is enabled."
  value       = module.networking.nat_gateway_public_ips
}

output "alb_security_group_id" {
  description = "ID of the ALB security group."
  value       = module.security.alb_security_group_id
}

output "app_security_group_id" {
  description = "ID of the EC2/app security group."
  value       = module.security.app_security_group_id
}

output "rds_security_group_id" {
  description = "ID of the RDS security group."
  value       = module.security.rds_security_group_id
}
