.DEFAULT_GOAL := help
.PHONY: help docker-up docker-down docker-reset docker-logs docker-ps

help:
	@echo "Available commands:"
	@echo "  make docker-up     - Build and start app + postgres"
	@echo "  make docker-down   - Stop containers"
	@echo "  make docker-reset  - Stop containers and delete volumes"
	@echo "  make docker-logs   - Follow app logs"
	@echo "  make docker-ps     - Show container status"

docker-up:
	docker compose up --build

docker-down:
	docker compose down

docker-reset:
	docker compose down -v

docker-logs:
	docker compose logs -f app

docker-ps:
	docker compose ps
