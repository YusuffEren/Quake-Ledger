output "raw_dataset_id" {
  value       = google_bigquery_dataset.raw.dataset_id
  description = "raw dataset ID'si."
}

output "usgs_table_id" {
  value       = google_bigquery_table.raw_usgs.id
  description = "USGS raw tablosunun tam ID'si."
}

output "kandilli_table_id" {
  value       = google_bigquery_table.raw_kandilli.id
  description = "Kandilli raw tablosunun tam ID'si."
}