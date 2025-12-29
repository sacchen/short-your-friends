.PHONY: help test-local test-prod deploy bench type-check run-server

help:
	@echo "Available commands:"
	@echo "  make test-local  - Run pytest locally"
	@echo "  make bench       - Run benchmarks with PyPy"
	@echo "  make type-check  - Run strict Mypy checks"
	@echo "  make run-server  - Start TCP server"

# Run everything locally
test-local:
	uv run pytest

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
	PYTHONPATH=src uv run server.py

# My existing deploy command
deploy:
	./deploy-exchange.sh