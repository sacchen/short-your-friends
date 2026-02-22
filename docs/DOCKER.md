# Docker guide

This stack gives you two containers:
- `app`: the Python exchange backend
- `postgres`: a PostgreSQL instance for upcoming persistence work

Use this when you want a reproducible local environment without installing Postgres directly on your machine.

## 1) Start the stack

From repo root:

```bash
make docker-up
```

What happens:
- Docker builds the app image from `python-prototype/Dockerfile`
- Postgres starts first and reports healthy via `pg_isready`
- App starts after Postgres is healthy

## 2) Check status

```bash
make docker-ps
make docker-logs
docker compose logs -f postgres
```

## 3) Run integration tests against containerized app

In a separate terminal (repo root):

```bash
cd python-prototype
TEST_SERVER_HOST=127.0.0.1 TEST_SERVER_PORT=8888 uv run pytest -m integration
```

## 4) Stop services

```bash
make docker-down
```

## 5) Reset persisted data (destructive)

```bash
make docker-reset
```

This removes:
- `app_state` volume (JSON state file path `/data/state.json`)
- `pg_data` volume (Postgres database files)

## How this maps to code

- `STATE_FILE=/data/state.json` is read by `server.py`.
- `DATABASE_URL` is provided now so the app environment is ready for issue `#4` (Postgres migration).
- Current backend persistence still uses JSON; Postgres is running in parallel for next steps.
