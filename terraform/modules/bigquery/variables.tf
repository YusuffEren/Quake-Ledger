variable "project_id" {
  type        = string
  description = "GCP proje ID'si."
}

variable "dataset_location" {
  type        = string
  default     = "EU"
  description = "BigQuery dataset lokasyonu."
}