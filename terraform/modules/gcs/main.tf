# Ham veri bucket — uniform bucket-level access ile IAM yönetimi.
resource "google_storage_bucket" "quake_raw" {
  name          = "${var.project_id}-${var.bucket_name}"
  project       = var.project_id
  location      = var.location
  force_destroy = false # Ham veri koruması — yanlışla silinmeyi önler.

  uniform_bucket_level_access = true

  versioning {
    enabled = true
  }

  # Hafta 3'te aktif edilecek — 90 gün sonra Nearline'a taşı.
  # lifecycle_rule {
  #   condition {
  #     age = 90
  #   }
  #   action {
  #     type          = "SetStorageClass"
  #     storage_class = "NEARLINE"
  #   }
  # }
}