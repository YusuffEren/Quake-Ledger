# BigQuery datasets — raw / staging / marts katmanları.
# EU multi-region: maliyet ve performans dengesi.

resource "google_bigquery_dataset" "raw" {
  dataset_id = "raw"
  project    = var.project_id
  location   = var.dataset_location

  delete_contents_on_destroy = false
}

resource "google_bigquery_dataset" "staging" {
  dataset_id = "staging"
  project    = var.project_id
  location   = var.dataset_location

  delete_contents_on_destroy = false
}

resource "google_bigquery_dataset" "marts" {
  dataset_id = "marts"
  project    = var.project_id
  location   = var.dataset_location

  delete_contents_on_destroy = false
}

# --- USGS raw tablosu ---
resource "google_bigquery_table" "raw_usgs" {
  dataset_id = google_bigquery_dataset.raw.dataset_id
  project   = var.project_id
  table_id  = "usgs_earthquakes"

  time_partitioning {
    type                     = "DAY"
    field                    = "event_time"
    require_partition_filter = true # Maliyet kontrolü — partition filter zorunlu.
  }

  clustering {
    fields = ["mag", "place"]
  }

  # Inline schema — ayrı JSON dosyası yerine burada, okunabilirlik için.
  schema = <<EOF
[
    {"name": "ingestion_id", "type": "STRING", "mode": "REQUIRED"},
    {"name": "ingestion_time", "type": "TIMESTAMP", "mode": "REQUIRED"},
    {"name": "event_id", "type": "STRING", "mode": "REQUIRED"},
    {"name": "event_time", "type": "TIMESTAMP", "mode": "REQUIRED"},
    {"name": "updated", "type": "TIMESTAMP", "mode": "NULLABLE"},
    {"name": "mag", "type": "FLOAT64", "mode": "NULLABLE"},
    {"name": "mag_type", "type": "STRING", "mode": "NULLABLE"},
    {"name": "place", "type": "STRING", "mode": "NULLABLE"},
    {"name": "status", "type": "STRING", "mode": "NULLABLE"},
    {"name": "tsunami", "type": "INTEGER", "mode": "NULLABLE"},
    {"name": "sig", "type": "INTEGER", "mode": "NULLABLE"},
    {"name": "net", "type": "STRING", "mode": "NULLABLE"},
    {"name": "nst", "type": "INTEGER", "mode": "NULLABLE"},
    {"name": "dmin", "type": "FLOAT64", "mode": "NULLABLE"},
    {"name": "rms", "type": "FLOAT64", "mode": "NULLABLE"},
    {"name": "gap", "type": "FLOAT64", "mode": "NULLABLE"},
    {"name": "type", "type": "STRING", "mode": "NULLABLE"},
    {"name": "alert", "type": "STRING", "mode": "NULLABLE"},
    {"name": "cdi", "type": "FLOAT64", "mode": "NULLABLE"},
    {"name": "mmi", "type": "FLOAT64", "mode": "NULLABLE"},
    {"name": "felt", "type": "INTEGER", "mode": "NULLABLE"},
    {"name": "lon", "type": "FLOAT64", "mode": "REQUIRED"},
    {"name": "lat", "type": "FLOAT64", "mode": "REQUIRED"},
    {"name": "depth_km", "type": "FLOAT64", "mode": "REQUIRED"},
    {"name": "source_url", "type": "STRING", "mode": "NULLABLE"},
    {"name": "raw_json", "type": "JSON", "mode": "NULLABLE"}
  ]
EOF
}

# --- Kandilli raw tablosu ---
resource "google_bigquery_table" "raw_kandilli" {
  dataset_id = google_bigquery_dataset.raw.dataset_id
  project    = var.project_id
  table_id   = "kandilli_earthquakes"

  time_partitioning {
    type                     = "DAY"
    field                    = "date_time"
    require_partition_filter = true
  }

  clustering {
    fields = ["mag"]
  }

  schema = <<EOF
[
    {"name": "ingestion_id", "type": "STRING", "mode": "REQUIRED"},
    {"name": "ingestion_time", "type": "TIMESTAMP", "mode": "REQUIRED"},
    {"name": "earthquake_id", "type": "STRING", "mode": "REQUIRED"},
    {"name": "date_time", "type": "TIMESTAMP", "mode": "REQUIRED"},
    {"name": "created_at", "type": "TIMESTAMP", "mode": "NULLABLE"},
    {"name": "mag", "type": "FLOAT64", "mode": "NULLABLE"},
    {"name": "depth_km", "type": "FLOAT64", "mode": "NULLABLE"},
    {"name": "lon", "type": "FLOAT64", "mode": "REQUIRED"},
    {"name": "lat", "type": "FLOAT64", "mode": "REQUIRED"},
    {"name": "title", "type": "STRING", "mode": "NULLABLE"},
    {"name": "location_tz", "type": "STRING", "mode": "NULLABLE"},
    {"name": "provider", "type": "STRING", "mode": "REQUIRED"},
    {"name": "epi_center_name", "type": "STRING", "mode": "NULLABLE"},
    {"name": "epi_center_population", "type": "INTEGER", "mode": "NULLABLE"},
    {"name": "closest_city_name", "type": "STRING", "mode": "NULLABLE"},
    {"name": "closest_city_distance_km", "type": "FLOAT64", "mode": "NULLABLE"},
    {"name": "location_properties", "type": "JSON", "mode": "NULLABLE"},
    {"name": "raw_json", "type": "JSON", "mode": "NULLABLE"}
  ]
EOF
}

# --- Staging tabloları — dbt materialize edecek, ama şema tutarlılığı için şimdiden tanımlı ---
# DİKKAT: Staging tabloları staging dataset'inde olmalı (raw'da değil).
resource "google_bigquery_table" "_stg_usgs" {
  dataset_id = google_bigquery_dataset.staging.dataset_id
  project    = var.project_id
  table_id   = "_stg_usgs"

  time_partitioning {
    type                     = "DAY"
    field                    = "event_time"
    require_partition_filter = true
  }

  clustering {
    fields = ["mag", "place"]
  }

  schema = google_bigquery_table.raw_usgs.schema
}

resource "google_bigquery_table" "_stg_kandilli" {
  dataset_id = google_bigquery_dataset.staging.dataset_id
  project    = var.project_id
  table_id   = "_stg_kandilli"

  time_partitioning {
    type                     = "DAY"
    field                    = "date_time"
    require_partition_filter = true
  }

  clustering {
    fields = ["mag"]
  }

  schema = google_bigquery_table.raw_kandilli.schema
}