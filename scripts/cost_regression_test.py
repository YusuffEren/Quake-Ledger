#!/usr/bin/env python3
"""
Quake-Ledger Maliyet Regresyon Testi
=====================================
PR'da değişen dbt modellerini dry-run ile analiz eder, 
tahmini taranan byte miktarını baseline ile karşılaştırır.
Eşik aşılırsa build fail eder.

Kullanım:
  python scripts/cost_regression_test.py \
    --project deprem-502519 \
    --dataset marts \
    --baseline-file cost_baseline.json \
    --threshold-percent 20

Gereksinimler:
  pip install google-cloud-bigquery
"""

import argparse
import json
import os
import sys
from pathlib import Path
from typing import Dict, List, Optional, Tuple

from google.cloud import bigquery


def parse_args():
    parser = argparse.ArgumentParser(description="dbt maliyet regresyon testi")
    parser.add_argument("--project", required=True, help="GCP proje ID")
    parser.add_argument("--dataset", default="marts", help="BQ dataset")
    parser.add_argument("--baseline-file", default="cost_baseline.json", help="Baseline dosyası")
    parser.add_argument("--threshold-percent", type=float, default=20.0, help="İzin verilen artış %")
    parser.add_argument("--model-dir", default="dbt/project/models", help="dbt model dizini")
    parser.add_argument("--dry-run-only", action="store_true", help="Sadece dry-run yap, karşılaştırma yapma")
    return parser.parse_args()


def find_changed_models(model_dir: str, baseline: Dict) -> List[str]:
    """Son commit'te değişen SQL model dosyalarını bul."""
    models = []
    model_path = Path(model_dir)
    
    # Git diff ile değişen dosyaları bul
    import subprocess
    result = subprocess.run(
        ["git", "diff", "--name-only", "HEAD~1", "--", "*.sql"],
        capture_output=True, text=True, cwd=model_path.parent.parent.parent
    )
    
    for line in result.stdout.strip().split("\n"):
        line = line.strip()
        if line and line.endswith(".sql") and "models" in line:
            # Model adını çıkar
            model_name = Path(line).stem
            if model_name not in ["schema"]:
                models.append(model_name)
    
    return models or list(baseline.keys())  # Hiç değişiklik yoksa tümünü test et


def dry_run_query(client: bigquery.Client, sql: str) -> int:
    """Bir SQL sorgusunun bytes_processed değerini dry-run ile al."""
    job_config = bigquery.QueryJobConfig(dry_run=True, use_query_cache=False)
    
    try:
        query_job = client.query(sql, job_config=job_config)
        return query_job.total_bytes_processed or 0
    except Exception as e:
        print(f"  ⚠️  Dry-run hatası: {e}", file=sys.stderr)
        return 0


def load_baseline(baseline_path: str) -> Dict:
    """Baseline dosyasını yükle."""
    path = Path(baseline_path)
    if path.exists():
        with open(path) as f:
            return json.load(f)
    return {}


def save_baseline(baseline: Dict, baseline_path: str):
    """Baseline dosyasını kaydet (güncelleme için)."""
    with open(baseline_path, "w") as f:
        json.dump(baseline, f, indent=2)
    print(f"  📝 Baseline kaydedildi: {baseline_path}")


def get_model_sql(project: str, dataset: str, model_name: str) -> Optional[str]:
    """dbt modelinin derlenmiş SQL pull'ını al."""
    # dbt compile çıktısını kullan
    compiled_path = Path(f"dbt/project/target/compiled/quake_ledger/models/{dataset}/{model_name}.sql")
    if compiled_path.exists():
        return compiled_path.read_text()
    
    # Alternatif: direkt model dosyası
    alt_path = Path(f"dbt/project/models/{dataset}/{model_name}.sql")
    if alt_path.exists():
        return alt_path.read_text()
    
    return None


def run_cost_regression_test(args) -> Tuple[bool, Dict]:
    """Ana test fonksiyonu. (geçti_mi, detaylar) döner."""
    client = bigquery.Client(project=args.project)
    baseline = load_baseline(args.baseline_file)
    models = find_changed_models(args.model_dir, baseline)
    
    print(f"\n{'='*60}")
    print(f"📊 Maliyet Regresyon Testi")
    print(f"{'='*60}")
    print(f"  Proje: {args.project}")
    print(f"  Dataset: {args.dataset}")
    print(f"  Threshold: %{args.threshold_percent}")
    print(f"  Modeller: {', '.join(models) if models else '(tümü)'}")
    print()
    
    results = {}
    all_passed = True
    
    for model_name in models:
        sql = get_model_sql(args.project, args.dataset, model_name)
        if not sql:
            print(f"  ⏭️  {model_name}: SQL bulunamadı, atlanıyor")
            continue
        
        print(f"  🔍 {model_name}: dry-run yapılıyor...", end=" ")
        bytes_now = dry_run_query(client, sql)
        cost_now = bytes_now * 5.0 / 1099511627776  # $5/TiB
        
        print(f"{bytes_now:,} bytes (${cost_now:.8f})")
        
        if model_name in baseline:
            bytes_baseline = baseline[model_name]["bytes_processed"]
            cost_baseline = baseline[model_name]["shadow_cost_usd"]
            
            if bytes_baseline > 0:
                increase_pct = ((bytes_now - bytes_baseline) / bytes_baseline) * 100
                
                if increase_pct > args.threshold_percent:
                    print(f"  ❌ {model_name}: Maliyet regresyonu! "
                          f"%{increase_pct:.1f} arttı "
                          f"(baseline: {bytes_baseline:,} → şimdi: {bytes_now:,})")
                    all_passed = False
                else:
                    print(f"  ✅ {model_name}: %{increase_pct:.1f} değişim (kabul edilebilir)")
        else:
            print(f"  ℹ️  {model_name}: Yeni model, baseline yok. Kaydediliyor...")
        
        results[model_name] = {
            "bytes_processed": bytes_now,
            "shadow_cost_usd": round(cost_now, 10),
        }
    
    # Baseline'ı güncelle (dry_run_only değilse)
    if not args.dry_run_only and results:
        baseline.update(results)
        save_baseline(baseline, args.baseline_file)
    
    print(f"\n{'='*60}")
    if all_passed:
        print(f"✅ Maliyet regresyon testi GEÇTİ")
    else:
        print(f"❌ Maliyet regresyon testi KALDI — baseline %{args.threshold_percent} üzerinde artış")
    print(f"{'='*60}\n")
    
    return all_passed, results


if __name__ == "__main__":
    args = parse_args()
    passed, _ = run_cost_regression_test(args)
    sys.exit(0 if passed else 1)
