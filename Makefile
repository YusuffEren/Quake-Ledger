.PHONY: lint test docker-build terraform-plan terraform-apply terraform-init dbt-build dbt-test lint-sql cost-regression cost-baseline

lint:
	ruff check src/ tests/
	ruff format --check src/ tests/
	terraform fmt -check -recursive terraform/

lint-sql:
	sqlfluff lint dbt/project/models/ --dialect bigquery

test:
	python -m pytest tests/

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