.PHONY: help test-local test-unit test-integration test-prod deploy bench type-check run-server ci-check

help:
	@echo "Available commands:"
	@echo "  make test-local  - Run pytest locally"
	@echo "  make test-unit   - Run unit/invariant tests only"
	@echo "  make test-integration - Run server-backed integration tests"
	@echo "  make bench       - Run benchmarks with PyPy"
	@echo "  make type-check  - Run strict Mypy checks"
	@echo "  make run-server  - Start TCP server"
	@echo "  make ci-check    - Run local CI equivalent"

# Run everything locally
test-local:
	uv run --env-file .env pytest

test-unit:
	uv run pytest -m "not integration"

test-integration:
	TEST_SERVER_HOST=127.0.0.1 TEST_SERVER_PORT=8888 uv run pytest -m integration

# Run integration tests against the live Droplet
test-prod:
	TEST_SERVER_HOST=REDACTED_IP uv run pytest

# Run performance benchmarks using PyPy for maximum speed
bench:
	uv run --python pypy --no-dev benchmark.py

# Run strict type checking
type-check:
	uv run mypy

# Run the server with corrected PYTHONPATH
run-server:
	PYTHONPATH=src uv run --env-file .env server.py

# My existing deploy command
deploy:
	./deploy-exchange.sh

ci-check:
	uv run ruff check .
	uv run mypy
	uv run pytest -m "not integration"
