# Changelog

Chronological journal of completed tasks — each task run APPENDS an entry below.
Reusable patterns are NOT recorded here: they live in Serena memory (`.serena/memories/*`)
and are indexed in the CLAUDE.md "Project knowledge" table.

---

## [2026-09-17] — Один инструмент из коробки: Claude Code + промт адаптации PROMT_TOOL

- Удалены готовые адаптеры под другие инструменты: каталоги `.codex/` (config.toml, hooks.json,
  4 агента `.toml`), `.zcode/config.json` и сгенерированные zcode-скиллы `.agents/skills/*`.
- `ai-flow/init.py`: убраны `--tool`, подкоманды `adapt` и `list-tools`, генераторы адаптеров
  (`.codex/prompts`, `.cursor/rules`, `.gemini/prompts`, `.agents/skills`) и `merge_zcode_config`.
  Установщик настраивает только Claude Code; MANIFEST потерял `.codex/config.toml` и
  `.zcode/config.json`, получил `PROMT_TOOL.md`.
- `ai-flow/agents.yml`: остался единственный агент `claude`; вместо записей codex/zcode — комментарий
  с формой записи, которую добавляет `PROMT_TOOL`. Механика `{prompt_file}` в `run_tasks.py`
  сохранена (нужна CLI, не читающим stdin).
- Добавлен `ai-flow/docs/prompts/PROMT_TOOL.md` — промт, который запускают ИЗ-ПОД другого агентского
  CLI: он проверяет реальные возможности инструмента (`--help`/доки), перекладывает 4 роли, 4 точки
  входа, SessionStart-хук и MCP на его механизмы, добавляет запись исполнителя в `agents.yml` и
  требует проверок (список скиллов, срабатывание хука, `--dry-run`, smoke-тест команды). Инварианты:
  `CLAUDE.md` — единственный источник правил, `.claude/` не удаляется, `run_tasks.py` не правится,
  тонкий роутер запрещён там, где инструмент не видит субагентов.
- Документация: README (новый раздел «Другой инструмент, не Claude Code» вместо «Поддерживаемые
  инструменты», команды `init.py` без `--tool`, 7 промтов), `CLAUDE.md`, `AGENTS.md`, память
  `suggested-commands`, комментарии в CI-workflow и инвариант 11 в `PROMT_CI.md`.

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

## [2026-09-22] - ai-flow: гейт тестов по единице работы — при запуске фичи тесты гоняются раз на фичу
- Гейт «зелёные тесты» теперь проверяется в конце той единицы работы, которую запросили. Запуск фичи
  (`run_tasks.py` без `--task`, «реализуй фичу» в сессии): задачи пишут тесты по TDD и обязаны
  компилироваться, но тесты не запускают; после последней задачи идёт проход проверки фичи — сборка,
  весь набор тестов, фиксы до зелёного. `--task`: задача сама гоняет тесты; если она закрыла фичу, за
  ней тоже идёт проход проверки. Нарезка задач (PROMT_TASKS §0) не меняется.
- `run_tasks.py`: `test_gate` (`feature` по умолчанию | `task`), `verify_timeout`, `verify_prompt`,
  `git.verify_message_template`; строка `Test gate:` в промпте задачи; проход проверки строгий
  (без маркера — провал даже при exit 0); фича архивируется только после зелёного прохода, отдельным
  коммитом; фича со всеми задачами в `done/`, но не в архиве, считается непроверенной и проверяется
  первой при следующем запуске; строка `##  [<feature>] feature verification pass` в выводе.
- Новый `ai-flow/docs/prompts/PROMT_VERIFY.md` (промпт прохода проверки), добавлен в MANIFEST `init.py`.
- Документация: `CLAUDE.md` (always-apply правило, список промптов, автоматическое выполнение),
  `PROMT_AGENT.md` (Quality Gate в двух режимах), `PROMT_TASKS.md` (§0, критерий приёмки, DesignReview,
  контрольная задача), `PROMT_TOOL.md`, `tasks/README.md`, память `task-completion`, агенты
  `task-runner` / `task-author`, скилл `run-tasks`, `README.md`, `agents.yml`.
- Проверено: py_compile; фейковый агент в scratch-репо — полный прогон двух фич, провал проверки 3× →
  exit 1 и возобновление только проходом проверки, `--task` с проверкой после последней задачи,
  `--task` с упавшей проверкой → exit 1, `test_gate: task` без прохода проверки, dry-run на
  непроверенной фиче.

## [2026-09-22] - ai-flow: меньше токенов на задачу — сжатый промпт, доки раз на фичу, карта контекста
- Сжатый промпт (`run_tasks.py`): задача получает только последние `context.changelog_entries`
  записей журнала (по умолчанию 3) вместо всего файла; `CLAUDE.md` не вставляется в промпт агенту с
  `loads_claude_md: true` (у `claude` включено — проверено, что `claude --print` грузит его сам);
  убран шаг «просмотреть журнал» из `PROMT_AGENT.md`.
- Доки раз на фичу: при запуске фичи задача ведёт только `<feature>/NOTES.md` (построено, файлы, API
  для следующих задач, решения, паттерны/доменные правила, конфликты, доки к обновлению); заметки
  подаются в промпт каждой следующей задачи и прохода проверки. Журнал, спека, `IMPLEMENTED.md`,
  индекс спек, памяти и таблица `CLAUDE.md` пишутся один раз — проходом проверки (`PROMT_VERIFY.md`,
  часть 2, после зелёных тестов). При `--task` задача делает доки сама. `README.md`/`NOTES.md` в папке
  фичи — не задачи.
- Карта контекста: обязательный раздел `## Context` в задаче (`PROMT_TASKS.md` §6a) — разделы шаблонов
  (номер + заголовок), памяти, раздел спеки, 3–7 якорей в коде; исполнитель начинает с неё и заметок
  фичи и расширяет поиск только при необходимости.
- Ключ `test_gate` переименован в `unit_of_work` (старое имя понимается), строка промпта `Unit of work:`.
- CI: шаг «Look for pending tasks» считает и непроверенные фичи — иначе упавший проход проверки в CI
  не повторялся (пробел предыдущего изменения); то же в инварианте 7 `PROMT_CI.md`.
- Документация: `CLAUDE.md`, `PROMT_AGENT.md`, `PROMT_VERIFY.md`, `PROMT_TASKS.md`, `PROMT_TOOL.md`,
  `PROMT_CI.md`, `tasks/README.md`, `README.md`, память `task-completion`, агенты `task-author` /
  `task-runner`, скиллы `new-task` / `run-tasks`, `agents.yml`.
- Проверено: py_compile; фейковый агент в scratch-репо — `NOTES.md` не считается задачей, уезжает в
  архив с фичей и доходит до следующих задач и прохода проверки; в промпт попадают записи журнала 3–5
  из 5, при `changelog_entries: 0` блока нет; `CLAUDE.md` не встраивается при `loads_claude_md: true` и
  встраивается без него; `test_gate: task` работает как алиас; подсчёт CI видит непроверенную фичу;
  повтор сценариев прошлого изменения (провал проверки 3× → возобновление, `--task`, закрывающий фичу).
