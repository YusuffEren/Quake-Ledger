output "bucket_name" {
  value       = google_storage_bucket.quake_raw.name
  description = "Oluşturulan bucket adı."
}

output "bucket_url" {
  value       = google_storage_bucket.quake_raw.url
  description = "Bucket URL'i."
}