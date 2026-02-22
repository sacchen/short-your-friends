# AGENTS.md

Canonical instructions for coding agents working in this repository.

## Scope
- This file is the single source of truth for agent behavior in this repo.
- Any `CLAUDE.md` files are compatibility pointers only.

## Start here
- Operational commands: `docs/DEVELOPER_GUIDE.md`
- System design: `ARCHITECTURE.md`
- Backend details: `python-prototype/README.md`
- Contribution standards: `CONTRIBUTING.md`

## Default workflow
Use this sequence for non-trivial tasks:
1. Explore relevant code and docs.
2. Plan a focused change.
3. Implement a single logical unit.
4. Run checks/tests.
5. Update docs when behavior or workflows changed.
6. Commit with clear rationale and validation.

## Commands
Run from `python-prototype/`:

```bash
uv sync --all-groups
make
make ci-check
make test-integration
make run-server
```

## Quality gates
- Lint: `uv run ruff check .`
- Types: `uv run mypy`
- Unit/invariant tests: `uv run pytest -m "not integration"`
- Integration tests: `uv run pytest -m integration` (requires live server)

CI enforces these via `.github/workflows/ci.yml`.

## Engineering rules
- Use integer cents for prices in engine/server paths.
- Keep matching/accounting invariants intact.
- Follow [The Perfect Commit](https://simonwillison.net/2022/Oct/29/the-perfect-commit/) style:
  - one logical change per commit
  - explain what/why
  - include validation run

## Documentation rules
- External audience: `README.md` (clear system snapshot and status)
- Contributor operations: `docs/DEVELOPER_GUIDE.md`
- Architecture: `ARCHITECTURE.md`
- If you change workflows, update docs in the same PR.

## Notes
- Learning logs in `python-prototype/logs/` are educational references and may include exploratory content.
