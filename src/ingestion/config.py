import os

# Cloud project ve storage hedefleri — deployment'ta mutlaka set edilmeli.
# Direkt os.environ[] KeyError fırlatır; açık mesaj config hatasını hızlıca
# teşhis ettirir.
PROJECT_ID = os.environ.get("PROJECT_ID")
if not PROJECT_ID:
    raise ValueError("PROJECT_ID environment variable is required")

RAW_BUCKET = os.environ.get("RAW_BUCKET")
if not RAW_BUCKET:
    raise ValueError("RAW_BUCKET environment variable is required")

BQ_DATASET = os.environ.get("BQ_DATASET", "raw")

# Kaynak API URL'leri — sabit, değişmesi beklenmez.
USGS_URL = "https://earthquake.usgs.gov/earthquakes/feed/v1.0/summary/all_hour.geojson"
KANDILLI_URL = "https://api.orhanaydogdu.com.tr/deprem/kandilli/live"

# Cloud Scheduler'ın bu servisi çağırma sıklığı (dakika).
INGESTION_INTERVAL_MINUTES = int(os.environ.get("INGESTION_INTERVAL_MINUTES", "15"))