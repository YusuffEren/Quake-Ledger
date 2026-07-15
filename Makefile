.PHONY: lint test docker-build terraform-plan terraform-apply terraform-init

lint:
	ruff check src/ tests/
	ruff format --check src/ tests/
	terraform fmt -check -recursive terraform/

test:
	python -m pytest tests/

docker-build:
	docker build -t quake-ingestion src/ingestion/

terraform-plan:
	cd terraform && terraform init && terraform plan

terraform-apply:
	cd terraform && terraform init && terraform apply

terraform-init:
	cd terraform && terraform init