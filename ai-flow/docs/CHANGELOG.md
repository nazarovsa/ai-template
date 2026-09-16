# Changelog

Chronological journal of completed tasks — each task run APPENDS an entry below.
Reusable patterns are NOT recorded here: they live in Serena memory (`.serena/memories/*`)
and are indexed in the CLAUDE.md "Project knowledge" table.

---

## 2026-08-22 — Project-level Codex MCP configuration

- Added `.codex/config.toml` to the installer manifest so initialized repositories support Codex
  alongside the existing Claude Code `.mcp.json` configuration.
- Updated `ai-flow/init.py` to configure both Serena (`--context codex`) and
  `codebase-memory-mcp` in the project-level Codex configuration.
- Updated `README.md` and `CLAUDE.md` with the dual-client MCP setup and session refresh guidance.

## [2026-09-16] - ai-flow: поддержка zcode доведена до рабочего состояния
- `agents.yml`: команда zcode-агента переписана по проверенным фактам о CLI 0.16.5 — у него нет
  `--model`, headless не читает stdin. Рабочая форма: `zcode --mode yolo --attach "{prompt_file}" --prompt ...`;
  модель и авторизация — в `~/.zcode/cli/config.json` (`provider` + `model.main`), в CI — env
  `ZCODE_MODEL` / `ZCODE_API_KEY` / `ZCODE_BASE_URL`.
- `run_tasks.py`: плейсхолдер `{prompt_file}` — промпт доставляется временным файлом, если команда
  агента его содержит; stdin-путь для claude/codex сохранён.
- `init.py`: для zcode генерируются self-contained скиллы `.agents/skills/*` (ZCode не видит
  субагентов из `.claude/agents/`, тонкие роутеры там ломались) и пишется `.zcode/config.json`
  (`mcp.servers` + `hooks.SessionStart` с `hooks.enabled: true` — ZCode не читает `.mcp.json` и
  `.claude/settings.json`). MANIFEST дополнен `task-runner`, `run-tasks`, `.zcode/config.json`;
  SUBAGENTS — `task-runner`.
- Проверено: py_compile; stub-прогон `{prompt_file}` (маркер найден); `init --tool zcode` в чистый
  каталог; `zcode skills list` видит все 4 скилла. Живой e2e zcode через `run_tasks.py` выполнен в
  рабочей репе-потребителе (acquirim).
