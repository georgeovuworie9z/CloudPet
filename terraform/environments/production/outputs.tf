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

output "app_instance_role_arn" {
  description = "ARN of the EC2 application instance role."
  value       = module.iam.instance_role_arn
}

output "app_instance_role_name" {
  description = "Name of the EC2 application instance role."
  value       = module.iam.instance_role_name
}

output "app_instance_profile_arn" {
  description = "ARN of the EC2 application instance profile."
  value       = module.iam.instance_profile_arn
}

output "app_instance_profile_name" {
  description = "Name of the EC2 application instance profile."
  value       = module.iam.instance_profile_name
}

output "ecr_repository_url" {
  description = "Registry URL of the CloudPet API ECR repository."
  value       = module.ecr.repository_url
}

output "ecr_repository_arn" {
  description = "ARN of the CloudPet API ECR repository."
  value       = module.ecr.repository_arn
}

output "ecr_repository_name" {
  description = "Name of the CloudPet API ECR repository."
  value       = module.ecr.repository_name
}

output "pet_images_bucket_name" {
  description = "Name of the pet-images S3 bucket (the application's S3_BUCKET_NAME)."
  value       = module.storage.bucket_name
}

output "pet_images_bucket_arn" {
  description = "ARN of the pet-images S3 bucket."
  value       = module.storage.bucket_arn
}

output "db_endpoint" {
  description = "RDS connection endpoint (host:port)."
  value       = module.database.endpoint
}

output "db_address" {
  description = "RDS connection hostname."
  value       = module.database.address
}

output "db_port" {
  description = "RDS connection port."
  value       = module.database.port
}

output "db_name" {
  description = "Name of the initial database."
  value       = module.database.db_name
}

output "db_master_user_secret_arn" {
  description = "ARN of the RDS-managed Secrets Manager secret holding the master password."
  value       = module.database.master_user_secret_arn
}

output "jwt_secret_parameter_name" {
  description = "Name (path) of the SSM SecureString parameter holding the application JWT secret."
  value       = module.secrets.jwt_secret_key_parameter_name
}

output "jwt_secret_parameter_arn" {
  description = "ARN of the SSM SecureString parameter holding the application JWT secret."
  value       = module.secrets.jwt_secret_key_parameter_arn
}
