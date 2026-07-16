"""Pytest yapılandırması — import path'leri ve ortam değişkenleri."""

import os
import sys
from pathlib import Path

# Proje kökünü ve src/ingestion/ dizinini PYTHONPATH'e ekle
PROJECT_ROOT = Path(__file__).resolve().parent.parent
SRC_INGESTION = PROJECT_ROOT / "src" / "ingestion"

for p in [str(PROJECT_ROOT), str(SRC_INGESTION)]:
    if p not in sys.path:
        sys.path.insert(0, p)

# Testler için gerekli environment variable'lar
os.environ.setdefault("PROJECT_ID", "test-project")
os.environ.setdefault("RAW_BUCKET", "test-raw-bucket")
os.environ.setdefault("BQ_DATASET", "raw")

# Google Cloud kütüphaneleri yoksa mock'la — testler gerçek GCP çağrısı yapmamalı
try:
    from google.cloud import bigquery  # noqa: F401
except ImportError:
    import sys
    from unittest.mock import MagicMock

    class MockBigQuery:
        Client = MagicMock
        LoadJobConfig = MagicMock
        SchemaField = MagicMock
        SourceFormat = MagicMock
        WriteDisposition = MagicMock
        QueryJobConfig = MagicMock

    sys.modules["google.cloud.bigquery"] = MockBigQuery()
    sys.modules["google.cloud"] = MagicMock()
    sys.modules["google"] = MagicMock()
