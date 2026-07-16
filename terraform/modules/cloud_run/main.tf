# Ingestion servisi için service account — least-privilege IAM.
resource "google_service_account" "ingestion_sa" {
  account_id   = "quake-ingestion-sa"
  project      = var.project_id
  display_name = "Quake-Ledger ingestion service account"
}

# Raw bucket'a yazma yetkisi.
resource "google_project_iam_member" "ingestion_object_creator" {
  project = var.project_id
  role    = "roles/storage.objectCreator"
  member  = "serviceAccount:${google_service_account.ingestion_sa.email}"
}

# BigQuery, GCS'deki staging JSONL dosyasını okumak için objectViewer gerekir.
resource "google_project_iam_member" "ingestion_object_viewer" {
  project = var.project_id
  role    = "roles/storage.objectViewer"
  member  = "serviceAccount:${google_service_account.ingestion_sa.email}"
}

# BigQuery job çalıştırma yetkisi — proje seviyesinde zorunlu (jobUser, sorgu çalıştırmanın önkoşulu).
resource "google_project_iam_member" "ingestion_bq_job_user" {
  project = var.project_id
  role    = "roles/bigquery.jobUser"
  member  = "serviceAccount:${google_service_account.ingestion_sa.email}"
}

# BigQuery raw dataset'e data editor — least-privilege: sadece raw dataset'i, proje geneli değil.
resource "google_bigquery_dataset_iam_member" "ingestion_bq_raw_editor" {
  dataset_id = var.raw_dataset_id
  role       = "roles/bigquery.dataEditor"
  member     = "serviceAccount:${google_service_account.ingestion_sa.email}"
}

# Cloud Run servisi — ingestion endpoint'lerini barındırır.
resource "google_cloud_run_service" "ingestion" {
  name     = "quake-ingestion"
  project  = var.project_id
  location = var.region

  autogenerate_revision_name = true

  template {
    spec {
      service_account_name  = google_service_account.ingestion_sa.email
      container_concurrency = 1
      timeout_seconds       = 300

      containers {
        image = var.cloud_run_image

        env {
          name  = "PROJECT_ID"
          value = var.project_id
        }

        env {
          name  = "RAW_BUCKET"
          value = var.raw_bucket_name
        }

        env {
          name  = "BQ_DATASET"
          value = var.bq_dataset
        }

        ports {
          container_port = 8080
        }

        resources {
          limits = {
            "memory" = "512Mi"
            "cpu"    = "1"
          }
        }

        # Sağlık kontrolü — servisin hazır olduğunu doğrular.
        startup_probe {
          http_get {
            path = "/health"
          }
          initial_delay_seconds = 10
          timeout_seconds       = 5
          period_seconds        = 10
        }
      }
    }

    # Maliyet optimizasyonu — boşta 0 instance.
    metadata {
      annotations = {
        "autoscaling.minInstances" = "0"
        "autoscaling.maxInstances" = "1"
      }
    }
  }

  traffic {
    percent         = 100
    latest_revision = true
  }
}