output "vpc_id" {
  description = "The VPC ID."
  value       = aws_vpc.this.id
}

output "vpc_cidr" {
  description = "The VPC CIDR block."
  value       = aws_vpc.this.cidr_block
}

output "availability_zones" {
  description = "AZs the subnets are spread across."
  value       = var.availability_zones
}

output "public_subnet_ids" {
  description = "Public subnet IDs (ALB, NAT), ordered by AZ."
  value       = aws_subnet.public[*].id
}

output "private_app_subnet_ids" {
  description = "Private application subnet IDs (EC2 / ASG), ordered by AZ."
  value       = aws_subnet.private_app[*].id
}

output "private_db_subnet_ids" {
  description = "Private database subnet IDs (RDS), ordered by AZ."
  value       = aws_subnet.private_db[*].id
}

output "public_route_table_id" {
  description = "ID of the shared public route table."
  value       = aws_route_table.public.id
}

output "private_app_route_table_ids" {
  description = "IDs of the per-AZ private-app route tables."
  value       = aws_route_table.private_app[*].id
}

output "private_db_route_table_id" {
  description = "ID of the shared private-db route table (local routing only)."
  value       = aws_route_table.private_db.id
}

output "internet_gateway_id" {
  description = "ID of the Internet Gateway."
  value       = aws_internet_gateway.this.id
}

output "nat_gateway_ids" {
  description = "IDs of the NAT Gateway(s); empty when create_nat_gateway = false."
  value       = aws_nat_gateway.this[*].id
}

output "nat_gateway_public_ips" {
  description = "Public IP(s) of the NAT Gateway EIP(s); empty when create_nat_gateway = false."
  value       = aws_eip.nat[*].public_ip
}

output "s3_gateway_endpoint_id" {
  description = "ID of the S3 Gateway VPC endpoint."
  value       = aws_vpc_endpoint.s3.id
}
