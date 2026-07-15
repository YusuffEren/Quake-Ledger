variable "project_id" {
  type        = string
  description = "GCP proje ID'si — zorunlu."
}

variable "region" {
  type        = string
  default     = "europe-west1"
  description = "Cloud Run ve Scheduler için varsayılan region."
}

variable "bucket_name" {
  type        = string
  default     = "quake-ledger-raw"
  description = "Ham veri bucket adı (project_id prefix olarak eklenir)."
}

variable "ingestion_schedule_usgs" {
  type        = string
  default     = "*/15 * * * *"
  description = "USGS ingestion cron schedule (UTC)."
}

variable "ingestion_schedule_kandilli" {
  type        = string
  default     = "*/15 * * * *"
  description = "Kandilli ingestion cron schedule (UTC)."
}

variable "ingestion_schedule_emsc" {
  type        = string
  default     = "*/15 * * * *"
  description = "EMSC ingestion cron schedule (UTC)."
}

variable "cloud_run_image" {
  type        = string
  description = "Ingestion container image URL (Artifact Registry). Zorunlu."
}