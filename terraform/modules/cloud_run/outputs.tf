output "service_name" {
  value       = google_cloud_run_service.ingestion.name
  description = "Cloud Run servis adı."
}

output "service_url" {
  value       = google_cloud_run_service.ingestion.status[0].url
  description = "Cloud Run servis URL'i."
}

output "service_account_email" {
  value       = google_service_account.ingestion_sa.email
  description = "Ingestion service account e-postası."
}