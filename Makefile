.PHONY: lint test docker-build terraform-plan terraform-apply terraform-init dbt-build dbt-test lint-sql cost-regression cost-baseline zip pre-commit-install pre-commit-run coverage

lint:
	ruff check src/ tests/
	ruff format --check src/ tests/
	terraform fmt -check -recursive terraform/

lint-sql:
	sqlfluff lint dbt/project/models/ --dialect bigquery

test:
	python -m pytest --cov=src/ingestion --cov-report=term-missing tests/ -q

# coverage — coverage raporunu HTML olarak da üretir (htmlcov/).
# HTML raporu ignore edilmiştir (aşağıda .gitignore'a güveniyoruz).
coverage:
	python -m pytest --cov=src/ingestion --cov-report=term-missing --cov-report=html tests/ -q

# pre-commit — takım içi ilk çalıştırmada hook'ları yükler, sonrasında
# elle tetiklemek için kullanılır. CI'da pre-commit-hooks action'ı ayrı
# çalışır; bu hedef geliştirici makineleri içindir.
pre-commit-install:
	pip install pre-commit
	pre-commit install

pre-commit-run:
	pre-commit run --all-files

dbt-deps:
	cd dbt/project && dbt deps

dbt-build: dbt-deps
	cd dbt/project && dbt build

dbt-test: dbt-build
	cd dbt/project && dbt test

cost-baseline:
	python scripts/cost_regression_test.py \
		--project deprem-502519 \
		--dataset staging \
		--dry-run-only

cost-regression:
	python scripts/cost_regression_test.py \
		--project deprem-502519 \
		--dataset staging \
		--threshold-percent 20

docker-build:
	docker build -t quake-ingestion src/ingestion/

terraform-plan:
	cd terraform && terraform init && terraform plan

terraform-apply:
	cd terraform && terraform init && terraform apply

terraform-init:
	cd terraform && terraform init

# Guvenli dagitim arsivi: sadece git tarafindan takip edilen (commit'li)
# dosyalari paketler. Untracked/ignored dosyalar (gcp-key.json, .gcloud/,
# .pytest_cache/, dbt target/logs artifact'lari) asla dahil edilmez cunku
# git archive sadece HEAD agacindan okur. dbt build artifact'lari (target/,
# logs/) artik git tarafindan takip edilmedigi icin ek pathspec exception'a
# gerek yok (bkz. P0-3 guvenlik temizligi raporu).
zip:
	git archive --format=zip -o quake-ledger.zip HEAD -- .
	@echo "quake-ledger.zip olusturuldu (sadece commit'li dosyalar)"