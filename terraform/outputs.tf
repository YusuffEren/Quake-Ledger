output "raw_bucket_name" {
  value       = module.gcs.bucket_name
  description = "Ham verinin yazıldığı GCS bucket adı."
}

output "cloud_run_url" {
  value       = module.cloud_run.service_url
  description = "Ingestion Cloud Run servisinin URL'i."
}

output "scheduler_job_names" {
  value = {
    usgs     = module.scheduler.usgs_job_name
    kandilli = module.scheduler.kandilli_job_name
  }
  description = "Cloud Scheduler job isimleri."
}