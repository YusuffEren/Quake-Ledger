variable "project_id" {
  type        = string
  description = "GCP proje ID'si."
}

variable "region" {
  type        = string
  description = "Scheduler region."
}

variable "cloud_run_url" {
  type        = string
  description = "Cloud Run servis URL'i (HTTP target için)."
}

variable "cloud_run_service_name" {
  type        = string
  description = "Cloud Run servis adı (IAM binding için)."
}

variable "ingestion_schedule_usgs" {
  type        = string
  description = "USGS cron schedule."
}

variable "ingestion_schedule_kandilli" {
  type        = string
  description = "Kandilli cron schedule."
}