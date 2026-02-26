# Vibe Coding Workflow: Claude Code + Codex

> Дата создания: 2026-02-26
> Последнее обновление: 2026-02-26
> Версия: 2.0 (проверено в реальном цикле ревью)

---

## 1. Обзор

Мультимодельный workflow, где **Claude Code** (Opus) пишет планы и код, а **Codex** автоматически ревьюит через Claude Code hooks. Цикл продолжается без участия пользователя, пока Codex не одобрит результат.

### Что нужно для работы

| Компонент | Требование |
|---|---|
| Claude Code | Установлен (`claude` CLI) |
| Codex CLI | Установлен (`codex` CLI), авторизован (`codex login`) |
| Проект | Склонирован с этими файлами в `.claude/` |

### Файлы системы (всё в git)

```
.claude/
  settings.json                  ← конфигурация hooks
  hooks/
    codex-review-hook.sh         ← PostToolUse: ревью планов
    codex-code-review-hook.sh    ← Stop: ревью кода (git diff)
    codex-session-cleanup.sh     ← SessionStart: очистка сессий

docs/
  VIBE_CODING_WORKFLOW.md        ← этот файл (документация)

CLAUDE.md                        ← инструкции для Claude (раздел про автоцикл)
.gitignore                       ← исключает runtime-файлы
```

Runtime-файлы (НЕ в git, создаются автоматически):
```
.codex-plan-session              ← thread_id сессии ревью планов
.codex-code-session              ← thread_id сессии ревью кода
.codex-review-result.md          ← результат последнего ревью
/tmp/codex-hook-debug.log        ← debug-лог хуков
```

---

## 2. Как работает автоцикл

### 2.1 Полный цикл (одно задание пользователя → готовый результат)

```
Пользователь: "Составь план рефакторинга категорий"
        │
        ▼
┌─── Claude Code ──────────────────────────────────────────────┐
│  1. Исследует код (субагенты, Grep, Read)                    │
│  2. Пишет план в *-plan.md (Write/Edit)                      │
│     │                                                        │
│     ▼ ─── PostToolUse HOOK (1-4 мин) ────────────────────    │
│     │  codex-review-hook.sh запускает Codex CLI              │
│     │  Codex ревьюит план → пишет .codex-review-result.md   │
│     │                                                        │
│  3. Claude читает .codex-review-result.md                    │
│     │                                                        │
│     ├── Status: APPROVED → переход к реализации              │
│     │                                                        │
│     └── Status: ISSUES FOUND →                               │
│         4. Claude показывает замечания, принимает/отклоняет   │
│         5. Claude правит план (Edit) → GOTO шаг 2            │
│                                                              │
│  6. План одобрен → параллельная реализация (субагенты)       │
│     │                                                        │
│     ▼ ─── Stop HOOK (при завершении) ────────────────────    │
│     │  codex-code-review-hook.sh ревьюит git diff            │
│     │  Resume план-сессии → Codex знает план + видит код     │
│     │                                                        │
│  7. Если CRITICAL/HIGH → Claude исправляет                   │
│  8. Готово                                                   │
└──────────────────────────────────────────────────────────────┘
```

### 2.2 Ключевой механизм: файл результата

**Проблема:** PostToolUse hook stdout НЕ попадает в контекст Claude (by design Claude Code).

**Решение:** Hook записывает результат Codex в файл `.codex-review-result.md`. Claude читает этот файл после каждого Edit/Write план-файла.

```
Edit *plan*.md → Hook запускается → Codex думает (1-4 мин) →
Hook пишет .codex-review-result.md → Edit возвращается Claude →
Claude делает Read .codex-review-result.md → анализирует →
правит план → снова Edit → снова Hook → ...
```

Инструкция для Claude зашита в CLAUDE.md (раздел "АВТОЦИКЛ CODEX REVIEW").

### 2.3 Session continuity (Codex помнит контекст)

1. Первый вызов → Codex создаёт сессию → `thread_id` → `.codex-plan-session`
2. Следующий Edit → `codex exec resume <thread_id>` → Codex **помнит** свои замечания
3. Stop hook → resume **план-сессии** → Codex знает план + видит код
4. Новая сессия Claude → `SessionStart` hook удаляет session-файлы → чистый лист

---

## 3. Настройка на новом ПК

### 3.1 Установка зависимостей

```bash
# 1. Claude Code (если ещё не установлен)
npm install -g @anthropic-ai/claude-code

# 2. Codex CLI
npm install -g @openai/codex

# 3. Авторизация Codex
codex login
# → откроется браузер, войти в аккаунт OpenAI
```

### 3.2 Конфигурация Codex

Создать `~/.codex/config.toml`:
```toml
model = "gpt-5.3-codex"
model_reasoning_effort = "high"
personality = "pragmatic"
```

### 3.3 Проверка работоспособности

```bash
# Проверить что обе CLI доступны
which claude && which codex

# Проверить что Codex авторизован
codex exec --full-auto "echo hello" 2>&1 | head -5

# Проверить что hooks подхватились (в директории проекта)
cd /path/to/expense_bot
cat .claude/settings.json | jq '.hooks'
```

### 3.4 Тест полного цикла

```bash
# 1. Открыть Claude Code в проекте
cd /path/to/expense_bot
claude

# 2. Попросить создать план
> "Создай план исправления bare except в bot/routers/chat.py"

# 3. Claude создаст *-plan.md → хук запустит Codex →
#    Claude прочитает результат → цикл пойдёт автоматически
```

### 3.5 Troubleshooting

| Проблема | Диагностика | Решение |
|---|---|---|
| Codex не найден | `which codex` → пусто | `npm install -g @openai/codex` |
| Hook не срабатывает | `cat /tmp/codex-hook-debug.log` | Проверить `.claude/settings.json` |
| Codex выдаёт ошибку | `codex exec --full-auto "test" 2>&1` | `codex login` заново |
| Результат не записался | `ls -la .codex-review-result.md` | Проверить permissions на запись |
| Claude не читает файл | Нет Read после Edit | Проверить раздел CLAUDE.md про автоцикл |
| Timeout (>5 мин) | Лог: `Codex finished` отсутствует | Увеличить timeout в settings.json |

---

## 4. Конфигурация hooks

### 4.1 `.claude/settings.json`

```json
{
  "hooks": {
    "SessionStart": [
      {
        "matcher": "startup",
        "hooks": [
          {
            "type": "command",
            "command": "bash \"$CLAUDE_PROJECT_DIR/.claude/hooks/codex-session-cleanup.sh\"",
            "timeout": 5
          }
        ]
      }
    ],
    "PostToolUse": [
      {
        "matcher": "Edit|Write",
        "hooks": [
          {
            "type": "command",
            "command": "bash \"$CLAUDE_PROJECT_DIR/.claude/hooks/codex-review-hook.sh\"",
            "timeout": 300
          }
        ]
      }
    ],
    "Stop": [
      {
        "hooks": [
          {
            "type": "command",
            "command": "bash \"$CLAUDE_PROJECT_DIR/.claude/hooks/codex-code-review-hook.sh\"",
            "timeout": 180
          }
        ]
      }
    ]
  }
}
```

**Таймауты:**
- SessionStart: 5 сек (просто rm файлов)
- PostToolUse: 300 сек (5 мин — Codex думает 30с-4мин)
- Stop: 180 сек (3 мин — ревью git diff)

### 4.2 Формат вывода Codex

Замечания:
```
[CRITICAL] Description - Suggestion
[HIGH] Description - Suggestion
[MEDIUM] Description - Suggestion
[LOW] Description - Suggestion
```

Одобрение:
```
NO_FINDINGS: Plan approved.
```

### 4.3 Файл результата `.codex-review-result.md`

Создаётся автоматически хуком. Формат:
```markdown
# Codex Review Result

**File:** plan-name.md
**Time:** 2026-02-26 11:48:30
**Session:** 019c970c-7dad-...

## Status: APPROVED / CRITICAL/HIGH ISSUES FOUND / FINDINGS TO REVIEW

## Findings

[HIGH] ...
[MEDIUM] ...
```

---

## 5. Реальный пример работы

### Цикл ревью code-quality-review-plan.md (2026-02-26)

```
Раунд 1 (v3.1): Codex нашёл 3 HIGH + 3 MEDIUM
  - HIGH: bare except count не совпадает с таблицей
  - HIGH: паттерн except Exception слишком мягкий для high-risk
  - HIGH: рефакторинг раньше тестов
  - MEDIUM: декоратор подписки уже существует
  - MEDIUM: CI workflow несогласованность
  - MEDIUM: нет задач по security/performance
  → Claude принял все 6, исправил план (v4)

Раунд 2 (v4): Codex нашёл 1 HIGH + 2 MEDIUM + 1 LOW
  - HIGH: числа bare except всё ещё не синхронизированы
  - MEDIUM: формулировка проблемы не обновлена
  - MEDIUM: оценка безопасности устарела
  - LOW: текст ревью неточен
  → Claude принял все 4, исправил план (v4.1)

Раунд 3 (v4.1): NO_FINDINGS ✅ APPROVED
  Итого: 3 раунда, ~10 мин автономной работы
```

---

## 6. Практические паттерны

### 6.1 Разделение задач по типу

| Тип задачи | Лучший инструмент | Почему |
|---|---|---|
| Архитектура, планирование | Claude Code (Opus) | Глубокий анализ, длинный контекст |
| Массовый рефакторинг | Codex (облако) | Параллельные задачи, автономность |
| Code review | Codex exec (через hooks) | Автоматизируется без UI |
| Быстрые правки | Claude Code (Sonnet) | Скорость, итеративность |
| Security audit | Codex + Snyk/Semgrep | Автоматические сканы |

### 6.2 Параллелизация

**Read-heavy (исследование) — параллелить смело:**
- Анализ разных модулей
- Поиск паттернов в коде

**Write-heavy (правки) — осторожно:**
- Разные файлы → можно параллелить (git worktrees)
- Один файл → только последовательно

### 6.3 Шаблон плана (*-plan.md)

```markdown
# Implementation Plan: [Название задачи]

## Задача
[Описание что нужно сделать]

## Acceptance Criteria
- [ ] Критерий 1
- [ ] Критерий 2
- [ ] Тесты проходят
- [ ] Нет security issues

## Архитектурные решения
[Какие подходы выбраны и почему]

## План реализации
1. Шаг 1: [описание] → файлы: [список]
2. Шаг 2: [описание] → файлы: [список]

## Ревью Codex (заполняется автоматически)
### Раунд 1
- **Reviewer:** Codex
- **Findings:** ...
- **Status:** resolved / open

## Статус
- [x] Draft
- [ ] Reviewed (Codex APPROVED)
- [ ] Implementing
- [ ] Done
```

---

## 7. Дополнительные инструменты

### 7.1 Codex GitHub Action для PR

```yaml
# .github/workflows/codex-review.yml
name: Codex Code Review
on:
  pull_request:
    types: [opened, synchronize]
jobs:
  review:
    runs-on: ubuntu-latest
    steps:
      - uses: openai/codex-action@v1
        with:
          review: true
```

### 7.2 Альтернативные инструменты мультимодельной работы

| Инструмент | Что делает | Ссылка |
|---|---|---|
| CodeMoot | Claude + Codex без copy-paste | https://github.com/katarmal-ram/codemoot |
| Aider | Architect/Editor mode (две модели) | https://aider.chat |
| Claude-Flow | 64 агента, оркестрация | https://github.com/ruvnet/claude-flow |
| GitHub Agent HQ | Claude + Codex в одном PR | https://github.blog/news-insights/company-news/pick-your-agent-use-claude-and-codex-on-agent-hq/ |

---

## 8. Источники

### Документация
- Claude Code hooks: https://code.claude.com/docs/en/hooks
- Codex CLI: https://developers.openai.com/codex/workflows
- Codex non-interactive: https://developers.openai.com/codex/noninteractive

### Статьи
- Simon Willison: Parallel coding agents — https://simonwillison.net/2025/Oct/5/parallel-coding-agents/
- Builder.io: Codex vs Claude Code — https://www.builder.io/blog/codex-vs-claude-code
