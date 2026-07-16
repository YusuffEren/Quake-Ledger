"""Config birim testleri."""

import os
import sys

import pytest


def test_config_requires_project_id():
    """PROJECT_ID environment variable eksikken ValueError fırlatılmalı."""
    # Ortam değişkenlerini temizle
    env_backup = {}
    for key in ["PROJECT_ID", "RAW_BUCKET"]:
        env_backup[key] = os.environ.pop(key, None)

    # Modülü yeniden yükle — ValueError bekliyoruz
    if "src.ingestion.config" in sys.modules:
        del sys.modules["src.ingestion.config"]

    try:
        with pytest.raises(ValueError) as excinfo:
            import src.ingestion.config  # noqa: F401
        assert "PROJECT_ID" in str(excinfo.value)
    finally:
        # Temizlik: environ'u geri yükle
        for key, val in env_backup.items():
            if val is not None:
                os.environ[key] = val

        # Modülü yeniden yükle
        if "src.ingestion.config" in sys.modules:
            del sys.modules["src.ingestion.config"]
        # Test için ihtiyacımız olan değerleri set et
        os.environ["PROJECT_ID"] = "test-project"
        os.environ["RAW_BUCKET"] = "test-bucket"


def test_config_defaults():
    """Varsayılan değerler doğru olmalı."""
    os.environ.setdefault("PROJECT_ID", "test-project")
    os.environ.setdefault("RAW_BUCKET", "test-bucket")
    os.environ.setdefault("BQ_DATASET", "raw")

    if "src.ingestion.config" in sys.modules:
        del sys.modules["src.ingestion.config"]

    from src.ingestion import config

    assert config.BQ_DATASET == "raw"
