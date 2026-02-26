#!/bin/bash
# Hook: auto code review via Codex on Stop
# Reviews git diff when Claude finishes work
# Only runs in plan sessions (when .codex-plan-session exists)
# Resumes plan session so Codex has full context
# Exit 2 on CRITICAL/HIGH → blocks stop, forces Claude to fix
# Max 5 iterations — after that, does not block stop

MAX_ITERATIONS=5
DEBUG_LOG="/tmp/codex-hook-debug.log"
log() { echo "$(date '+%Y-%m-%d %H:%M:%S') [code-review] $1" >> "$DEBUG_LOG"; }

INPUT=$(cat)

PROJECT_ROOT=$(echo "$INPUT" | jq -r '.cwd // empty')
if [ -z "$PROJECT_ROOT" ]; then
    PROJECT_ROOT="$(cd "$(dirname "$0")/.." && pwd)"
fi

cd "$PROJECT_ROOT" || exit 0

# Only run in plan sessions (plan was reviewed in this session)
if [ ! -f "$PROJECT_ROOT/.codex-plan-session" ]; then
    log "SKIP: no plan session found, not a plan-based session"
    exit 0
fi

log "TRIGGERED: plan session exists, reviewing code changes"

# Check for code changes FIRST (exclude non-code files: .md, images, backup .sql)
EXCLUDE_PATTERN='\.(md|jpeg|jpg|png|gif|svg)$|backup.*\.sql$|.*_backup_.*\.sql$'
CODE_DIFF=$(git diff --name-only HEAD 2>/dev/null | grep -vE "$EXCLUDE_PATTERN")
STAGED_DIFF=$(git diff --cached --name-only 2>/dev/null | grep -vE "$EXCLUDE_PATTERN")
UNTRACKED=$(git ls-files --others --exclude-standard 2>/dev/null | grep -vE "$EXCLUDE_PATTERN")

ALL_CHANGES=$(printf "%s\n%s\n%s" "$CODE_DIFF" "$STAGED_DIFF" "$UNTRACKED" | sort -u | sed '/^$/d')

if [ -z "$ALL_CHANGES" ]; then
    log "SKIP: no code changes found"
    exit 0
fi

# Increment iteration counter ONLY when there are real changes to review
COUNTER_FILE="$PROJECT_ROOT/.codex-code-review-count"
CURRENT_COUNT=0
if [ -f "$COUNTER_FILE" ]; then
    RAW_COUNT=$(cat "$COUNTER_FILE")
    if [[ "$RAW_COUNT" =~ ^[0-9]+$ ]]; then
        CURRENT_COUNT=$RAW_COUNT
    fi
fi
CURRENT_COUNT=$((CURRENT_COUNT + 1))
echo "$CURRENT_COUNT" > "$COUNTER_FILE"

log "Code review iteration: $CURRENT_COUNT / $MAX_ITERATIONS"

# Check iteration limit
if [ "$CURRENT_COUNT" -gt "$MAX_ITERATIONS" ]; then
    log "MAX_ITERATIONS reached ($MAX_ITERATIONS). Not blocking stop."
    REVIEW_FILE="$PROJECT_ROOT/.codex-review-result.md"
    {
        echo "# Codex Code Review Result"
        echo ""
        echo "**Iteration:** $CURRENT_COUNT / $MAX_ITERATIONS"
        echo "**Time:** $(date '+%Y-%m-%d %H:%M:%S')"
        echo ""
        echo "## Status: MAX_ITERATIONS_REACHED"
        echo ""
        echo "MAX_ITERATIONS: Достигнут лимит в $MAX_ITERATIONS итераций ревью кода."
        echo "Codex больше не вызывается. Сообщи пользователю какие замечания остались нерешёнными."
    } > "$REVIEW_FILE"
    echo "MAX_ITERATIONS: Code review limit ($MAX_ITERATIONS) reached. Report remaining findings to user."
    exit 0
fi

if ! command -v codex &> /dev/null; then
    echo "CODEX_CODE_REVIEW: codex CLI not found"
    exit 0
fi

CHANGED_COUNT=$(echo "$ALL_CHANGES" | wc -l | tr -d ' ')

echo ""
echo "============================================"
echo "CODEX CODE REVIEW: Checking $CHANGED_COUNT changed files..."
echo "============================================"
echo "Files:"
echo "$ALL_CHANGES" | head -20
echo ""

FULL_DIFF=$(git diff HEAD 2>/dev/null; git diff --cached 2>/dev/null)

for f in $UNTRACKED; do
    if [ -f "$f" ]; then
        CONTENT=$(head -200 "$f")
        FULL_DIFF=$(printf "%s\n--- /dev/null\n+++ b/%s\n%s" "$FULL_DIFF" "$f" "$CONTENT")
    fi
done

DIFF_LINES=$(echo "$FULL_DIFF" | wc -l | tr -d ' ')
if [ "$DIFF_LINES" -gt 500 ]; then
    FULL_DIFF=$(echo "$FULL_DIFF" | head -500)
fi

SESSION_FILE="$PROJECT_ROOT/.codex-plan-session"
CODE_SESSION_FILE="$PROJECT_ROOT/.codex-code-session"

REVIEW_PROMPT="You are a senior code reviewer. Review these code changes (git diff).

Changed files: $ALL_CHANGES

Diff:
$FULL_DIFF

Check for:
1. Bugs and logic errors
2. Security vulnerabilities (OWASP Top 10)
3. Missing error handling
4. Performance issues
5. Missing type hints (Python)
6. Inconsistency with project patterns (check CLAUDE.md)
7. Missing database migrations if models changed

For each finding:
[SEVERITY] file:line - Description - Suggestion
Severities: CRITICAL, HIGH, MEDIUM, LOW

If code is solid: NO_FINDINGS: Code review passed.
Be concise and specific."

# Try to resume plan session (so Codex knows the plan context)
# Otherwise resume code session, otherwise start new
if [ -f "$SESSION_FILE" ]; then
    SESSION_ID=$(cat "$SESSION_FILE")
    RAW_OUTPUT=$(codex exec resume "$SESSION_ID" "$REVIEW_PROMPT" \
        --full-auto \
        --json 2>&1)
elif [ -f "$CODE_SESSION_FILE" ]; then
    SESSION_ID=$(cat "$CODE_SESSION_FILE")
    RAW_OUTPUT=$(codex exec resume "$SESSION_ID" "$REVIEW_PROMPT" \
        --full-auto \
        --json 2>&1)
else
    RAW_OUTPUT=$(codex exec \
        --full-auto \
        -C "$PROJECT_ROOT" \
        --json \
        "$REVIEW_PROMPT" 2>&1)
fi

# Save code review session
THREAD_ID=$(echo "$RAW_OUTPUT" | grep '"thread.started"' | jq -r '.thread_id // empty' 2>/dev/null)
if [ -n "$THREAD_ID" ]; then
    echo "$THREAD_ID" > "$CODE_SESSION_FILE"
fi

# Extract agent messages
REVIEW_OUTPUT=$(echo "$RAW_OUTPUT" | grep '"agent_message"' | jq -r '.item.text // empty' 2>/dev/null | tr '\n' '\n')

if [ -z "$REVIEW_OUTPUT" ]; then
    REVIEW_OUTPUT=$(echo "$RAW_OUTPUT" | grep -v '^{' | grep -v '^OpenAI' | grep -v '^---' | grep -v '^$')
fi

# Save review output to file for PreToolUse injection (backup mechanism)
REVIEW_FILE="$PROJECT_ROOT/.codex-review-result.md"
{
    echo "# Codex Code Review Result"
    echo ""
    echo "**Changes:** $CHANGED_COUNT files"
    echo "**Time:** $(date '+%Y-%m-%d %H:%M:%S')"
    echo "**Session:** $(cat "$CODE_SESSION_FILE" 2>/dev/null || echo 'new')"
    echo ""
    if echo "$REVIEW_OUTPUT" | grep -qi "NO_FINDINGS"; then
        echo "## Status: APPROVED"
    elif echo "$REVIEW_OUTPUT" | grep -qi "CRITICAL\|HIGH"; then
        echo "## Status: CRITICAL/HIGH ISSUES FOUND"
    else
        echo "## Status: FINDINGS TO REVIEW"
    fi
    echo ""
    echo "## Findings"
    echo ""
    echo "$REVIEW_OUTPUT"
} > "$REVIEW_FILE"

log "Review saved to: $REVIEW_FILE"

echo "$REVIEW_OUTPUT"
echo ""
echo "============================================"

if echo "$REVIEW_OUTPUT" | grep -qi "CRITICAL\|HIGH"; then
    log "RESULT: CRITICAL/HIGH — blocking stop (exit 2)"
    echo "Codex found CRITICAL/HIGH issues in code. Fix them before finishing." >&2
    exit 2
elif echo "$REVIEW_OUTPUT" | grep -qi "NO_FINDINGS"; then
    log "RESULT: Code approved"
    echo ">>> Code passed Codex review. All clean."
    exit 0
else
    log "RESULT: Findings to review"
    echo ">>> Review Codex findings and fix what is needed."
    exit 0
fi
