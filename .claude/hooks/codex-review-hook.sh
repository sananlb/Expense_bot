#!/bin/bash
# Hook: auto review plan files via Codex CLI
# Triggers on any *plan*.md file
# Maintains session continuity via .codex-plan-session file
# Max 5 iterations per session — after that, skips Codex

MAX_ITERATIONS=5
DEBUG_LOG="/tmp/codex-hook-debug.log"
log() { echo "$(date '+%Y-%m-%d %H:%M:%S') [plan-review] $1" >> "$DEBUG_LOG"; }

INPUT=$(cat)
FILE_PATH=$(echo "$INPUT" | jq -r '.tool_input.file_path // empty')

# Only process plan files
if [[ "$FILE_PATH" != *plan*.md ]] && [[ "$FILE_PATH" != *plan*.MD ]]; then
    exit 0
fi

log "TRIGGERED for: $FILE_PATH"

if [ ! -f "$FILE_PATH" ]; then
    log "SKIP: file not found"
    exit 0
fi

# Check codex CLI availability with PATH fallback
export PATH="/opt/homebrew/bin:/usr/local/bin:$PATH"
if ! command -v codex &> /dev/null; then
    echo "CODEX_REVIEW: codex CLI not found in PATH"
    log "ERROR: codex not found"
    exit 0
fi

PROJECT_ROOT=$(echo "$INPUT" | jq -r '.cwd // empty')
if [ -z "$PROJECT_ROOT" ]; then
    PROJECT_ROOT="$(cd "$(dirname "$0")/../.." && pwd)"
fi

FILENAME=$(basename "$FILE_PATH")
SESSION_FILE="$PROJECT_ROOT/.codex-plan-session"
COUNTER_FILE="$PROJECT_ROOT/.codex-plan-review-count"

# Increment iteration counter (validate as integer)
CURRENT_COUNT=0
if [ -f "$COUNTER_FILE" ]; then
    RAW_COUNT=$(cat "$COUNTER_FILE")
    if [[ "$RAW_COUNT" =~ ^[0-9]+$ ]]; then
        CURRENT_COUNT=$RAW_COUNT
    fi
fi
CURRENT_COUNT=$((CURRENT_COUNT + 1))
echo "$CURRENT_COUNT" > "$COUNTER_FILE"

log "Plan review iteration: $CURRENT_COUNT / $MAX_ITERATIONS"

# Check iteration limit
if [ "$CURRENT_COUNT" -gt "$MAX_ITERATIONS" ]; then
    log "MAX_ITERATIONS reached ($MAX_ITERATIONS). Skipping Codex."
    REVIEW_FILE="$PROJECT_ROOT/.codex-review-result.md"
    {
        echo "# Codex Review Result"
        echo ""
        echo "**File:** $FILENAME"
        echo "**Time:** $(date '+%Y-%m-%d %H:%M:%S')"
        echo "**Iteration:** $CURRENT_COUNT / $MAX_ITERATIONS"
        echo ""
        echo "## Status: MAX_ITERATIONS_REACHED"
        echo ""
        echo "## Findings"
        echo ""
        echo "MAX_ITERATIONS: Достигнут лимит в $MAX_ITERATIONS итераций ревью плана."
        echo "Codex больше не вызывается. Сообщи пользователю какие замечания остались нерешёнными."
    } > "$REVIEW_FILE"
    echo "MAX_ITERATIONS: Plan review limit ($MAX_ITERATIONS) reached. Report remaining findings to user."
    exit 0
fi

echo ""
echo "============================================"
echo "CODEX AUTO-REVIEW: Checking plan ($FILENAME)..."
echo "============================================"
echo ""

PROMPT="You are a senior code reviewer. Read and review the file '$FILE_PATH'.

Check for:
1. Architectural issues and design flaws
2. Missing edge cases and error handling
3. Security concerns
4. Performance implications
5. Missing steps or incomplete sections
6. Contradictions or inconsistencies
7. Whether the plan matches the project existing patterns (check CLAUDE.md for context)

For each finding:
[SEVERITY] Description - Suggestion
Severities: CRITICAL, HIGH, MEDIUM, LOW

If no significant issues: NO_FINDINGS: Plan approved.
Be concise. Do NOT rewrite the plan."

log "Starting codex exec..."

# Check for existing session to resume
if [ -f "$SESSION_FILE" ]; then
    SESSION_ID=$(cat "$SESSION_FILE")
    log "Resuming session: $SESSION_ID"

    RESUME_PROMPT="The plan file '$FILENAME' has been updated since your last review. Please re-review it focusing on whether previous findings were addressed and any new issues.

Re-read the file '$FILE_PATH' and check again.

For each finding:
[SEVERITY] Description - Suggestion
Severities: CRITICAL, HIGH, MEDIUM, LOW

If no significant issues: NO_FINDINGS: Plan approved.
Be concise. Do NOT rewrite the plan."

    RAW_OUTPUT=$(codex exec resume "$SESSION_ID" "$RESUME_PROMPT" \
        --full-auto \
        --json 2>&1)
    CODEX_EXIT=$?
else
    log "New session in: $PROJECT_ROOT"

    RAW_OUTPUT=$(codex exec \
        --full-auto \
        -C "$PROJECT_ROOT" \
        --json \
        "$PROMPT" 2>&1)
    CODEX_EXIT=$?
fi

log "Codex finished with exit code: $CODEX_EXIT"

# Extract and save session/thread id for next resume
THREAD_ID=$(echo "$RAW_OUTPUT" | grep '"thread.started"' | jq -r '.thread_id // empty' 2>/dev/null)
if [ -n "$THREAD_ID" ]; then
    echo "$THREAD_ID" > "$SESSION_FILE"
    log "Saved thread_id: $THREAD_ID"
fi

# Extract agent messages for display
REVIEW_OUTPUT=$(echo "$RAW_OUTPUT" | grep '"agent_message"' | jq -r '.item.text // empty' 2>/dev/null | tr '\n' '\n')

if [ -z "$REVIEW_OUTPUT" ]; then
    # Fallback: show raw output without JSON envelope
    REVIEW_OUTPUT=$(echo "$RAW_OUTPUT" | grep -v '^{' | grep -v '^OpenAI' | grep -v '^---' | grep -v '^$')
fi

if [ -z "$REVIEW_OUTPUT" ]; then
    echo "CODEX_REVIEW: No output received from Codex (exit code: $CODEX_EXIT)"
    log "ERROR: empty output from codex"
    exit 0
fi

# Save review output to file for Claude to read after Edit/Write returns
REVIEW_FILE="$PROJECT_ROOT/.codex-review-result.md"
{
    echo "# Codex Review Result"
    echo ""
    echo "**File:** $FILENAME"
    echo "**Time:** $(date '+%Y-%m-%d %H:%M:%S')"
    echo "**Session:** $(cat "$SESSION_FILE" 2>/dev/null || echo 'new')"
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
    echo ">>> Claude: Codex found CRITICAL/HIGH issues. Analyze each and fix the plan."
    log "RESULT: CRITICAL/HIGH issues found"
elif echo "$REVIEW_OUTPUT" | grep -qi "NO_FINDINGS"; then
    echo ">>> Claude: Plan APPROVED by Codex. STOP and ask user before implementing code."
    log "RESULT: Plan approved"
else
    echo ">>> Claude: Review Codex findings and decide what to address."
    log "RESULT: Findings to review"
fi

exit 0
