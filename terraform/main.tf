# Root module — tüm alt modülleri burada birleştirir.
# API'lerin hazır olması için google_project_service'e bağlıyoruz (depends_on).

module "gcs" {
  source      = "./modules/gcs"
  project_id  = var.project_id
  bucket_name = var.bucket_name

  depends_on = [google_project_service.enabled_apis]
}

module "bigquery" {
  source          = "./modules/bigquery"
  project_id      = var.project_id
  dataset_location = "EU"

  depends_on = [google_project_service.enabled_apis]
}

module "cloud_run" {
  source          = "./modules/cloud_run"
  project_id      = var.project_id
  region          = var.region
  cloud_run_image = var.cloud_run_image
  raw_bucket_name = module.gcs.bucket_name
  bq_dataset      = "raw"
  raw_dataset_id  = module.bigquery.raw_dataset_id

  depends_on = [google_project_service.enabled_apis]
}

module "scheduler" {
  source                       = "./modules/scheduler"
  project_id                   = var.project_id
  region                       = var.region
  cloud_run_url                = module.cloud_run.service_url
  cloud_run_service_name       = module.cloud_run.service_name
  ingestion_schedule_usgs      = var.ingestion_schedule_usgs
  ingestion_schedule_kandilli   = var.ingestion_schedule_kandilli
  ingestion_schedule_emsc       = var.ingestion_schedule_emsc

  depends_on = [google_project_service.enabled_apis]
}