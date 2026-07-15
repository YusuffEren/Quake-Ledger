variable "project_id" {
  type        = string
  description = "GCP proje ID'si."
}

variable "bucket_name" {
  type        = string
  description = "Bucket adı (project_id prefix olarak eklenir)."
}

variable "location" {
  type        = string
  default     = "EU"
  description = "Bucket lokasyonu — multi-region önerilir."
}