variable "project_id" {
  type        = string
  description = "GCP proje ID'si."
}

variable "region" {
  type        = string
  description = "Cloud Run region."
}

variable "cloud_run_image" {
  type        = string
  description = "Ingestion container image URL."
}

variable "raw_bucket_name" {
  type        = string
  description = "Ham veri bucket adı — env var olarak container'a verilir."
}

variable "bq_dataset" {
  type        = string
  description = "BigQuery dataset adı (raw) — env var olarak container'a verilir."
}

variable "raw_dataset_id" {
  type        = string
  description = "BigQuery raw dataset ID'si — dataset seviyesi IAM binding için (least-privilege)."
}