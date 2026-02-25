# Vibe Coding Workflow: Claude Code + Codex

> Дата создания: 2026-02-26
> Последнее обновление: 2026-02-26
> Источники: исследование Claude Code, рекомендации Codex 5.3, документация Anthropic/OpenAI

---

## 1. Проблема текущего workflow

**Было:**
```
Claude Code (план) → ручное копирование → Codex (ревью) → ручное копирование →
Claude Code (правки) → снова копирование → ... → реализация → снова копирование → ...
```

**Bottleneck:** Ручной copy-paste между моделями. Каждый цикл ревью = 2-3 минуты ручной работы.

---

## 2. Целевой workflow

### 2.1 Единый источник правды

Вместо копирования из чатов — **файл плана** (`*-plan.md`) в корне проекта. Название любое, главное чтобы содержало `plan` и расширение `.md`:

```
refactoring-categories-plan.md
cashback-optimization-plan.md
new-feature-plan.md
```

Обе модели работают с этим файлом. Не нужно копировать контекст — он уже в проекте.

### 2.2 Автоматизированный цикл (РЕАЛИЗОВАНО)

```
1. Ты задаёшь задачу + acceptance criteria
2. Claude Code готовит план в *-plan.md
3. → HOOK: Codex автоматически ревьюит план (PostToolUse)
4. Claude Code видит замечания, анализирует, правит план
5. → HOOK: Codex снова ревьюит (resume той же сессии — помнит контекст)
6. Автоциклы пока не будет "NO_FINDINGS"
7. Параллельная реализация через субагентов
8. → HOOK: Codex автоматически ревьюит весь код (Stop hook, git diff)
9. Claude Code исправляет замечания к коду
10. Merge
```

**Пользователь участвует только в:** задании задачи (шаг 1) и финальном одобрении.

---

## 3. Реализованная система автоматизации (hooks)

### 3.1 Архитектура

Система состоит из трёх hooks и Codex CLI:

| Hook | Событие | Скрипт | Что делает |
|---|---|---|---|
| **SessionStart** | Новая сессия Claude | `codex-session-cleanup.sh` | Чистит session-файлы для свежего контекста |
| **PostToolUse** | Write/Edit `*plan*.md` | `codex-review-hook.sh` | Codex ревьюит план |
| **Stop** | Claude завершает работу | `codex-code-review-hook.sh` | Codex ревьюит весь git diff |

### 3.2 Конфигурация: `.claude/settings.json`

```json
{
  "hooks": {
    "SessionStart": [
      {
        "matcher": "startup",
        "hooks": [
          {
            "type": "command",
            "command": "bash \"$CLAUDE_PROJECT_DIR/scripts/codex-session-cleanup.sh\"",
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
            "command": "bash \"$CLAUDE_PROJECT_DIR/scripts/codex-review-hook.sh\"",
            "timeout": 120
          }
        ]
      }
    ],
    "Stop": [
      {
        "hooks": [
          {
            "type": "command",
            "command": "bash \"$CLAUDE_PROJECT_DIR/scripts/codex-code-review-hook.sh\"",
            "timeout": 180
          }
        ]
      }
    ]
  }
}
```

### 3.3 Управление сессиями Codex

Ключевая особенность — **Codex сохраняет контекст между вызовами**:

1. Первый вызов (ревью плана) → Codex создаёт сессию → `thread_id` сохраняется в `.codex-plan-session`
2. Claude правит план → hook вызывает `codex exec resume <session_id>` → Codex **помнит** свои предыдущие замечания
3. Stop hook (ревью кода) → resume **той же сессии плана** → Codex знает план, замечания и теперь видит код
4. Code review session сохраняется в `.codex-code-session`

**Новая задача** (новая сессия Claude): `SessionStart` hook удаляет session-файлы → Codex начинает с чистого листа.

**Resume сессии Claude**: `SessionStart` НЕ срабатывает (matcher `startup`, не `resume`) → Codex продолжает ту же сессию.

### 3.4 Файлы скриптов

Все скрипты в `scripts/`:

| Файл | Назначение |
|---|---|
| `scripts/codex-session-cleanup.sh` | Очистка session-файлов при старте |
| `scripts/codex-review-hook.sh` | Ревью файлов планов (`*plan*.md`) |
| `scripts/codex-code-review-hook.sh` | Ревью кода (git diff) при Stop |

Session-файлы (в `.gitignore`):
- `.codex-plan-session` — ID сессии ревью плана
- `.codex-code-session` — ID сессии ревью кода

### 3.5 Конфигурация Codex CLI

Файл `~/.codex/config.toml`:
```toml
model = "gpt-5.3-codex"
model_reasoning_effort = "high"
personality = "pragmatic"
```

Авторизация через аккаунт OpenAI: `codex login` (без API-ключа).

### 3.6 Формат вывода Codex для Claude

Hook возвращает stdout в контекст Claude. Формат замечаний:

```
[CRITICAL] Description - Suggestion
[HIGH] Description - Suggestion
[MEDIUM] Description - Suggestion
[LOW] Description - Suggestion
```

Или при отсутствии проблем:
```
NO_FINDINGS: Plan approved. / Code review passed.
```

В конце вывода — инструкция для Claude:
```
>>> Claude: Codex found CRITICAL/HIGH issues. Analyze each and fix the plan.
>>> Claude: Plan passed Codex review. Ready to implement.
>>> Claude: Code passed Codex review. All clean.
```

---

## 4. Дополнительные инструменты автоматизации

### 4.1 Codex GitHub Action для PR

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
          # Автоматические комментарии к PR
```

### 4.2 MCP как общий слой

И Claude Code, и Codex поддерживают MCP. Настроить общие MCP серверы:

```json
// .claude/mcp.json (или аналог для Codex)
{
  "servers": {
    "project-context": {
      "command": "npx",
      "args": ["-y", "@anthropic/mcp-server-filesystem", "/path/to/project"]
    },
    "postgres": {
      "command": "npx",
      "args": ["-y", "@anthropic/mcp-server-postgres", "postgresql://..."]
    }
  }
}
```

Обе модели получают одинаковый доступ к проекту и БД.

### 4.3 AGENTS.md для Codex

Codex поддерживает иерархию инструкций через `AGENTS.md`:

```markdown
<!-- AGENTS.md в корне проекта -->
# Agent Instructions

## Роль: Code Reviewer
- Проверяй безопасность (OWASP Top 10)
- Проверяй обработку ошибок
- Проверяй типизацию
- Формат замечаний: severity (critical/high/medium/low) + описание + предложение

## Роль: Implementer
- Следуй CLAUDE.md для стиля кода
- Всегда заполняй мультиязычные поля моделей
- Валидируй FK перед присвоением
```

---

## 5. Готовые решения для мультимодельной работы

### 5.1 CodeMoot (Claude + Codex без copy-paste)

```bash
pip install codemoot

codemoot review    # Codex ревьюит код Claude
codemoot fix       # Автоцикл: ревью → фикс → повторный ревью
codemoot debate    # Дискуссия между моделями по архитектуре
```

GitHub: https://github.com/katarmal-ram/codemoot

### 5.2 Aider (Architect/Editor mode)

```bash
pip install aider-chat

# Claude проектирует, Codex реализует
aider --architect --model claude-opus-4-6 --editor-model gpt-5-codex

# Или наоборот
aider --architect --model gpt-5-codex --editor-model claude-sonnet-4-6
```

Лучшие пары:
- Claude Opus (архитектор) + Codex (редактор)
- DeepSeek R1 (архитектор) + Claude Sonnet (редактор)

### 5.3 Claude-Flow (тяжёлая оркестрация)

```bash
# Подключить как MCP сервер к Claude Code
claude mcp add ruflo -- npx -y ruflo@latest mcp start
```

64 специализированных агента, иерархические паттерны, stream-JSON chaining.
GitHub: https://github.com/ruvnet/claude-flow

### 5.4 GitHub Agent HQ

С февраля 2026 — Claude Code и Codex в едином интерфейсе GitHub. Агенты работают в одном PR.

---

## 6. Практические паттерны

### 6.1 Разделение задач по типу

| Тип задачи | Лучший инструмент | Почему |
|---|---|---|
| Архитектура, планирование | Claude Code (Opus) | Глубокий анализ, длинный контекст |
| Массовый рефакторинг | Codex (облако) | Параллельные задачи, автономность |
| Code review | Codex exec / CodeRabbit | Автоматизируется без UI |
| Быстрые правки | Claude Code (Sonnet) | Скорость, итеративность |
| Security audit | Codex + Snyk/Semgrep | Автоматические сканы |

### 6.2 Параллелизация

**Read-heavy задачи (исследование) — параллелить смело:**
- Анализ разных модулей
- Поиск паттернов в коде
- Чтение документации

**Write-heavy задачи (правки) — осторожно:**
- Разные файлы → можно параллелить (git worktrees)
- Один файл → только последовательно
- Связанные изменения → последовательно с проверкой

### 6.3 Git Worktrees для параллельных агентов

```bash
# Создать worktree для каждого агента
git worktree add .claude/worktrees/agent-1 -b feature/agent-1
git worktree add .claude/worktrees/agent-2 -b feature/agent-2

# Каждый агент работает в своей копии
# После завершения — merge в основную ветку
```

---

## 7. Шаблон плана (*-plan.md)

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
3. ...

## Ревью (заполняется автоматически)
### Раунд 1
- **Reviewer:** Codex 5.3
- **Severity:** [critical/high/medium/low]
- **Findings:**
  - ...
- **Status:** resolved / open

### Раунд 2
- ...

## Статус
- [x] Draft
- [x] Reviewed
- [ ] Approved
- [ ] Implementing
- [ ] Done
```

---

## 8. Рекомендации Codex 5.3 по улучшению workflow

> Получены из анализа Codex текущей архитектуры процесса (февраль 2026)

1. **Файл плана = единственный источник правды** — не копипаст из чатов, а файл в проекте
2. **Автоматизировать ревью** через `codex exec` в hooks, а не вручную в UI
3. **Авто-ревью PR** через `openai/codex-action@v1` или `/review` локально до коммита
4. **Claude hooks**: автозапуск тестов/линта после правок и блок завершения если критерии не пройдены
5. **MCP и Skills** как общий слой интеграций между инструментами
6. **Разделять read-heavy и write-heavy**: параллелить исследование, осторожно с параллельными правками кода

### Что поддерживается инструментами:

| Возможность | Codex | Claude Code |
|---|---|---|
| Non-interactive режим | `codex exec` + JSON вывод | `claude -p` + `--output-format json` |
| Multi-agent | Экспериментально, роли агентов | Субагенты (Task tool) |
| Инструкции агентам | `AGENTS.md` с иерархией | `CLAUDE.md` |
| Hooks | N/A | PreToolUse/PostToolUse/Stop/SessionStart |
| MCP | Поддерживается | Поддерживается |
| Agent Skills standard | Поддерживается | Поддерживается |

---

## 9. Источники

### Документация инструментов
- Claude Code: hooks — https://code.claude.com/docs/en/hooks
- Claude Code: MCP — https://code.claude.com/docs/en/mcp
- Claude Code: субагенты — https://code.claude.com/docs/en/sub-agents
- Codex: workflows — https://developers.openai.com/codex/workflows
- Codex: multi-agent — https://developers.openai.com/codex/multi-agent
- Codex: non-interactive — https://developers.openai.com/codex/noninteractive
- Codex: AGENTS.md — https://developers.openai.com/codex/guides/agents-md
- Codex: GitHub Action — https://developers.openai.com/codex/github-action
- Codex: MCP — https://developers.openai.com/codex/mcp

### Инструменты
- CodeMoot — https://github.com/katarmal-ram/codemoot
- Claude-Flow — https://github.com/ruvnet/claude-flow
- Aider — https://aider.chat
- GitHub Agent HQ — https://github.blog/news-insights/company-news/pick-your-agent-use-claude-and-codex-on-agent-hq/

### Статьи и исследования
- Simon Willison: Parallel coding agents — https://simonwillison.net/2025/Oct/5/parallel-coding-agents/
- Pragmatic Engineer: Programming by parallel AI agents — https://blog.pragmaticengineer.com/new-trend-programming-by-kicking-off-parallel-ai-agents/
- Softr: 8 vibe coding best practices — https://www.softr.io/blog/vibe-coding-best-practices
- Builder.io: Codex vs Claude Code — https://www.builder.io/blog/codex-vs-claude-code
