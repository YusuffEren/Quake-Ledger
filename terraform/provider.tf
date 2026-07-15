# GCP provider — europe-west1 region olarak sabitlenmedi, var.region'dan gelir.
terraform {
  required_version = ">= 1.8"

  required_providers {
    google = {
      source  = "hashicorp/google"
      version = "~> 5.0"
    }
  }

  # State GCS'te tutulur — takım içi paylaşım ve lock için.
  # DİKKAT: Bu bucket Terraform tarafından yönetilmez;
  # ilk `terraform init` öncesinde manuel oluşturulmalı (versioning açık):
  #   gcloud storage buckets create gs://deprem-502519-tfstate \
  #     --project=deprem-502519 --location=EU --uniform-bucket-level-access
  backend "gcs" {
    bucket = "deprem-502519-tfstate"
    prefix = "terraform/state"
  }
}

provider "google" {
  project = var.project_id
  region  = var.region
}

# API'ler proje seviyesinde açık olmalı — burada yalnızca bildirim amaçlı.
resource "google_project_service" "enabled_apis" {
  for_each = toset([
    "storage.googleapis.com",
    "bigquery.googleapis.com",
    "run.googleapis.com",
    "cloudscheduler.googleapis.com",
    "iam.googleapis.com",
  ])

  service            = each.value
  disable_on_destroy = false
}