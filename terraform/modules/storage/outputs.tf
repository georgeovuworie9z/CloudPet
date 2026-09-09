output "bucket_name" {
  description = "Name of the pet-images S3 bucket (the application's S3_BUCKET_NAME)."
  value       = aws_s3_bucket.pet_images.id
}

output "bucket_arn" {
  description = "ARN of the pet-images S3 bucket."
  value       = aws_s3_bucket.pet_images.arn
}

output "bucket_regional_domain_name" {
  description = "Regional domain name of the pet-images S3 bucket."
  value       = aws_s3_bucket.pet_images.bucket_regional_domain_name
}
