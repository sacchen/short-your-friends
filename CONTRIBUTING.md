# Contributing

Use `docs/DEVELOPER_GUIDE.md` as the primary operational reference.

## Setup
Run from `python-prototype/`:

```bash
uv sync --all-groups
make
```

## Local quality checks
Use the same checks required by CI:

```bash
uv run ruff check .
uv run mypy
uv run pytest -m "not integration"
```

For server-backed tests:

```bash
PYTHONPATH=src uv run server.py
# in another shell
TEST_SERVER_HOST=127.0.0.1 TEST_SERVER_PORT=8888 uv run pytest -m integration
```

## Workflow
1. Create a branch from `main`.
2. Make a focused change.
3. Add or update tests.
4. Update relevant docs (`README.md`, `python-prototype/README.md`, `ARCHITECTURE.md` if interfaces changed).
5. Run local quality checks.
6. Open a PR and wait for CI.

## Commit style
Follow the spirit of [The Perfect Commit](https://simonwillison.net/2022/Oct/29/the-perfect-commit/):
- One logical change per commit.
- Commit message explains what changed and why.
- Include validation in the commit body (tests/checks run).

Minimal format:
- Subject: `<type>: <what changed>`
- Body: `Why: ...`
- Body: `Validation: ...`

## Project layout
- `python-prototype/src/orderbook/`: core data structures and economy
- `python-prototype/src/engine/`: engine orchestration
- `python-prototype/server.py`: TCP server boundary
- `ios-client/`: SwiftUI client prototype
