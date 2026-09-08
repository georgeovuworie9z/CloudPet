locals {
  az_count  = length(var.availability_zones)
  nat_count = var.create_nat_gateway ? (var.single_nat_gateway ? 1 : local.az_count) : 0
}

# ----------------------------------- VPC --------------------------------------
resource "aws_vpc" "this" {
  cidr_block           = var.vpc_cidr
  enable_dns_support   = true
  enable_dns_hostnames = true

  tags = merge(var.tags, { Name = "${var.name_prefix}-vpc" })
}

# Lock down the VPC's default security group: no rules, so nothing uses it.
resource "aws_default_security_group" "this" {
  vpc_id = aws_vpc.this.id

  tags = merge(var.tags, { Name = "${var.name_prefix}-default-sg-locked" })
}

# ------------------------------ Internet Gateway ----------------------------
resource "aws_internet_gateway" "this" {
  vpc_id = aws_vpc.this.id

  tags = merge(var.tags, { Name = "${var.name_prefix}-igw" })
}

# --------------------------------- Subnets ---------------------------------
resource "aws_subnet" "public" {
  count                   = local.az_count
  vpc_id                  = aws_vpc.this.id
  cidr_block              = var.public_subnet_cidrs[count.index]
  availability_zone       = var.availability_zones[count.index]
  map_public_ip_on_launch = false

  tags = merge(var.tags, {
    Name = "${var.name_prefix}-public-${var.availability_zones[count.index]}"
    Tier = "public"
  })
}

resource "aws_subnet" "private_app" {
  count             = local.az_count
  vpc_id            = aws_vpc.this.id
  cidr_block        = var.private_app_subnet_cidrs[count.index]
  availability_zone = var.availability_zones[count.index]

  tags = merge(var.tags, {
    Name = "${var.name_prefix}-private-app-${var.availability_zones[count.index]}"
    Tier = "private-app"
  })
}

resource "aws_subnet" "private_db" {
  count             = local.az_count
  vpc_id            = aws_vpc.this.id
  cidr_block        = var.private_db_subnet_cidrs[count.index]
  availability_zone = var.availability_zones[count.index]

  tags = merge(var.tags, {
    Name = "${var.name_prefix}-private-db-${var.availability_zones[count.index]}"
    Tier = "private-db"
  })
}

# ------------------------------- NAT Gateway ------------------------------
resource "aws_eip" "nat" {
  count      = local.nat_count
  domain     = "vpc"
  depends_on = [aws_internet_gateway.this]

  tags = merge(var.tags, { Name = "${var.name_prefix}-nat-eip-${count.index}" })
}

resource "aws_nat_gateway" "this" {
  count         = local.nat_count
  allocation_id = aws_eip.nat[count.index].id
  subnet_id     = aws_subnet.public[count.index].id
  depends_on    = [aws_internet_gateway.this]

  tags = merge(var.tags, { Name = "${var.name_prefix}-nat-${count.index}" })
}

# ------------------------ Route table: public (shared) ------------------
resource "aws_route_table" "public" {
  vpc_id = aws_vpc.this.id

  tags = merge(var.tags, {
    Name = "${var.name_prefix}-public-rt"
    Tier = "public"
  })
}

resource "aws_route" "public_internet" {
  route_table_id         = aws_route_table.public.id
  destination_cidr_block = "0.0.0.0/0"
  gateway_id             = aws_internet_gateway.this.id
}

resource "aws_route_table_association" "public" {
  count          = local.az_count
  subnet_id      = aws_subnet.public[count.index].id
  route_table_id = aws_route_table.public.id
}

# ------------------- Route tables: private-app (one per AZ) ------------
resource "aws_route_table" "private_app" {
  count  = local.az_count
  vpc_id = aws_vpc.this.id

  tags = merge(var.tags, {
    Name = "${var.name_prefix}-private-app-rt-${var.availability_zones[count.index]}"
    Tier = "private-app"
  })
}

resource "aws_route" "private_app_nat" {
  count                  = var.create_nat_gateway ? local.az_count : 0
  route_table_id         = aws_route_table.private_app[count.index].id
  destination_cidr_block = "0.0.0.0/0"
  nat_gateway_id         = aws_nat_gateway.this[var.single_nat_gateway ? 0 : count.index].id
}

resource "aws_route_table_association" "private_app" {
  count          = local.az_count
  subnet_id      = aws_subnet.private_app[count.index].id
  route_table_id = aws_route_table.private_app[count.index].id
}

# ------------- Route table: private-db (shared, local routing only) ----
resource "aws_route_table" "private_db" {
  vpc_id = aws_vpc.this.id

  # No 0.0.0.0/0 route: the database tier has no internet egress.
  tags = merge(var.tags, {
    Name = "${var.name_prefix}-private-db-rt"
    Tier = "private-db"
  })
}

resource "aws_route_table_association" "private_db" {
  count          = local.az_count
  subnet_id      = aws_subnet.private_db[count.index].id
  route_table_id = aws_route_table.private_db.id
}

# --------------------- S3 Gateway VPC Endpoint (free) -----------------
resource "aws_vpc_endpoint" "s3" {
  vpc_id            = aws_vpc.this.id
  service_name      = "com.amazonaws.${var.aws_region}.s3"
  vpc_endpoint_type = "Gateway"
  route_table_ids   = aws_route_table.private_app[*].id

  tags = merge(var.tags, { Name = "${var.name_prefix}-s3-gateway-endpoint" })
}
