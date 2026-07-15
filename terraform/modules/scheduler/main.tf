# Scheduler service account — Cloud Run'i tetiklemek için.
resource "google_service_account" "scheduler_sa" {
  account_id   = "quake-scheduler-sa"
  project      = var.project_id
  display_name = "Quake-Ledger scheduler service account"
}

# Cloud Run servisini invoke yetkisi.
resource "google_cloud_run_service_iam_member" "invoker" {
  project  = var.project_id
  location = var.region
  service  = var.cloud_run_service_name
  role     = "roles/run.invoker"
  member   = "serviceAccount:${google_service_account.scheduler_sa.email}"
}

# Scheduler SA'nın Cloud Run invoke için OIDC token üretebilmesi gerekmez — 
# Cloud Scheduler otomatik olarak OIDC token oluşturur. Sadece run.invoker yeterli.

# --- USGS ingestion job ---
resource "google_cloud_scheduler_job" "usgs_ingestion" {
  name     = "trigger-usgs-ingestion"
  project  = var.project_id
  region   = var.region
  schedule = var.ingestion_schedule_usgs
  time_zone = "UTC"

  http_target {
    http_method = "POST"
    uri         = "${var.cloud_run_url}/ingest/usgs"

    oidc_token {
      service_account_email = google_service_account.scheduler_sa.email
    }
  }

  # Retry: 3 deneme, max 20 dk, 5s-300s backoff.
  retry_config {
    retry_count          = 3
    max_retry_duration   = "1200s" # 20 dk
    min_backoff_duration = "5s"
    max_backoff_duration = "300s"
  }
}

# --- Kandilli ingestion job ---
resource "google_cloud_scheduler_job" "kandilli_ingestion" {
  name     = "trigger-kandilli-ingestion"
  project  = var.project_id
  region   = var.region
  schedule = var.ingestion_schedule_kandilli
  time_zone = "UTC"

  http_target {
    http_method = "POST"
    uri         = "${var.cloud_run_url}/ingest/kandilli"

    oidc_token {
      service_account_email = google_service_account.scheduler_sa.email
    }
  }

  retry_config {
    retry_count          = 3
    max_retry_duration   = "1200s"
    min_backoff_duration = "5s"
    max_backoff_duration = "300s"
  }
}

# --- EMSC ingestion job ---
resource "google_cloud_scheduler_job" "emsc_ingestion" {
  name     = "trigger-emsc-ingestion"
  project  = var.project_id
  region   = var.region
  schedule = var.ingestion_schedule_emsc
  time_zone = "UTC"

  http_target {
    http_method = "POST"
    uri         = "${var.cloud_run_url}/ingest/emsc"

    oidc_token {
      service_account_email = google_service_account.scheduler_sa.email
    }
  }

  retry_config {
    retry_count          = 3
    max_retry_duration   = "1200s"
    min_backoff_duration = "5s"
    max_backoff_duration = "300s"
  }
}