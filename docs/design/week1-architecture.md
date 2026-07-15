# Quake-Ledger — Hafta 1 Mimarisi

## Amaç

USGS ve Kandilli'den canlı deprem verisini toplayıp GCP free tier uyumlu, gözlemlenebilir, idempotent bir ham veri katmanına taşımak.

## Bileşenler

### 1. Ingestion Servisi (`src/ingestion/`)

- **Framework:** FastAPI + uvicorn
- **Runtime:** Cloud Run
- **Endpoint'ler:**
  - `POST /ingest/usgs` — USGS API'den son depremleri çeker.
  - `POST /ingest/kandilli` — Kandilli RSS/JSON kaynağından son depremleri çeker.
- **İş Akışı:**
  1. Fetcher kaynak API'yi çağırır.
  2. Her kayıt için kaynak + ingestion zaman damgası eklenir.
  3. Ham JSON GCS'e `raw/{source}/{date}/{timestamp}.jsonl` olarak yazılır.
  4. Normalize edilmiş satırlar BigQuery `raw.{source}` tablosuna `MERGE` ile atılır (idempotent).

### 2. Depolama

- **GCS:** `quake-ledger-raw` bucket'ı; ham JSON satırları, ileride Nearline lifecycle ile saklanır.
- **BigQuery:**
  - `raw` dataset — kaynak sistemden gelen normalize satırlar.
  - `staging` dataset — temizlenmiş, tipe çevrilmiş veri (Hafta 2).
  - `marts` dataset — analitik ve raporlama tabloları (Hafta 2).

### 3. Altyapı (`terraform/`)

- `modules/gcs` — raw veri bucket'ı.
- `modules/bigquery` — dataset + tablolar.
- `modules/cloud_run` — ingestion servisi, service account, IAM.
- `modules/scheduler` — USGS ve Kandilli için Cloud Scheduler job'ları.

### 4. Zamanlama

- Cloud Scheduler her 15 dakikada bir `/ingest/usgs` ve `/ingest/kandilli` endpoint'lerini tetikler.
- Cloud Run `max_instances = 1` ile sıralı çalışır; aynı kaydın birden fazla işlenmesi `MERGE` ile giderilir.

### 5. CI/CD

- `.github/workflows/ci.yml` — ruff lint, pytest, `terraform fmt -check`, `terraform validate`, Docker build.
- `.github/workflows/terraform-plan.yml` — PR'da gerçek GCP ortamına karşı `terraform plan` çalıştırır; `GCP_SA_KEY` secret'ı gerekir.

## Güvenlik ve Maliyet Kontrolleri

- Service account minimum yetkiyle oluşturulur.
- BigQuery tablolarında `require_partition_filter = true`.
- GCS bucket `force_destroy = false`.
- Cloud Run non-root kullanıcı (`USER 1000`) ile çalışır.
- State GCS bucket'ında versioning açıktır.

## Veri Kontratı (Hafta 1)

- `raw.usgs` ve `raw.kandilli` tabloları en az şu alanları içerir:
  - `event_id` — kaynak sistemdeki benzersiz kimlik.
  - `latitude`, `longitude`, `magnitude`, `depth`.
  - `event_time` — depremin gerçekleştiği zaman (UTC).
  - `ingested_at` — pipeline'a alındığı zaman.
  - `raw_payload` — orijinal JSON satırı.
- Idempotency: `MERGE ... ON event_id` ile aynı kaydın tekrar işlenmesi veri çoğaltmaz.

## Sınırlılıklar

- Hafta 1'de dbt dönüşüm katmanı aktif değildir; veri `raw` katmanda kalır.
- Lifecycle rule ve maliyet regresyon testleri Hafta 3'e bırakılmıştır.
- Alerting / monitoring dashboard'u Hafta 2'de eklenecektir.
