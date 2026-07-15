#!/bin/sh
gcloud auth activate-service-account --key-file=/workspace/gcp-key.json --project=deprem-502519 >/dev/null 2>&1
TOKEN=$(gcloud auth print-identity-token)
curl -s -X POST -H "Authorization: Bearer $TOKEN" https://quake-ingestion-588042584335.europe-west1.run.app/ingest/emsc
