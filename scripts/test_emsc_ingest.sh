#!/bin/sh
# GOOGLE_APPLICATION_CREDENTIALS environment variable'ından key path'ini al, yoksa varsayılan
KEY_FILE="${GOOGLE_APPLICATION_CREDENTIALS:-/workspace/gcp-key.json}"
gcloud auth activate-service-account --key-file="${KEY_FILE}" --project=deprem-502519 >/dev/null 2>&1
TOKEN=$(gcloud auth print-identity-token)
curl -s -X POST -H "Authorization: Bearer $TOKEN" https://quake-ingestion-588042584335.europe-west1.run.app/ingest/emsc
