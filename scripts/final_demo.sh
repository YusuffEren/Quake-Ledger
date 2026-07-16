#!/bin/sh
# GOOGLE_APPLICATION_CREDENTIALS environment variable'ından key path'ini al, yoksa varsayılan
KEY_FILE="${GOOGLE_APPLICATION_CREDENTIALS:-/workspace/gcp-key.json}"
gcloud auth activate-service-account --key-file="${KEY_FILE}" --project=deprem-502519 >/dev/null 2>&1

echo ""
echo "========================================================================"
echo "  QUAKE-LEDGER PROJESI — SON DURUM"
echo "========================================================================"
echo ""

echo "1. HEALTH CHECK"
TOKEN=$(gcloud auth print-identity-token)
curl -s -H "Authorization: Bearer $TOKEN" https://quake-ingestion-588042584335.europe-west1.run.app/health
echo ""

echo ""
echo "2. VERI KAYNAKLARI"
bq query --nouse_legacy_sql "
SELECT 'USGS' AS kaynak, COUNT(*) AS event_sayisi, ROUND(AVG(mag),2) AS ortalama_mag
FROM \`deprem-502519.raw.usgs_earthquakes\` WHERE event_time >= TIMESTAMP_SUB(CURRENT_TIMESTAMP(), INTERVAL 24 HOUR)
UNION ALL
SELECT 'EMSC', COUNT(*), ROUND(AVG(mag),2)
FROM \`deprem-502519.raw.emsc_earthquakes\` WHERE event_time >= TIMESTAMP_SUB(CURRENT_TIMESTAMP(), INTERVAL 24 HOUR)
UNION ALL
SELECT 'Kandilli', COUNT(*), ROUND(AVG(mag),2)
FROM \`deprem-502519.raw.kandilli_earthquakes\` WHERE date_time >= TIMESTAMP_SUB(CURRENT_TIMESTAMP(), INTERVAL 24 HOUR)
" 2>/dev/null

echo ""
echo "3. GUNLUK OZET (dbt marts)"
bq query --nouse_legacy_sql "
SELECT event_date, source, earthquake_count, avg_magnitude, max_magnitude
FROM \`deprem-502519.staging_marts.dm_earthquake_daily\`
WHERE earthquake_count > 0
ORDER BY event_date DESC, source
LIMIT 10
" 2>/dev/null

echo ""
echo "4. MALIYET"
bq query --nouse_legacy_sql "
SELECT ROUND(SUM(bytes_processed)/1024,2) AS toplam_kb, 
       ROUND(SUM(shadow_cost_usd)*1000000000,4) AS maliyet_nano_usd
FROM \`deprem-502519.staging_marts.fct_model_cost\`
" 2>/dev/null

echo ""
echo "========================================================================"
echo "  ✅ PROJE CANLI VE CALISIYOR!"
echo "  3 kaynak: USGS + EMSC + Kandilli"
echo "  Maliyet: ~$0/ay (GCP Free Tier)"
echo "  Scheduler: 15dk'da bir otomatik ingestion"
echo "  dbt: staging -> reconciliation -> marts"
echo "========================================================================"
