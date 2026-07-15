output "usgs_job_name" {
  value       = google_cloud_scheduler_job.usgs_ingestion.name
  description = "USGS ingestion scheduler job adı."
}

output "kandilli_job_name" {
  value       = google_cloud_scheduler_job.kandilli_ingestion.name
  description = "Kandilli ingestion scheduler job adı."
}

output "scheduler_sa_email" {
  value       = google_service_account.scheduler_sa.email
  description = "Scheduler service account e-postası."
}