.PHONY: test-local test-prod deploy

# Run everything locally
test-local:
	uv run pytest

# Run integration tests against the live Droplet
test-prod:
	TEST_SERVER_HOST=REDACTED_IP uv run pytest

# Your existing deploy command
deploy:
	./deploy-exchange.sh