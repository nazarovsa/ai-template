# Задачи (по фичам)

Задачи группируются по доработкам (фича или фикс — не важно). Одна папка = одна доработка:

```
ai-flow/docs/tasks/
└── YYYYMMddHHmm_FEATURE_NAME/          # FEATURE_NAME — kebab-case название доработки
    ├── README.md                       # DesignReview доработки (шаблон ниже)
    ├── YYYYMMddHHmm_TASK_SUMMARY.md     # задача; TASK_SUMMARY — ≤5 англ. слов через "-"
    └── done/                            # сюда run_tasks.py ПЕРЕМЕЩАЕТ выполненные задачи
```

- `YYYYMMddHHmm` — таймстамп (получить: `date +%Y%m%d%H%M`).
- Задачи выполняются в порядке имён (таймстамп → хронология); строка `Depends on:` уточняет порядок.
- `README.md` внутри папки фичи задачей НЕ считается.
- Создавать доработки: скилл `/new-task` (субагент `task-author`) или `../prompts/PROMT_TASKS.md`.
- После выполнения доработки её функциональность документируется в `../specs/<feature>/`
  (`README.md` — целевой, `IMPLEMENTED.md` — как реализовано) — обновляется автоматически.

## Запуск

```bash
python ai-flow/run_tasks.py                    # все доработки
python ai-flow/run_tasks.py --feature user-login   # только совпадающие папки фич
python ai-flow/run_tasks.py --task add-login       # только задачи по имени
python ai-flow/run_tasks.py --dry-run
```

## Шаблон `README.md` доработки (DesignReview)

Беглый обзор доработки: суть, ценность, архитектура.

```markdown
# <Feature Name>

- Type: feature | fix
- Created: YYYY-MM-DD HH:MM
- Status: planned | in-progress | done

## Summary
<глобальная суть: что и зачем, 2–4 предложения>

## Value
<ценность: пользовательская / бизнес / системная>

## Architecture
<затрагиваемые компоненты, подход, поток данных, ключевые решения>

## Scope
- In scope: <что входит>
- Out of scope: <что не входит>

## Tasks
- [ ] YYYYMMddHHmm_task-summary — <одна строка>

## Acceptance
<как поймём, что доработка готова>
```

## Шаблон файла задачи

Структурные заголовки (`# <Title>`, `## Changes`, `Depends on:`) обязательны — по ним работает парсер
(первый `#`-заголовок = название; `Depends on:` / `Зависит от:` = зависимости; ссылка на другую задачу
по её имени/подстроке или `none`).

```markdown
# <Task title>

## Overview
<что и зачем>

## Changes
### 1. <действие>
**File**: `path/to/file.ext`
<сигнатуры / структуры / схемы>

## Dependencies
- Depends on: <имя другой задачи в этой папке | none>

## Acceptance Criteria
1. [ ] <проверяемый критерий>
```
