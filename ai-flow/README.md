# ai-flow

Базовый рабочий процесс для проектов «под AI»: **планирование → постановка задач → автоматическое
выполнение → самоподдержка знаний**. Вся инфраструктура флоу лежит в этом каталоге (`ai-flow/`);
в корне проекта остаются только `CLAUDE.md`, `AGENTS.md`, `.claude/`, `.serena/`.

## Структура

```
<repo>/
├── CLAUDE.md              # единый свод правил + таблица read_memory(...) (English)
├── AGENTS.md              # редирект прочих инструментов на CLAUDE.md
├── .claude/agents,skills  # субагенты task-author, doc-keeper + скиллы new-task, sync-docs
├── .serena/               # конфиг + память Serena (.md)
└── ai-flow/
    ├── run_tasks.py        # оркестратор авто-выполнения
    ├── init.py             # установка/адаптация под инструмент + настройка Serena MCP
    ├── agents.yml          # конфиг агентов (claude / codex / zcode)
    ├── hooks/              # хук синхронизации памяти
    └── docs/
        ├── prompts/        # PROMT_SPEC / PROMT_TASKS / PROMT_AGENT / PROMT_SERENA
        ├── specs/          # спецификации + функциональность: root README + <feature>/{README, IMPLEMENTED}
        ├── tasks/          # задачи по фичам: <YYYYMMddHHmm_FEATURE>/{README, задачи, done/}
        └── CHANGELOG.md    # хронологический журнал
```

## Модель задач и документации

- Задачи группируются по доработкам: `tasks/<YYYYMMddHHmm_FEATURE_NAME>/` с `README.md` (DesignReview),
  файлами задач `<YYYYMMddHHmm_TASK_SUMMARY>.md` и подпапкой `done/` (туда `run_tasks.py` переносит
  выполненные). Порядок — по таймстампу; `Depends on:` уточняет. Подробности — `docs/tasks/README.md`.
- Спецификации и функциональность проекта живут в `docs/specs/` (без отдельной `functionality/`):
  корневой `README.md` (обзор, заполняется при онбординге) и по папке на реализованную фичу —
  `README.md` (целевой) + `IMPLEMENTED.md` (как реализовано). Обновляется автоматически после задач.

## Установка в новый или существующий проект

```bash
# новый проект (язык проекта + язык коммуникации)
python ai-flow/init.py init --target ../my-project --tool claude --lang typescript --comm-lang ru

# инициализация в текущем существующем репозитории под Codex
python ai-flow/init.py init --tool codex

# только переадаптация субагентов/скиллов под другой инструмент
python ai-flow/init.py adapt --tool cursor

# только настроить Serena MCP под инструмент
python ai-flow/init.py setup-serena --tool claude

python ai-flow/init.py list-tools
```

`init` не перезаписывает существующие файлы без `--force`, `.gitignore` дополняет. Поддерживаемые
инструменты: `claude`, `codex`, `cursor`, `gemini`, `zcode`. Для не-Claude инструментов субагенты/скиллы
адаптируются в их формат (`.codex/prompts`, `.cursor/rules`, `.gemini/prompts`), а файл-инструкция
инструмента лишь редиректит на `CLAUDE.md`.

## Рабочий процесс (end-to-end)

1. **Спецификация** — `ai-flow/docs/prompts/PROMT_SPEC.md` → файлы в `ai-flow/docs/specs/`.
2. **Память проекта** — `ai-flow/docs/prompts/PROMT_SERENA.md` (или скилл `/sync-docs`) наполняет
   `.serena/memories/*` и таблицу `read_memory(...)` в `CLAUDE.md`.
3. **Задачи** — `ai-flow/docs/prompts/PROMT_TASKS.md` (или скилл `/new-task`) → папка фичи
   `ai-flow/docs/tasks/<YYYYMMddHHmm_FEATURE>/` с DesignReview `README.md` и файлами задач.
4. **Выполнение** — `python ai-flow/run_tasks.py`; выполненная задача переносится в `<feature>/done/`,
   а `specs/<feature>/{README,IMPLEMENTED}.md` обновляются автоматически.

## Запуск оркестратора

```bash
python ai-flow/run_tasks.py                       # агент по умолчанию (agents.yml)
python ai-flow/run_tasks.py --agent codex --model gpt-5-codex
python ai-flow/run_tasks.py --agent zcode --model glm-4.6
python ai-flow/run_tasks.py --feature user-login  # только совпадающие папки фич
python ai-flow/run_tasks.py --task add-login      # только задачи по имени
python ai-flow/run_tasks.py --dry-run             # план без выполнения
```

Требуется `pip install pyyaml`. Оркестратор берёт задачи из папок фич в порядке таймстампа (строка
`Depends on:` / `Зависит от:` уточняет порядок), передаёт агенту промт через stdin, ждёт маркер
`<promise>COMPLETE</promise>`, ПЕРЕМЕЩАЕТ файл в `<feature>/done/` и (если это git-репозиторий) коммитит.
Флаги codex/zcode в `agents.yml` сверяйте с их `--help` — меняется только строка `command`.

## Языки

Промты, субагенты, скиллы и память — **на English**. Язык коммуникации (как агент говорит с
пользователем) задаётся `init.py --comm-lang` и живёт строкой `Communication language:` в `CLAUDE.md`.

## Хук синхронизации памяти

`ai-flow/hooks/check_memory_sync.py` сверяет таблицу `read_memory(...)` в `CLAUDE.md` с реальными
записями в `.serena/memories/` и предупреждает о рассинхроне (висячие строки без памяти; записи без
строки в таблице). Регистрируется как `SessionStart`-хук в `.claude/settings.json` (`init.py` подмешивает
его в существующий `settings.json`, не затирая прочие хуки; для инструментов claude/zcode).

Это **best-effort напоминание** (не блокирует), запускается на старте сессии. Уровни срабатывания
инструкций: комментарий в `CLAUDE.md` — пассивная заметка; правило-буллет — агент следует по мере
работы; **хук — единственное детерминированное «автоматически»** (запускает харнесс).

Конфигурация — `ai-flow/hooks/hooks.config.json`:

| Ключ | Значение | Смысл |
|------|----------|-------|
| `enabled` | `true`/`false` | главный выключатель |
| `mode` | `"warn"`/`"off"` | warn — печатает уведомление; off — молчит |
| `check_dangling` | `true`/`false` | строки таблицы без файла памяти |
| `check_orphans` | `true`/`false` | записи памяти без строки в таблице |
| `ignore_memories` | список | записи, которые не считать «сиротами» (по умолчанию shipped) |

Полностью отключить — `mode: "off"` в конфиге или убрать блок `SessionStart` из `.claude/settings.json`.
Сделать блокирующим — зарегистрировать на gating-событие и вернуть `exit(2)` при проблемах.

## Настройка Serena

Основной путь — автоматический: `python ai-flow/init.py setup-serena --tool <TOOL>` (или на этапе `init`).
Требуется `uv`/`uvx` (`pip install uv` или https://astral.sh/uv).

Ручной fallback (Claude Code):
```bash
claude mcp add serena -- uvx --from git+https://github.com/oraios/serena \
  serena start-mcp-server --context ide-assistant --project "$(pwd)"
```
Codex — секция `[mcp_servers.serena]` в `~/.codex/config.toml`; Cursor — `.cursor/mcp.json`.
Память Serena — обычные `.md` в `.serena/memories/`, поэтому она читается напрямую даже без MCP;
MCP нужен для удобного поиска/редактирования. Документация: https://github.com/oraios/serena

## Не коммитить флоу

Если не нужно тащить флоу в git, исключите весь набор (`ai-flow/`, `.claude/`, `.serena/`, `CLAUDE.md`,
`AGENTS.md`) через **global gitignore** (личный, на все репозитории) — репозиторный `.gitignore` при этом
не трогается:

```bash
git config --global core.excludesFile ~/.gitignore_global
printf '%s\n' 'ai-flow/' '.claude/' '.serena/' 'CLAUDE.md' 'AGENTS.md' 'BUILD_PROMPT.md' >> ~/.gitignore_global
```

Для одного репозитория без коммита правила — те же строки в `.git/info/exclude`. `.gitignore` действует
только на неотслеживаемые файлы; уже закоммиченное сначала уберите из индекса: `git rm --cached <path>`.
