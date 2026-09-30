@AGENTS.md

# Claude Code specifics

- The repository docs are the memory of this project. Do not rely on anything remembered from a previous
  conversation that is not written in `docs/`; if something important was decided in chat, record it in
  `docs/DECISIONS.md` or `docs/STATUS.md` before the session ends.
- **Model roles.** Use the strongest available Opus model for architecture, anything touching the `.vox`
  format or Teardown conventions, debugging of in-game failures, and reviews. A Sonnet model is fine for
  well-specified implementation tasks with clear tests. When in doubt, choose Opus.
- **Independent review.** Before declaring a milestone step done, run the `reviewer` subagent
  (`.claude/agents/reviewer.md`) on the changes. It exists because no human reviews the code.
- **Tooling.** Run project commands through `uv` (`uv run python scripts/check.py`, `uv run pytest`).
  The primary shell is PowerShell on Windows; the Bash tool (Git Bash) is also available.
- Commit/PR attribution lines follow the Claude Code system instructions for the session.
