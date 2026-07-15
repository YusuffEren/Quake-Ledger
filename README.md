# Quake-Ledger

Canlı deprem verisi üzerine GCP free tier'da çalışan, tam gözlemlenebilirlikli, CI'da veri kontratı ve maliyet regresyon testi olan bir data engineering pipeline'ı.

## Hafta 1 — İskelet ve Ham Veri

### Kurulum

1. GCP projesi oluşturun.
2. Terraform state bucket'ını manuel oluşturun:
   ```bash
   gcloud storage buckets create gs://quake-ledger-tfstate \
     --project=<PROJECT_ID> --location=EU --uniform-bucket-level-access
   gcloud storage buckets update gs://quake-ledger-tfstate --versioning
   ```
3. Terraform tfvars dosyasını hazırlayın:
   ```bash
   cd terraform
   cp terraform.tfvars.example terraform.tfvars
   # terraform.tfvars içinde project_id, region, bucket_name, cloud_run_image değerlerini düzenleyin.
   ```
4. Terraform ile kaynakları oluşturun:
   ```bash
   cd terraform
   terraform init
   terraform plan
   terraform apply
   ```
5. Ingestion image'ını build edip Artifact Registry'e push'layın:
   ```bash
   docker build -t quake-ingestion src/ingestion/
   docker tag quake-ingestion europe-west1-docker.pkg.dev/<PROJECT_ID>/quake/ingestion:latest
   docker push europe-west1-docker.pkg.dev/<PROJECT_ID>/quake/ingestion:latest
   ```
6. GitHub Secrets'a GCP service account key ekleyin: `GCP_SA_KEY`

### Mimari

Detaylı tasarım için bkz. [docs/design/week1-architecture.md](docs/design/week1-architecture.md).

```
USGS / Kandilli API
        │
        ▼
  Cloud Scheduler (*/15 dk)
        │  POST /ingest/{usgs,kandilli}
        ▼
  Cloud Run (quake-ingestion)
        │
        ├─► GCS (raw bucket)  ── ham JSON
        └─► BigQuery (raw dataset) ── normalize edilmiş satırlar
                │
                ▼
          dbt (staging → marts)  [Hafta 2]
```

### Proje Yapısı

```
quake-ledger/
├── terraform/              # IaC — GCP kaynakları
│   ├── modules/gcs/        # Ham veri bucket
│   ├── modules/bigquery/   # raw / staging / marts dataset + tablolar
│   ├── modules/cloud_run/  # Ingestion servisi + service account
│   └── modules/scheduler/  # Cloud Scheduler job'ları
├── src/ingestion/          # Cloud Run ingestion servisi
├── dbt/                    # Dönüşüm katmanı (Hafta 2)
├── tests/                  # Birim testleri ve fixture'lar
├── .github/workflows/      # CI/CD workflow'ları
└── docs/                   # Mimari dokümanlar
```

### Geliştirme

```bash
make lint          # ruff + terraform fmt
make test          # pytest
make docker-build  # ingestion image
```

### GCP Secret'ları (CI)

- `GCP_SA_KEY` — Terraform plan için yetkili service account JSON key.

### Notlar

- Ham veri bucket `force_destroy = false` — yanlışla silinmeyi önler.
- BigQuery tablolarında `require_partition_filter = true` — maliyet kontrolü.
- Cloud Run `max_instances = 1` — tek instance, sıralı ingestion.
- Lifecycle rule (Nearline) Hafta 3'te aktif edilecek.
