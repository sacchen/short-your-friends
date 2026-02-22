# Developer guide

If you only read one file to work on this repo, read this one.

## What to read for what
- Getting started and commands: this file
- System design and boundaries: `ARCHITECTURE.md`
- Backend-specific details: `python-prototype/README.md`
- Contribution expectations: `CONTRIBUTING.md`
- Docker workflow: `docs/DOCKER.md`

## Quick start
Run from `python-prototype/`:

```bash
uv sync --all-groups
make
```

`make` prints available commands.

## How the Makefile works
The Makefile is a shortcut layer over longer shell commands.
Each target just runs one or more explicit commands.

Examples:
- `make run-server` runs `PYTHONPATH=src uv run --env-file .env server.py`
- `make test-unit` runs `uv run pytest -m "not integration"`
- `make ci-check` runs lint + type-check + unit tests

Use `make <target>` for routine tasks and use raw commands only when debugging.

## Daily workflow
From `python-prototype/`:

```bash
make test-unit
make type-check
make ci-check
```

When needed:

```bash
make run-server
make test-integration
```

## Test model
- Unit/invariant tests: no running server required
- Integration tests: require a running TCP server on `TEST_SERVER_HOST:TEST_SERVER_PORT`

## Current project status
- CI checks are configured in `.github/workflows/ci.yml`
- Persistence is JSON (`state.json`) for now
- Next infra priorities:
  - Docker Compose (`#6`)
  - PostgreSQL transactional persistence (`#4`)

## Containerized workflow (optional)
From repo root:

```bash
docker compose up --build
```

See `docs/DOCKER.md` for logs, teardown, integration-test commands, and volume reset.
