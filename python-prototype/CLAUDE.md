# Commands
- **Install**: `uv sync --all-groups`
- **Lint**: `uv run ruff check .`
- **Type Check**: `uv run mypy` (Strict mode is ON).
- **Test**: `uv run --env-file .env pytest`
- **Benchmark**: `uv run --python pypy --no-dev benchmark.py`
- **Run Server**: `uv run --env-file .env server.py`

# Architecture: The Factorio Mindset
- **Manage Complexity**: Build systems, not scripts. Inputs/Outputs must be clear.
- **Scalability**: Design for expansion. Avoid hard-coding.
- **Performance**: Watch for O(n) traps in the order book; aim for O(1) or O(log n).
- **Learning Logs (`logs/`)**:
    - Personal explanations and deep dives into concepts.
    - Used for "writing to learn" and solidifying understanding.
    - Format: `N-topic-name.md`.

# Education & Tutoring
- **Walk Me Through It**: Explain the *logic* and *architecture* choices, not just the syntax.
- **Teach**: If you see a better pattern (e.g., Rust-like safety, better algorithms), stop and teach it.
- **Drafting Logs**: When I conquer a complex topic, offer to help draft a `logs/` entry to cement the knowledge.

# Workflow: Explore → Plan → Code → Commit
You MUST follow this cycle. Do not jump straight to coding for complex tasks.

1.  **Explore (Read-Only)**:
    * Read relevant files.
    * Use `claude --permission-mode plan` or ask "Analyze X" first.
2.  **Plan (The "Think" Step)**:
    * Use keyword **"think"** to trigger extended reasoning.
    * Evaluate modularity (Factorio mindset).
3.  **Implementation**:
    * Write code for a single, focused change.
4.  **Tests**:
    * Add tests that pass (Tests-included development).
5.  **Documentation (The Perfect Commit)**:
    * **User-facing**: Update `README.md` (Features/Usage).
    * **Dev-facing**: Update `CONTRIBUTING.md` (Setup/Internals).
    * **Personal Learning**: Create/Update `logs/` if the task involved learning a new concept.
6.  **Commit**:
    * One-line summary + link to the issue (e.g., `Refactor engine to support async (refs #15)`).

## Review Guidelines
- **Safety**: Verify integer overflow risks and floating point precision.
- **Typing**: Strict compliance with `mypy` (Python 3.14 target).