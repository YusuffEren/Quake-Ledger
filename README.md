# Quake-Ledger

Canlı deprem verisi üzerine **GCP free tier**'da çalışan, tam gözlemlenebilirlikli, CI'da veri kontratı ve maliyet regresyon testi olan bir **data engineering pipeline**'ı.

```
                      ┌─────────────────┐
   Cloud Scheduler ──▶│  Cloud Run       │──▶ USGS + Kandilli API
   (*/15 dk)          │  (ingestion)     │──▶ GCS (ham JSON)
                      └────────┬─────────┘
                               │ BigQuery (MERGE)
                               ▼
                      ┌──────────────────┐
                      │  BigQuery Raw     │  ← ham, immutable
                      └────────┬─────────┘
                               │
                      ┌────────▼─────────┐
                      │  dbt Staging      │  ← normalize views
                      └────────┬─────────┘
                               │
                      ┌────────▼─────────┐
                      │  dbt Reconcil.    │  ← Haversine eşleştirme
                      └────────┬─────────┘
                               │
                      ┌────────▼─────────┐
                      │  dbt Marts        │  ← analitik tablolar
                      └────────┬─────────┘
                               │
                      ┌────────▼─────────┐
                      │  Looker Studio    │  ← dashboard
                      │  + Cloud Logging  │  ← gözlemlenebilirlik
                      └──────────────────┘

   CI/CD: GitHub Actions · lint · test · dbt build · dbt test · cost regression
   IaC:   Terraform (GCS · BQ · Cloud Run · Scheduler · IAM)
```

---

## Hızlı Başlangıç

### 1. GCP Hazırlık

```bash
# Terraform state bucket (manuel, ilk sefer)
gcloud storage buckets create gs://<PROJECT_ID>-tfstate --location=EU

# Service account key indir → gcp-key.json olarak proje köküne koy
```

### 2. Altyapı

```bash
cd terraform
cp terraform.tfvars.example terraform.tfvars
# project_id, cloud_run_image değerlerini düzenle
terraform init
terraform apply
```

### 3. Docker Image

```bash
docker build -t quake-ingestion src/ingestion/
docker tag quake-ingestion europe-west1-docker.pkg.dev/<PROJECT_ID>/quake-ingestion/ingestion:latest
docker push europe-west1-docker.pkg.dev/<PROJECT_ID>/quake-ingestion/ingestion:latest
```

### 4. dbt

```bash
cd dbt/project
dbt deps
dbt build     # staging → reconciliation → marts
dbt test      # veri kontratları
```

---

## Proje Yapısı

```
quake-ledger/
│
├── terraform/                 # IaC — GCP kaynakları
│   ├── modules/gcs/           # Ham veri bucket
│   ├── modules/bigquery/      # raw/staging/marts dataset + tablolar
│   ├── modules/cloud_run/     # Ingestion servisi + SA
│   └── modules/scheduler/     # Cloud Scheduler job'ları
│
├── src/ingestion/             # Cloud Run ingestion servisi (FastAPI)
│   ├── fetchers/              # USGS + Kandilli API fetcher
│   ├── storage/               # GCS + BigQuery writer
│   └── main.py                # /health, /ingest/usgs, /ingest/kandilli
│
├── dbt/project/               # dbt dönüşüm katmanı
│   ├── models/
│   │   ├── staging/           # Normalize view'lar
│   │   ├── reconciliation/    # Haversine eşleştirme + unified events
│   │   └── marts/             # Analitik tablolar + cost metrikleri
│   └── tests/singular/        # Veri kontratları (freshness, range, cross-source)
│
├── scripts/                   # Yardımcı araçlar
│   └── cost_regression_test.py # Maliyet regresyon testi
│
├── tests/                     # Birim testleri (pytest, 14 test)
│
├── .github/workflows/         # CI/CD pipeline
│   ├── ci.yml                 # lint → test → dbt build → dbt test → cost regression
│   └── terraform-plan.yml     # PR'da terraform plan
│
└── docs/design/               # Mimari dokümanlar
```

---

## Pipeline Adımları

| Adım | Açıklama | Teknoloji |
|---|---|---|
| **Ingestion** | USGS + Kandilli'den 15dk'da bir veri çek | Cloud Run + Python |
| **Raw Storage** | Ham JSON → GCS (immutable) + BQ (MERGE idempotent) | GCS + BigQuery |
| **Staging** | Normalize views (ortak şema) | dbt (view) |
| **Reconciliation** | Haversine eşleştirme + unified events | dbt (table) |
| **Marts** | Analitik tablolar + cost metrikleri | dbt (table) |
| **Dashboard** | Gözlemlenebilirlik panelleri | Looker Studio |
| **CI/CD** | lint → test → dbt build → dbt test → cost regression | GitHub Actions |

---

## Veri Kontratları (CI'da Build Fail)

| Test | Açıklama | Eşik |
|---|---|---|
| **Freshness USGS** | En son deprem çok eski mi? | 120 dk |
| **Freshness Kandilli** | En son deprem çok eski mi? | 120 dk |
| **Magnitude Range** | Büyüklük -2 ile 10 arasında mı? | Her kayıt |
| **Min Events** | Son 6 saatte en az 2 saat diliminde event var mı? | 2 saat |
| **Cross-Source Disagreement** | USGS vs Kandilli büyüklük farkı > 2.0? | Uyarı |
| **Source Integrity** | Primary key unique + not null | Her kayıt |

---

## Maliyet Yönetimi (FinOps)

Pipeline'ın **gölge maliyeti** BigQuery INFORMATION_SCHEMA üzerinden takip edilir:

- `fct_model_cost` — Her modelin bytes_processed + shadow_cost
- `dm_daily_pipeline_cost` — Günlük toplam maliyet
- **Maliyet regresyon testi** — PR'da değişen model maliyeti %20+ artarsa build fail

**Güncel GCP Free Tier Kullanımı:**
- BigQuery: ~1 TiB/ay ücretsiz sorgu → pipeline çok altında
- Cloud Run: 2M istek/ay ücretsiz → ~5,760 istek/ay
- GCS: 5 GB/ay → <100 MB
- **Toplam: $0/ay**

---

---

## Known Limitations (Bilinçli Tradeoff'lar)

Bu proje portföy amaçlıdır ve aşağıdaki sınırlamaların farkında olarak tasarlanmıştır:

| Sınırlama | Açıklama | Gelecek İyileştirme |
|---|---|---|
| **Reconciliation CROSS JOIN** | Haversine eşleştirmesi tüm kaynak çiftlerini `CROSS JOIN` eder (O(n×m)). Küçük hacimde sorunsuz, büyürken patlar. | Time-bucket + geohash ön filtresi ile bloklama |
| **Kandilli rate-limit** | ETag ve 15sn bekleme in-process state'te tutulur. Cold start/çoklu instance'da best-effort. | Paylaşılan state (GCS/Firestore) veya Cloud Scheduler zaten 15dk ara ile tetikler |
| **Staging concurrency** | Aynı kaynağın iki ingestion'ı `_stg_` tablosuna çakışarak yazabilir. `maxInstances=1` + `concurrency=1` ile risk düşük. | _stg_ tablosunu ingestion_id ile uniqueness |
| **Kandilli proxy bağımlılığı** | Kandilli verisi `api.orhanaydogdu.com.tr` topluluk proxy'si üzerinden alınır. Kesinti durumunda veri kaybı olabilir. | KOERI HTML scraping ile fallback fetcher |
| **Tek region/instance** | Cloud Run europe-west1'de, BigQuery EU'da. Disaster recovery yok. | Multi-region, Terraform modülü ile genişletme |
| **Gözlemlenebilirlik** | Structured logging + BigQuery sorguları seviyesinde. Ayrı bir observability platformu yok. | OpenLineage + Elementary + Cloud Monitoring alert |

---

## Geliştirme Komutları

```bash
make lint                    # ruff + terraform fmt
make test                    # pytest (14 test)
make dbt-build               # dbt build (staging → reconciliation → marts)
make dbt-test                # dbt test (veri kontratları)
make cost-baseline           # Maliyet baseline ölçümü
make cost-regression         # Maliyet regresyon testi
make docker-build            # Ingestion image build
make terraform-plan          # Terraform plan
make terraform-apply         # Terraform apply
```

---

## GCP Secret'ları (CI)

| Secret | Açıklama |
|---|---|
| `GCP_SA_KEY` | Terraform plan için SA JSON key |
| `DBT_PROJECT_ID` | GCP proje ID |
| `DBT_KEYFILE` | dbt için SA JSON key (base64) |

---

## Lisans ve Atıf

- USGS verisi: [USGS Earthquake Hazards Program](https://earthquake.usgs.gov/) — public domain
- Kandilli verisi: [Boğaziçi Üniversitesi Kandilli Rasathanesi](http://www.koeri.boun.edu.tr/) — eğitim/portföy amaçlı kullanım
- Topluluk API'si: [orhanayd/kandilli-rasathanesi-api](https://github.com/orhanayd/kandilli-rasathanesi-api)
