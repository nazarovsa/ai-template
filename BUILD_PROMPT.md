# BUILD PROMPT — Базовый AI-репозиторий (bootstrap)

> Это одноразовый промт для Claude Code. Скорми его в пустом репозитории
> `D:/Work/open-source/ai-template`, чтобы собрать базовый шаблон для новых
> проектов: планирование → постановка задач → автоматическое выполнение.
> После успешной сборки этот файл можно удалить.

---

## Роль и цель

Ты — senior-инженер, собирающий **базовый (template) репозиторий** для новых проектов.
Репозиторий сам по себе НЕ содержит прикладного кода — он даёт **рабочий процесс**:

1. **Планирование** — из требований пишется спецификация, затем декомпозируется в задачи.
2. **Постановка задач** — каждая задача оформляется отдельным файлом в `docs/tasks/`.
3. **Автоматическое выполнение** — `run_tasks.py` прогоняет задачи через выбранного
   AI-агента (Claude Code / Codex / zcode) по DAG зависимостей.
4. **Самоподдержка знаний** — по мере появления общих паттернов агент обновляет
   память Serena и держит `docs/` в актуальном состоянии.

## Языковая политика (важно)

- **English — обязательно** для всех машинных/агентных артефактов: `CLAUDE.md`, `docs/prompts/*`
  (включая `PROMT_SERENA.md`), `.claude/agents/*`, `.claude/skills/*`, записи памяти `.serena/memories/*`.
- **Язык коммуникации** (на каком языке агент общается с пользователем) выбирается пользователем
  при инициализации через `init.py --comm-lang <ru|en|…>` и записывается директивой в `CLAUDE.md`.
  По умолчанию — English.
- `README.md` — руководство для человека: пиши на русском (рабочий язык пользователя).
- Этот BUILD_PROMPT и твои пояснения в чате — на русском; содержимое создаваемых артефактов — по правилам выше.

---

## Источники для адаптации (прочитай перед сборкой)

Эти файлы существуют на машине — прочитай их и адаптируй, НЕ пиши с нуля там, где сказано «адаптируй»:

- `D:/Work/VideoDownloaderBot/run_tasks.py` — базовый оркестратор (адаптировать).
- `D:/Work/VideoDownloaderBot/PROMT_AGENT.md` — промт агента на задачу (адаптировать).
- `D:/Work/VideoDownloaderBot/docs/tasks/PROMT_TASKS.md` — промт декомпозиции (адаптировать).
- `D:/Work/VideoDownloaderBot/.serena/project.yml` — эталон конфигурации Serena.
- `D:/Work/VideoDownloaderBot/.serena/memories/*` — эталон структуры памяти.
- `D:/Work/mentorship/mentorship-bot/CLAUDE.md` — эталон «минимального» CLAUDE.md с ссылками на паттерны в памяти Serena.
- `D:/Work/mentorship/mentorship-bot/docs/tasks/README.md` и `.../done/TASK_01_DOMAIN.md` — эталон оформления и шаблона задачи (RU).

---

## Layout convention (важно — читать первым)

Вся операционная инфраструктура флоу вынесена в один каталог **`ai-flow/`**, чтобы не засорять
корень проекта. В корне остаются ТОЛЬКО:
- `CLAUDE.md` и `AGENTS.md` — инструменты автоподхватывают их из корня проекта (перенос сломает обнаружение);
- `.claude/` (субагенты/скиллы) и `.serena/` (память) — **вынужденное исключение**: Claude Code и Serena
  ищут эти каталоги строго в корне проекта, перенести их нельзя. Это требование инструментов, не наше.

Все пути `ai-flow/docs/...` и `ai-flow/<script>` в этом документе означают именно этот layout.
`run_tasks.py`/`init.py` вычисляют **REPO_ROOT = родитель каталога `ai-flow/`** и все относительные
пути из `agents.yml` резолвят от REPO_ROOT; агент запускается с cwd = REPO_ROOT (видит весь проект).

## Итоговая структура репозитория

```
ai-template/
├── AGENTS.md                     # КОРЕНЬ: универсальный редирект не-Claude инструментов на CLAUDE.md
├── CLAUDE.md                     # КОРЕНЬ: минимальные правила + таблица read_memory(...) (English)
├── .gitignore                    # КОРЕНЬ
├── .claude/                      # КОРЕНЬ (обязательно — обнаружение Claude Code)
│   ├── agents/
│   │   ├── task-author.md        # СУБАГЕНТ 1: формирование новой задачи → ai-flow/docs/tasks/task-NN.md
│   │   └── doc-keeper.md         # СУБАГЕНТ 2: создание/актуализация документации + память Serena
│   └── skills/
│       ├── new-task/SKILL.md     # СКИЛЛ: запускает task-author (постановка задачи)
│       └── sync-docs/SKILL.md    # СКИЛЛ: запускает doc-keeper (синхронизация документации)
├── .serena/                      # КОРЕНЬ (обязательно — обнаружение Serena)
│   ├── project.yml               # конфиг Serena (язык проекта задаётся init.py)
│   └── memories/                 # English; project-specific память создаёт PROMT_SERENA
│       ├── suggested-commands.md # команды репозитория (run_tasks.py, init.py) — ship с шаблоном
│       └── task-completion.md    # определение «задача выполнена» — ship с шаблоном
│                                 # (architecture-overview, testing-patterns, db-access-rules,
│                                 #  api-conventions, error-handling, auth-conventions,
│                                 #  build-and-verify — генерируются PROMT_SERENA под проект)
└── ai-flow/                      # ← ВСЯ инфраструктура флоу тут
    ├── run_tasks.py              # оркестратор авто-выполнения задач (мультиагентный, через agents.yml)
    ├── init.py                   # CLI: инициализация/адаптация шаблона в новый или существующий репозиторий
    ├── agents.yml                # конфиг: claude / codex / zcode + маркеры, таймауты, git, контекст
    ├── README.md                 # как пользоваться флоу + гайд по настройке Serena под свой инструмент
    └── docs/
        ├── prompts/              # ВСЕ промты — на English
        │   ├── PROMT_SPEC.md      # промт: написать спецификацию по требованиям
        │   ├── PROMT_TASKS.md     # промт: декомпозировать спецификацию в задачи ai-flow/docs/tasks/
        │   ├── PROMT_AGENT.md     # промт: инструкции агенту на выполнение ОДНОЙ задачи
        │   └── PROMT_SERENA.md    # промт: bootstrap памяти Serena по коду + wiring в CLAUDE.md
        ├── specs/
        │   └── README.md          # что кладём в specs (спецификации-контекст, read-only)
        └── tasks/
            ├── README.md          # формат задач, нейминг, жизненный цикл, шаблон задачи
            ├── INDEX.md           # обзор фаз + DAG + таблица прогресса (заготовка)
            └── progress.md        # журнал прогресса + секция «Codebase Patterns» (создаётся автоматически)
```

> `BUILD_PROMPT.md` — временный bootstrap-файл в корне; после сборки удаляется.

---

## Пофайловые требования

### 1. `ai-flow/run_tasks.py` — оркестратор (адаптировать из VideoDownloaderBot)

Возьми `D:/Work/VideoDownloaderBot/run_tasks.py` за основу и внеси изменения:

**1.0. Расположение и корень проекта (новый layout).**
- Скрипт лежит в `ai-flow/`. Вычисляй `REPO_ROOT = Path(__file__).resolve().parent.parent`
  (родитель `ai-flow/`), а `FLOW_DIR = Path(__file__).resolve().parent`.
- Конфиг по умолчанию — `FLOW_DIR / "agents.yml"`.
- Все относительные пути из `agents.yml → context` резолвь **от REPO_ROOT** (не от FLOW_DIR).
- Агента запускай с `cwd = REPO_ROOT`, чтобы он видел и правил весь проект, а не только `ai-flow/`.

**1.1. Мультиагентность через `agents.yml`.**
- Убери хардкод команды `claude …`. Читай конфиг `agents.yml` (см. §2).
- Выбор агента: `--agent {claude|codex|zcode}` (по умолчанию `default_agent` из конфига).
- Команда агента берётся из `agents.<name>.command`, в ней подставляется `{model}`
  (модель из `--model` или `agents.<name>.model`). Промт всегда передаётся через **stdin**
  (пиши промт во временный файл и запускай `command < prompt_file`, как в оригинале).
- `agents.<name>.env` (если задан) — добавляй в окружение процесса (для zcode/Z.ai:
  `ANTHROPIC_BASE_URL`, `ANTHROPIC_AUTH_TOKEN` и т.п.).
- Маркер завершения — `completion_marker` из конфига (по умолчанию `<promise>COMPLETE</promise>`).
- Таймаут — `task_timeout` из конфига.

**1.2. Пометка выполненной задачи как `(done)` (не `(Completed)`).**
- При успехе переименовывай `task-NN.md` → `task-NN (done).md`.
- Детект завершённых — по подстроке `(done)` в имени файла (регистронезависимо).
- Обнови все хелперы (`_task_filename`, `_id_from_file`, `_is_completed`, `completed_ids`)
  на суффикс `(done)`.

**1.3. Источник знаний — память Serena (сырые файлы), а не `docs/patterns/`.**
- Контекст-пути бери из `agents.yml → context` (резолвь от REPO_ROOT):
  - `tasks_dir` (по умолчанию `ai-flow/docs/tasks`) — каталог с `task-NN.md`; замени хардкод `TASKS_DIR`.
  - `specs_dir` (по умолчанию `ai-flow/docs/specs`) — в промт подставляй только **список файлов** (указатели).
  - `memories_dir` (по умолчанию `.serena/memories`) — по умолчанию в промт подставляй
    **указатели** (имя записи + первую строку-заголовок каждого `*.md`), НЕ полный текст,
    чтобы не раздувать контекст. Если `context.inline_memories: true` — вставляй полный текст.
    Записи памяти — обычные `.md`, читаются напрямую с диска (MCP Serena не обязателен исполнителю).
  - `progress_file` (по умолчанию `docs/tasks/progress.md`).
  - `agent_prompt` (по умолчанию `docs/prompts/PROMT_AGENT.md`).
- В промт также добавляй содержимое корневого `CLAUDE.md` (как основной свод правил).

**1.4. Git-коммиты — опциональны и безопасны.**
- Блок `git` в конфиге: `enabled`, `auto_commit`, `message_template` (плейсхолдеры `{id}`, `{title}`).
- **Сообщение коммита: одна строка, обрезай до ≤155 символов**; никаких упоминаний Claude/AI/инструментов
  (без `Co-Authored-By`, без «Generated with …»). Это правило из `CLAUDE.md` — соблюдай его в оркестраторе.
- Если `git.enabled: false` ИЛИ каталог не является git-репозиторием (`git rev-parse` падает) —
  коммиты пропускаются с сообщением, выполнение продолжается (репозиторий-шаблон может быть без git).

**1.5. Новые флаги CLI.**
- `--agent NAME` — выбрать агента (перекрывает `default_agent`).
- `--model NAME` — перекрыть модель агента.
- `--config PATH` — путь к конфигу (по умолчанию `agents.yml` рядом со скриптом).
- `--task ID` — выполнить только одну задачу по id (если зависимости не выполнены — предупредить и выйти).
- `--dry-run` — показать план (готовые задачи, команду агента) без запуска.
- Сохрани существующую логику: DAG-готовность по `Depends on:` / `Зависит от:`, стоп после 3 подряд провалов,
  UTF-8 reconfigure, потоковый вывод stdout, корректный `SIGINT`.

**1.6. Зависимость.** Скрипт использует `pyyaml`. Если модуль не установлен — понятная ошибка
с подсказкой `pip install pyyaml`. Ничего другого сверх стандартной библиотеки не тяни.

**1.7. Докстринг** вверху файла обнови: опиши мультиагентный режим, `(done)`-нейминг,
источник паттернов из памяти Serena и примеры запуска.

---

### 2. `agents.yml` — конфиг оркестратора (полное содержимое)

Создай файл ровно с такой структурой (значения — разумные дефолты; флаги codex/zcode
помечены как проверяемые):

```yaml
# Конфигурация оркестратора run_tasks.py

default_agent: claude          # какой агент использовать по умолчанию
task_timeout: 1200             # таймаут на задачу, сек
completion_marker: "<promise>COMPLETE</promise>"

git:
  enabled: true                # false → коммиты выключены; также авто-пропуск, если это не git-репозиторий
  auto_commit: true
  message_template: "feat: task #{id} - {title}"

context:                                      # все пути — относительно REPO_ROOT (родитель ai-flow/)
  tasks_dir: ai-flow/docs/tasks               # где лежат task-NN.md (+ (done))
  specs_dir: ai-flow/docs/specs               # в промт идут только имена файлов (указатели)
  memories_dir: .serena/memories              # память Serena в КОРНЕ (сырые .md, читаются напрямую)
  progress_file: ai-flow/docs/tasks/progress.md
  agent_prompt: ai-flow/docs/prompts/PROMT_AGENT.md
  inline_memories: false                      # false → в промт только указатели на записи памяти (экономия контекста)

agents:
  # Claude Code — https://docs.claude.com/claude-code
  claude:
    command: "claude --model {model} --print --dangerously-skip-permissions"
    model: sonnet

  # OpenAI Codex CLI — промт читается из stdin через "-"
  # ВНИМАНИЕ: сверь флаги с установленной версией `codex exec --help`
  codex:
    command: "codex exec -m {model} --dangerously-bypass-approvals-and-sandbox --skip-git-repo-check -"
    model: gpt-5-codex

  # zcode / Z.ai GLM — headless-режим
  # ВНИМАНИЕ: сверь флаги с `zcode --help`; вариант через Claude Code + прокси Z.ai см. в env
  zcode:
    command: "zcode -p -m {model}"
    model: glm-4.6
    # env:
    #   ANTHROPIC_BASE_URL: "https://api.z.ai/api/anthropic"
    #   ANTHROPIC_AUTH_TOKEN: "${ZAI_API_KEY}"
```

В `README.md` явно предупреди, что точные флаги `codex`/`zcode` нужно сверить с их `--help`,
т.к. CLI быстро меняются — менять только строку `command`, остальной пайплайн универсален.

---

### 3. `CLAUDE.md` — минимальный свод правил + таблица памяти Serena (на English)

Ориентир — `mentorship-bot/CLAUDE.md`, но БЕЗ прикладной специфики, короткий, **на английском**.
Раздел «Project knowledge» — общий с `PROMT_SERENA.md` (§5.4): та же таблица `read_memory(...)`
по task-триггерам (это и есть «минимальные ссылки, загружаемые по необходимости»).
Строку `Communication language` подставляет `init.py --comm-lang` (по умолчанию English).
Содержимое (адаптируй формулировки, смысл сохрани):

```markdown
# CLAUDE.md

Base repository for AI-driven projects. This is the single source of truth for rules.
Load Serena memories and docs **on demand** — do not preload everything into context.

**Communication language: English.** <!-- set by init.py --comm-lang -->

## Workflow

- Flow infrastructure lives under `ai-flow/`. Root keeps only `CLAUDE.md`, `AGENTS.md`, `.claude/`, `.serena/`.
- Planning prompts live in `ai-flow/docs/prompts/` (`PROMT_SPEC`, `PROMT_TASKS`, `PROMT_AGENT`, `PROMT_SERENA`).
- Read-only context specs live in `ai-flow/docs/specs/`.
- **Task artifacts ALWAYS go into `ai-flow/docs/tasks/`** — one file per task (see `ai-flow/docs/tasks/README.md`).
- Automated execution: `python ai-flow/run_tasks.py` (config `ai-flow/agents.yml`).
- A completed task file is renamed with a `(done)` suffix: `task-NN (done).md`.

## Project knowledge (Serena memories)

Run `list_memories` at session start to confirm what's available. Memories are plain `.md`
files under `.serena/memories/` — readable directly even without the Serena MCP.

Mandatory reads — call BEFORE the matching task:

| Task trigger | Required call |
|---|---|
| Structural changes, new modules | `read_memory("architecture-overview")` |
| Touching auth/authz code | `read_memory("auth-conventions")` |
| Writing or modifying tests | `read_memory("testing-patterns")` |
| Adding DB queries or migrations | `read_memory("db-access-rules")` |
| Adding/modifying HTTP endpoints | `read_memory("api-conventions")` |
| Any non-trivial change | `read_memory("error-handling")` |
| Verifying work is done | `read_memory("build-and-verify")` |

<!-- Keep this table in sync with actual memories: drop rows without a memory, add new triggers. -->

## Always-apply rules

- Task setup → artifacts only in `docs/tasks/` (format: `docs/tasks/README.md`).
- **New/changed reusable pattern in code** → create/update the matching `.serena/memories/<name>.md`
  via `write_memory(...)` and keep the table above in sync. Never silently diverge from a memory —
  fix the memory or escalate the conflict.
- **Behavior/architecture changed** → update the corresponding file under `docs/` (spec / README)
  in the same change — docs must not lag behind code.
- Git commits: a single-line message, **≤155 characters**. Do NOT mention Claude, AI, or any tool —
  no `Co-Authored-By`, no "Generated with …" footers, no tool names anywhere in the message.
```

---

### 4. `AGENTS.md` — универсальный редирект на CLAUDE.md

Файл `AGENTS.md` читают Codex, Cursor, Gemini CLI, Copilot, Windsurf, zcode и др.
Сделай его тонким редиректом (полное содержимое):

```markdown
# AGENTS.md

Этот репозиторий конфигурируется через **CLAUDE.md** — это единственный источник правды.

Любой AI-инструмент или агент (Codex, Cursor, Gemini CLI, GitHub Copilot, Windsurf,
zcode/GLM и другие) обязан прочитать и соблюдать **[CLAUDE.md](./CLAUDE.md)**:
- соглашения и правила проекта,
- рабочий процесс задач (`docs/tasks/`, `docs/prompts/`),
- база знаний в памяти Serena (загружать по необходимости).

Не дублируй инструкции здесь. При любых сомнениях — следуй CLAUDE.md.
```

---

### 5. `docs/prompts/` — планирующие промты (все — на English)

**5.1. `PROMT_TASKS.md`** — скопируй `D:/Work/VideoDownloaderBot/docs/tasks/PROMT_TASKS.md`
как есть (он на English), с единственной правкой в §8: завершённые задачи переименовываются в
`task-{NN} (done).md` (а не `(Completed)`). Сохрани требование, что выход — по файлу на задачу в `docs/tasks/`.

**5.2. `PROMT_AGENT.md`** — адаптируй `D:/Work/VideoDownloaderBot/PROMT_AGENT.md` (на English):
- Убери привязку к .NET/C# (сделай язык-агностичным: «build the project and run tests
  with the project's own tooling», без конкретики про сборку).
- Раздел «Before Starting»: read root `CLAUDE.md`; из его таблицы «Project knowledge» вызвать
  нужные `read_memory(...)` по task-триггеру (память — обычные `.md`, читаются напрямую даже без MCP);
  read relevant specs из `docs/specs/`; read `docs/tasks/progress.md`.
- Раздел «Progress Report»: как в оригинале — APPEND в `docs/tasks/progress.md`.
- Раздел «Consolidate knowledge»: при новом/изменённом переиспользуемом паттерне — `write_memory("<name>", …)`
  в `.serena/memories/` (формат — как в `PROMT_SERENA.md` §Phase 3) и синхронизировать таблицу
  «Project knowledge» в `CLAUDE.md`. Never silently diverge from a memory.
- **Новый раздел «Keep docs in sync»**: если задача изменила поведение/архитектуру/команды —
  синхронно обновить соответствующий файл в `docs/` (spec/README) и релевантную запись памяти
  (`architecture-overview`, `suggested-commands`, `build-and-verify` и т.п.).
- Раздел «Completion»: печатать ровно `<promise>COMPLETE</promise>`; НЕ делать git commit
  (коммитит оркестратор).

**5.3. `PROMT_SPEC.md`** — промт для написания спецификации по требованиям (на English, язык-агностично).
Структура итоговой спецификации, которую он должен требовать:
`## Overview` → `## Goals / Non-goals` → `## Architecture & Layers` → `## Components`
(по компонентам: ответственность, интерфейсы/сигнатуры, данные) → `## Data model`
→ `## External integrations` → `## Acceptance criteria` → `## Open questions`.
Файлы спеки складываются в `docs/specs/` с числовым префиксом (`00-overview.md`, `01-…`).

**5.4. `PROMT_SERENA.md`** — промт bootstrap-а памяти Serena (на English). Это доработанная версия
пользовательского промта, СОВМЕЩЁННАЯ с §8: он и создаёт стартовую память проекта, и делает wiring.
Возьми текст ниже дословно (это финальная редакция — учти отличия от исходника пользователя):
**отличие 1** — Phase 4 обновляет таблицу «Project knowledge» в **`CLAUDE.md`** (наш источник правды),
а НЕ в `AGENTS.md` (`AGENTS.md` остаётся тонким редиректом на `CLAUDE.md`);
**отличие 2** — не перезаписывай shipped-память `suggested-commands`/`task-completion`, а дополняй.

````markdown
# PROMT_SERENA — Bootstrap persistent project knowledge (Serena)

You are bootstrapping persistent project knowledge for AI coding agents on this codebase.
Goal: populate Serena memories with project-specific patterns and wire them into **CLAUDE.md**
(the project's source-of-truth instructions file; `AGENTS.md` only redirects to it) with direct
`read_memory(...)` calls — not filename hints.

## Phase 1 — Discover patterns

Investigate the codebase systematically. Use Serena's tools (`get_symbols_overview`, `find_symbol`,
`search_for_pattern`, `list_dir`) — do not read every file blindly. For each category, find ≥3 real
examples before drawing a conclusion. If patterns conflict, note both and flag the inconsistency
instead of picking one.

Categories:
- Architecture & layering — module boundaries, dependency direction, where business logic lives
- Error handling — exception types, propagation, what gets logged vs rethrown
- Testing — framework, naming, structure (AAA/GWT), mocking conventions, location
- Naming — files, types, methods, variables — note deviations from language defaults
- Data access — ORM/query patterns, transaction boundaries, repository shape
- API design — request/response shapes, validation, versioning, auth flow
- Configuration & secrets — where they live, how loaded, env handling
- Logging & observability — logger setup, levels, structured fields, tracing
- Build & verify — exact commands for build, test, lint, typecheck (run them once to confirm they
  work — do not guess)
- Commit/PR conventions — branch naming, commit format, PR template

## Phase 2 — Decide what becomes a memory

A pattern qualifies only if ALL hold:
- Non-obvious from a quick code read
- Violating it causes real problems (broken builds, regressions, review rejection)
- Stable (won't change weekly)

Skip anything a linter/formatter enforces, anything language conventions already imply, and one-off
historical decisions with no ongoing consequence.

Group memories by *task trigger*, not topic. Ask: "When would the agent need this?" Aim for 5–10
memories total, each ≤80 lines. Do NOT overwrite the shipped memories `suggested-commands` and
`task-completion` — extend them if needed. Suggested triggers (drop any that don't apply, add others):
- architecture-overview — before structural changes
- auth-conventions — when touching auth code
- testing-patterns — before writing/modifying tests
- db-access-rules — when adding queries or migrations
- api-conventions — when adding/modifying endpoints
- error-handling — for any non-trivial change
- build-and-verify — before declaring work done

## Phase 3 — Write the memories

For each memory, use this structure, then save with `write_memory("<name>", "<content>")`:

# <Name>

## When to consult
<1–2 lines: which tasks trigger this read>

## Rules
- <Concrete, enforceable statement, with file:line reference where possible>

## Canonical examples in this codebase
- <path/to/file.ext> — <what makes it canonical>

## Anti-patterns
- <What NOT to do, with the reason>

## Phase 4 — Update CLAUDE.md

Add (or replace) the "Project knowledge (Serena memories)" section using direct tool calls. Format:

## Project knowledge (Serena memories)

Run `list_memories` at session start to confirm what's available.

Mandatory reads — call BEFORE the matching task:

| Task trigger | Required call |
|---|---|
| Structural changes, new modules | `read_memory("architecture-overview")` |
| Touching auth/authz code | `read_memory("auth-conventions")` |
| Writing or modifying tests | `read_memory("testing-patterns")` |
| Adding DB queries or migrations | `read_memory("db-access-rules")` |
| Adding/modifying HTTP endpoints | `read_memory("api-conventions")` |
| Verifying work is done | `read_memory("build-and-verify")` |

After establishing a new pattern or correcting an outdated one, update with `write_memory(...)`.
Do not silently diverge from a memory — fix the memory or escalate the conflict.

Use the actual memory names you created. Drop rows whose memory you didn't create. No placeholders.

## Phase 5 — Self-check before reporting done

1. Every memory written is referenced from CLAUDE.md (no orphans).
2. Every CLAUDE.md row points to an existing memory — verify with `list_memories`.
3. Each memory contains ≥1 concrete codebase reference, not just abstract rules.
4. No memory duplicates another memory's content.
5. Build/test commands in `build-and-verify` were actually executed and confirmed.

## Final report

- Memories created: list with one-line summaries
- CLAUDE.md diff
- Pattern conflicts found in the codebase that the team should resolve
````

---

### 6. `docs/tasks/` — постановка задач

**6.1. `README.md`** — опиши (RU), опираясь на `mentorship-bot/docs/tasks/README.md`:
- Что такое задача, где живёт (`docs/tasks/task-NN.md`), нейминг и жизненный цикл:
  `task-NN.md` (pending) → после выполнения `run_tasks.py` → `task-NN (done).md`.
- Таблицу задач со статусами и граф зависимостей (как оформлять).
- **Шаблон задачи** (встрой прямо в README) — двуязычно совместимый с парсером `run_tasks.py`
  (`Depends on:` / `Зависит от:`). Базовый шаблон (RU, по образцу mentorship-bot + VDB):

  ```markdown
  # Task #NN: <Заголовок>

  ## Overview
  <1–2 предложения: что делаем и зачем>

  ## Motivation
  <какую проблему решает>

  ## Changes

  ### 1. <Конкретное действие>
  **File**: `path/to/file.ext`
  <сигнатуры/структуры/схемы — достаточно, чтобы реализовать без домыслов>

  ## Dependencies
  - Depends on: Task #X (что именно нужно)
  - Blocks: Task #Y (что предоставляет)

  ## Acceptance Criteria
  1. [ ] <проверяемый критерий>

  ## Notes (optional)
  <крайние случаи, ограничения>
  ```

**6.2. `INDEX.md`** — заготовка (по образцу VDB `docs/tasks/INDEX.md`): пустые секции
«Phase Overview», «Dependency Graph», «Progress Table», «Task Files» с пояснением-комментарием,
что заполняется при декомпозиции через `PROMT_TASKS.md`.

**6.3. `progress.md`** — можно не создавать вручную: оркестратор создаёт его при первом запуске
с секцией `## Codebase Patterns`. Но добавь короткий `progress.md`-заготовку с этой секцией и пояснением.

---

### 7. `docs/specs/README.md`

Короткий файл: сюда кладутся спецификации-контекст (read-only), нейминг `NN-name.md`,
они подаются агенту как указатели (`run_tasks.py` перечисляет их имена). Генерируются через `PROMT_SPEC.md`.

---

### 8. `.serena/` — конфиг и стартовая память (совмещено с PROMT_SERENA)

Модель памяти единая с §5.4: записи именуются по **task-триггеру** (flat, kebab-case),
на English; project-specific записи создаёт `PROMT_SERENA.md`, а таблица `read_memory(...)`
живёт в `CLAUDE.md`. Здесь только конфиг + две «встроенные» записи про сам рабочий процесс шаблона.

**8.1. `.serena/project.yml`** — возьми за основу `VideoDownloaderBot/.serena/project.yml`, но:
- `project_name: "ai-template"`.
- `languages` — ОДИН язык-плейсхолдер с крупным комментарием «REPLACE with your project language»
  (например `- python`); фактически проставляется `init.py --lang`.
- Остальные поля — дефолтные (как в эталоне).

**8.2. Встроенные записи памяти** (English, обычные `.md`, ship с шаблоном; `PROMT_SERENA` их НЕ перезаписывает):
- `memories/suggested-commands.md` — реальные команды репозитория: `python run_tasks.py`
  (`--agent`, `--model`, `--dry-run`, `--task`), `python init.py init/adapt/list-tools`, где лежат промты/задачи.
- `memories/task-completion.md` — критерии «done»: build/tests зелёные (`read_memory("build-and-verify")`),
  дописан `progress.md`, при новом паттерне обновлена память + таблица в `CLAUDE.md`, синхронизированы `docs/`.

**8.3. Project-specific записи — НЕ пиши руками.** Их создаёт запуск `docs/prompts/PROMT_SERENA.md`
(через инструмент пользователя или скилл `sync-docs`): `architecture-overview`, `testing-patterns`,
`db-access-rules`, `api-conventions`, `error-handling`, `auth-conventions`, `build-and-verify` —
по task-триггерам, с wiring в таблицу `CLAUDE.md`. В свежесозданном шаблоне их ещё нет — это нормально.

---

### 9. `README.md` — руководство по репозиторию

Напиши на русском, с разделами:
1. **Назначение** — базовый шаблон для новых AI-проектов: планирование → задачи → авто-выполнение → самоподдержка знаний.
2. **Структура репозитория** — дерево с пояснениями.
3. **Установка/инициализация (`init.py`)** — в новый или существующий репозиторий, выбор инструмента
   (`--tool`), языка проекта (`--lang`) и языка коммуникации (`--comm-lang`); авто-настройка Serena MCP.
4. **Рабочий процесс (end-to-end):**
   - написать спецификацию (`docs/prompts/PROMT_SPEC.md` → `docs/specs/`);
   - наполнить память проекта (`docs/prompts/PROMT_SERENA.md` → `.serena/memories/*` + таблица в CLAUDE.md);
   - декомпозировать в задачи (`docs/prompts/PROMT_TASKS.md` → `docs/tasks/task-NN.md`);
   - выполнить (`python run_tasks.py`), задачи автоматически помечаются `(done)`.
5. **Запуск `run_tasks.py`** — примеры на все три агента:
   - `python run_tasks.py` (claude по умолчанию);
   - `python run_tasks.py --agent codex --model gpt-5-codex`;
   - `python run_tasks.py --agent zcode --model glm-4.6`;
   - `--dry-run`, `--task 03`. Требование: `pip install pyyaml`.
6. **Справка по `agents.yml`** — что настраивается; предупреждение сверять флаги codex/zcode с их `--help`.
7. **Языки** — промты/агенты/скиллы/память на English; язык коммуникации задаётся `--comm-lang` и живёт в CLAUDE.md.
8. **Память Serena** — что это, что храним; принцип «минимальный контекст: таблица `read_memory(...)` в
   CLAUDE.md, загрузка по требованию».
9. **Гайд по настройке Serena под свой инструмент** (см. §10) — обязательный раздел.
10. **Самоподдержка** — как агент обновляет память и `docs/` (правила из CLAUDE.md/PROMT_AGENT.md).

---

### 10. Гайд по настройке Serena (раздел README) — обязательно

Основной путь — **автоматический**: `python init.py setup-serena --tool <TOOL>` (или на этапе `init`).
Раздел README должен объяснить это + дать ручной fallback:

- **Требования:** установленный `uv`/`uvx` (`pip install uv` или см. astral.sh/uv).
- **Авто:** `python init.py init --tool claude` / `python init.py setup-serena --tool codex` —
  скрипт сам пропишет MCP-сервер Serena под инструмент (см. §14.5).
- **Ручной fallback (Claude Code):**
  ```bash
  claude mcp add serena -- uvx --from git+https://github.com/oraios/serena \
    serena start-mcp-server --context ide-assistant --project "$(pwd)"
  ```
- **Ручной fallback (Codex):** секция `[mcp_servers.serena]` в `~/.codex/config.toml`
  (`command = "uvx"`, `args = [..., "start-mcp-server", "--context", "codex", "--project", "."]`).
- **Первичное наполнение памяти:** после настройки MCP выполнить `docs/prompts/PROMT_SERENA.md`
  (через инструмент или скилл `sync-docs`) — он создаст project-specific записи и таблицу в `CLAUDE.md`.
- **Важно:** память Serena — обычные `.md` в `.serena/memories/`, поэтому даже без MCP
  агент (и `run_tasks.py`) читают их напрямую с диска. MCP нужен для удобного поиска/редактирования.
- Ссылка на офиц. репозиторий: https://github.com/oraios/serena — свериться с актуальной документацией.

---

### 11. `.gitignore` (в корне) + вариант «не коммитить»

**Репозиторный `.gitignore` (default, для тех, кто версионирует флоу):**
Игнорируй: `.serena/cache/`, `.claude/cache/`, `.claude/tsc-cache/`, `__pycache__/`, `*.pyc`,
`ai-flow/**/__pycache__/`, временные файлы, локальные env (`.env`), `BUILD_PROMPT.md`.
ОБЯЗАТЕЛЬНО оставляй в git: `.serena/project.yml`, `.serena/memories/**`, `ai-flow/**`,
`CLAUDE.md`, `AGENTS.md`.

**Вариант «не коммитить флоу» — задокументируй в `ai-flow/README.md`.**
Пользователь, который не хочет тащить флоу в git, исключает весь набор одним из способов:
- **Global gitignore** (личный, на все репозитории машины) — рекомендуется, если флоу используется во
  многих проектах:
  ```bash
  git config --global core.excludesFile ~/.gitignore_global
  printf '%s\n' 'ai-flow/' '.claude/' '.serena/' 'CLAUDE.md' 'AGENTS.md' 'BUILD_PROMPT.md' >> ~/.gitignore_global
  ```
- **Per-repo без коммита правила** — `.git/info/exclude` (те же строки), если нужно только для одного репо.

Набор для исключения (всё, что добавляет флоу): `ai-flow/`, `.claude/`, `.serena/`, `CLAUDE.md`, `AGENTS.md`.
Оговорка: `.gitignore` действует только на неотслеживаемые файлы — если что-то уже закоммичено,
сначала `git rm --cached <path>`. `init.py` может подсказать эти команды в финальном отчёте.

---

### 12. `.claude/agents/` — два разных субагента Claude Code

Формат субагента Claude Code — markdown с YAML-фронтматтером (`name`, `description`, `tools`, опц. `model`)
и системным промтом в теле. **Тело/описание — на English.** **Обязательно ДВА разных агента**
(нельзя объединять постановку задач и документацию).

**12.1. `task-author.md` — СУБАГЕНТ формирования новой задачи.**
```markdown
---
name: task-author
description: >
  Forms new executable tasks. Takes a requirement or a spec reference and decomposes it into one or
  more self-contained docs/tasks/task-NN.md files. Use proactively when the user asks to "create a task",
  "write up a task", or "decompose a feature".
tools: Read, Grep, Glob, Write, Edit
---
```
Системный промт (English, суть):
- You are a technical lead who writes tasks. Take decomposition rules and the task format from
  `docs/prompts/PROMT_TASKS.md` and `docs/tasks/README.md`. Tasks must be atomic, self-contained,
  with full signatures and file paths.
- Before writing, study existing code and call the relevant `read_memory(...)` from the CLAUDE.md
  "Project knowledge" table so tasks match project conventions.
- **Output ONLY into `docs/tasks/`**: `task-NN.md` files per template; set `Depends on:` (DAG),
  update `docs/tasks/INDEX.md` (table + graph) and the progress table.
- Numbering = topological order. Do not implement code — only author tasks.
- Do NOT touch docs/specs/memories beyond tasks — that is `doc-keeper`'s scope.

**12.2. `doc-keeper.md` — СУБАГЕНТ создания/актуализации документации.**
```markdown
---
name: doc-keeper
description: >
  Creates and maintains documentation and the knowledge base. Writes/updates docs/specs, README, and
  Serena memories (.serena/memories/*), and keeps the "Project knowledge" read_memory(...) table in
  CLAUDE.md in sync. Use proactively after code/behavior changes, when docs drift, and to bootstrap
  project memories by running docs/prompts/PROMT_SERENA.md.
tools: Read, Grep, Glob, Write, Edit
---
```
Системный промт (English, суть):
- You are a documentation & knowledge engineer. Source of truth is the code; docs must not lag behind.
- Duties: (a) bootstrap project memories by executing `docs/prompts/PROMT_SERENA.md` (discover → write
  trigger-based memories → wire the CLAUDE.md table); (b) on behavior/architecture change — update the
  matching `docs/spec`/`README`; (c) on a new/changed reusable pattern — `write_memory("<name>", …)`
  and keep the CLAUDE.md "Project knowledge" table in sync. Never silently diverge from a memory.
- Keep context minimal: CLAUDE.md holds only the table; full content lives in memories/specs.
- Do NOT create tasks (`docs/tasks/`) and do NOT write application code — that is `task-author`/executors.

Явно укажи в обоих: агенты РАЗНЫЕ и с непересекающейся зоной ответственности.

---

### 13. `.claude/skills/` — скиллы-обёртки для субагентов

Формат скилла Claude Code — каталог со `SKILL.md` (фронтматтер `name`, `description` + инструкции).
**Содержимое `SKILL.md` — на English.**

**13.1. `new-task/SKILL.md`** — скилл постановки задачи:
- `description`: "Author new task file(s) in docs/tasks/ from a requirement or a spec."
- Body: read `docs/prompts/PROMT_TASKS.md`; delegate to the `task-author` subagent (via Agent/Task)
  with the given requirement; output — created `docs/tasks/task-NN.md` and updated INDEX.

**13.2. `sync-docs/SKILL.md`** — скилл синхронизации документации/памяти:
- `description`: "Bootstrap/refresh Serena memories and docs to match the current codebase."
- Body: determine scope (given scope / recent changes; or full bootstrap → run `docs/prompts/PROMT_SERENA.md`);
  delegate to the `doc-keeper` subagent; output — updated `docs/*`, `.serena/memories/*`, and the
  "Project knowledge" table in `CLAUDE.md`.

Скиллы — тонкие: вся логика в субагентах, скилл лишь маршрутизирует и передаёт вход.

---

### 14. `ai-flow/init.py` — CLI инициализации/адаптации в существующий или новый репозиторий

Назначение: развернуть весь рабочий процесс в целевом репозитории (новом или существующем)
и **адаптировать Claude-Code-специфику (субагенты/скиллы) под нужный инструмент** пользователя.
Только стандартная библиотека Python, кроссплатформенно (Windows/Unix). Не перезаписывает файлы
пользователя без `--force`; идемпотентно; `.gitignore` — дополняет, а не затирает.

**14.1. Команды CLI.** (`init.py` лежит в `ai-flow/`; вызывается как `python ai-flow/init.py …`)
- `python ai-flow/init.py init [--target DIR] [--tool TOOL] [--lang LANG] [--comm-lang LANG] [--force] [--no-serena]`
  Разворачивает в `--target` (по умолчанию текущий каталог) новый layout:
  - **в подкаталог `ai-flow/`**: `run_tasks.py`, `init.py`, `agents.yml`, `README.md`,
    `docs/` (prompts, tasks/README+INDEX+progress, specs/README);
  - **в КОРЕНЬ `--target`**: `CLAUDE.md`, `AGENTS.md`, `.claude/agents/*`, `.claude/skills/*`,
    `.serena/` (project.yml + стартовые memories), записи в `.gitignore`.
  - `--lang` — язык проекта в `.serena/project.yml` (для LSP Serena).
  - `--comm-lang` — **язык коммуникации** (на каком языке агент говорит с пользователем); подставляется
    в строку `Communication language:` файла `CLAUDE.md`. По умолчанию English. Промты/агенты/скиллы —
    всегда English (не зависит от этого флага).
  - `--tool` — целевой инструмент (см. 14.2); также выставляет `default_agent` в `agents.yml`.
  - Настройка Serena MCP под инструмент — см. 14.5 (можно отключить `--no-serena`).
- `python init.py adapt --tool TOOL [--target DIR]` — (пере)генерирует адаптеры под инструмент в существующем проекте.
- `python init.py setup-serena --tool TOOL [--target DIR]` — только (пере)настроить Serena MCP под инструмент (см. 14.5).
- `python init.py list-tools` — список поддерживаемых инструментов.

**14.2. Матрица адаптации под инструмент** (субагенты/скиллы Claude Code → нативные механизмы инструмента).
Реализуй генераторы для каждого `--tool`; неизвестный инструмент → сообщить и предложить `claude` по умолчанию.

| Инструмент | Файл-инструкция | Субагенты | Скиллы/команды |
|------------|-----------------|-----------|----------------|
| `claude` (по умолчанию) | `CLAUDE.md` | `.claude/agents/*.md` (как есть) | `.claude/skills/*/SKILL.md` (как есть) |
| `codex` | `AGENTS.md` (→ CLAUDE.md) | `.codex/prompts/{task-author,doc-keeper}.md` (ручной вызов) | те же prompt-файлы |
| `cursor` | `.cursor/rules/000-claude.mdc` (→ CLAUDE.md) | `.cursor/rules/{task-author,doc-keeper}.mdc` | — (правила) |
| `gemini` | `GEMINI.md` (→ CLAUDE.md) | `.gemini/prompts/*.md` | — |
| `zcode` | `AGENTS.md`/`CLAUDE.md` (GLM Claude-совместим через прокси) | переиспользовать `.claude/*` | переиспользовать `.claude/*` |

Принципы адаптеров:
- Тело субагента/скилла — единый источник; под каждый инструмент оборачивается в его формат
  (фронтматтер `.mdc` для Cursor, простой markdown-prompt для Codex/Gemini).
- Файл-инструкция инструмента всегда лишь **перенаправляет на `CLAUDE.md`** (не дублирует правила),
  как это делает `AGENTS.md`.
- Для `zcode`/`claude` нативные `.claude/*` сохраняются; в `agents.yml` при `zcode` — подсказать env-прокси Z.ai.

**14.3. Поведение установки в существующий репозиторий.**
- Обнаружить существующие `CLAUDE.md`/`AGENTS.md`/`docs/` и НЕ затирать: при конфликте — писать рядом
  (`*.ai-template.md`) или в вывод и предупреждать; сливать только `.gitignore`.
- По завершении печатать краткий отчёт: что создано, что пропущено, следующие шаги (язык Serena,
  флаги CLI, статус настройки Serena MCP, запустить `PROMT_SERENA` для наполнения памяти).

**14.4. README.** Добавь раздел «Установка в существующий проект»:
```bash
# новый проект под свой инструмент (проектный язык + язык коммуникации)
python init.py init --target ../my-new-project --tool claude --lang typescript --comm-lang ru

# инициализация в текущем существующем репозитории под Codex
python init.py init --tool codex

# только переадаптация под другой инструмент
python init.py adapt --tool cursor

# только настроить Serena MCP под инструмент
python init.py setup-serena --tool claude
```

**14.5. Авто-настройка Serena MCP под инструмент (обязательно).**
`init.py` сам конфигурирует Serena MCP для выбранного `--tool` (кроме `--no-serena`). Идемпотентно,
с понятным выводом; при отсутствии `uvx`/CLI инструмента — не падать, а напечатать точную ручную команду.
- **claude:** выполнить `claude mcp add serena -- uvx --from git+https://github.com/oraios/serena
  serena start-mcp-server --context ide-assistant --project <target>` (через `subprocess`; если `claude`
  не найден — напечатать команду для ручного запуска).
- **codex:** записать/дополнить MCP-сервер в конфиг Codex (`~/.codex/config.toml` или проектный
  `.codex/config.toml`): секция `[mcp_servers.serena]` с `command = "uvx"` и `args = [..., "start-mcp-server",
  "--context", "codex", "--project", "<target>"]`. Не дублировать, если уже есть.
- **cursor:** записать `<target>/.cursor/mcp.json` c сервером `serena` (`command: "uvx"`, те же `args`).
- **gemini / прочие:** записать соответствующий MCP-конфиг инструмента, если формат известен; иначе —
  напечатать готовую команду `uvx … serena start-mcp-server --project <target>` для ручного добавления.
- **zcode/GLM:** как для `claude` (Claude-совместимый MCP), при необходимости подсказать env-прокси Z.ai.
- После настройки напомнить: наполнить память проекта — запустить `docs/prompts/PROMT_SERENA.md`
  (через инструмент или скилл `sync-docs`), т.к. в свежем шаблоне project-specific памяти ещё нет.

---

## Ключевые правила поведения (закодировать в артефактах)

1. **Выход по задачам — только `docs/tasks/`** (зафиксировано в CLAUDE.md и PROMT_TASKS.md).
2. **Пометка `(done)`** после выполнения через `run_tasks.py` (переименование файла).
3. **Самоподдержка памяти:** новый общий паттерн → `write_memory("<name>", …)` в `.serena/memories/`
   + синхронизация таблицы `read_memory(...)` в CLAUDE.md (правило в CLAUDE.md и PROMT_AGENT.md).
4. **Синхронизация docs:** изменилось поведение/архитектура → обновить соответствующий `docs/*` и память.
5. **Минимальный контекст:** CLAUDE.md держит только таблицу `read_memory(...)`; полные записи/спеки
   грузятся по требованию; `run_tasks.py` по умолчанию подставляет указатели (`inline_memories: false`).
6. **Универсальность инструментов:** AGENTS.md перенаправляет всё на CLAUDE.md.
7. **Языки:** промты/агенты/скиллы/память — English; язык коммуникации — `init.py --comm-lang` → CLAUDE.md.
8. **Serena:** `init.py` сам настраивает MCP под инструмент; наполнение памяти — `PROMT_SERENA`.

---

## Критерии приёмки (проверь перед завершением)

1. [ ] Дерево репозитория соответствует разделу «Итоговая структура».
2. [ ] `python run_tasks.py --dry-run` отрабатывает без ошибок на пустом `docs/tasks/`
       (сообщает, что задач нет) и с одной тестовой задачей показывает план и корректную команду агента.
3. [ ] `run_tasks.py` читает `agents.yml`, поддерживает `--agent claude|codex|zcode`, `--model`, `--task`, `--config`.
4. [ ] Завершение задачи переименовывает файл в `task-NN (done).md`; детект `(done)` работает.
5. [ ] Коммиты пропускаются без ошибок, если каталог не git-репозиторий.
6. [ ] `CLAUDE.md` — короткий, **на English**, с таблицей `read_memory(...)` по task-триггерам,
        строкой `Communication language:` и правилами самоподдержки; без прикладной специфики.
7. [ ] `AGENTS.md` перенаправляет на CLAUDE.md.
8. [ ] `docs/prompts/` содержит `PROMT_SPEC.md`, `PROMT_TASKS.md` (с `(done)`), `PROMT_AGENT.md`
        и `PROMT_SERENA.md` — все на English; PROMT_SERENA пишет память + таблицу в CLAUDE.md.
9. [ ] `docs/tasks/README.md` содержит шаблон задачи, совместимый с парсером (`Depends on:` / `Зависит от:`).
10. [ ] `.serena/project.yml` + встроенные записи `suggested-commands`/`task-completion` (English) на месте;
        project-specific память не захардкожена (её создаёт PROMT_SERENA).
11. [ ] `README.md` содержит гайд по Serena: авто-настройка `init.py setup-serena` + ручной fallback.
12. [ ] `.gitignore` не игнорирует память Serena и docs.
13. [ ] `.claude/agents/task-author.md` и `.claude/agents/doc-keeper.md` — ДВА разных субагента (English)
        с непересекающейся зоной ответственности (постановка задач vs документация).
14. [ ] `.claude/skills/new-task/` и `.claude/skills/sync-docs/` содержат `SKILL.md` (English), делегирующие
        соответствующим субагентам.
15. [ ] `python init.py list-tools` работает; `python init.py init --target <tmp> --tool claude --lang python --comm-lang ru`
        разворачивает процесс в чистый каталог (не затирая файлы без `--force`) и проставляет язык коммуникации в CLAUDE.md.
16. [ ] `python init.py adapt --tool codex` (и `cursor`) генерирует адаптеры-редиректы на CLAUDE.md
        и обёртки субагентов в формате инструмента.
17. [ ] `README.md` содержит раздел «Установка в существующий проект» с примерами `init.py`.
18. [ ] `python init.py setup-serena --tool claude` конфигурирует Serena MCP (или печатает точную ручную
        команду, если `claude`/`uvx` не найдены) — без падения.

---

## Порядок выполнения

1. Прочитай источники (§ «Источники для адаптации»).
2. Создай структуру каталогов и все файлы по §1–§14 (включая субагентов, скиллы и `init.py`).
3. Проверь критерии приёмки: `run_tasks.py --dry-run` (создай временную `docs/tasks/task-01.md`,
   прогони, удали), `init.py list-tools`, `init.py init --target <tmp> --tool claude` во временный
   каталог, `init.py adapt --tool codex`.
4. Кратко отчитайся: что создано, как запускать (`run_tasks.py`, `init.py`), что предстоит донастроить
   пользователю (язык в `.serena/project.yml`, флаги codex/zcode, установка Serena MCP под инструмент).
```
