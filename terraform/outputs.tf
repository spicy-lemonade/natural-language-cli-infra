output "bronze_bucket_name" {
  description = "Name of the bronze layer storage bucket"
  value       = google_storage_bucket.nlcli_ml_training_bronze.name
}

output "bronze_bucket_url" {
  description = "GCS URL of the bronze layer bucket"
  value       = google_storage_bucket.nlcli_ml_training_bronze.url
}

output "bronze_bucket_self_link" {
  description = "Self link of the bronze bucket for IAM bindings"
  value       = google_storage_bucket.nlcli_ml_training_bronze.self_link
}

output "silver_bucket_name" {
  description = "Name of the silver layer storage bucket"
  value       = google_storage_bucket.nlcli_ml_training_silver.name
}

output "silver_bucket_url" {
  description = "GCS URL of the silver layer bucket"
  value       = google_storage_bucket.nlcli_ml_training_silver.url
}

output "silver_bucket_self_link" {
  description = "Self link of the silver bucket for IAM bindings"
  value       = google_storage_bucket.nlcli_ml_training_silver.self_link
}

output "gold_bucket_name" {
  description = "Name of the gold layer storage bucket"
  value       = google_storage_bucket.nlcli_ml_training_gold.name
}

output "gold_bucket_url" {
  description = "GCS URL of the gold layer bucket"
  value       = google_storage_bucket.nlcli_ml_training_gold.url
}

output "gold_bucket_self_link" {
  description = "Self link of the gold bucket for IAM bindings"
  value       = google_storage_bucket.nlcli_ml_training_gold.self_link
}
