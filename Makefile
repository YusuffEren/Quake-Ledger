.PHONY: lint test docker-build terraform-plan terraform-apply terraform-init dbt-build dbt-test lint-sql

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

docker-build:
	docker build -t quake-ingestion src/ingestion/

terraform-plan:
	cd terraform && terraform init && terraform plan

terraform-apply:
	cd terraform && terraform init && terraform apply

terraform-init:
	cd terraform && terraform init