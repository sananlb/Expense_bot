#!/bin/bash
# Hook: run Codex for arbitrary tasks via .codex-task trigger file
# Usage: write to .codex-task file:
#   PROMPT: your prompt here
#   FILE: optional/path/to/file.py   (optional)
#
# Result is injected into Claude's context via .codex-review-result.md
# (same file read by codex-inject-review.sh PreToolUse hook)

DEBUG_LOG="/tmp/codex-hook-debug.log"
log() { echo "$(date '+%Y-%m-%d %H:%M:%S') [task-runner] $1" >> "$DEBUG_LOG"; }

INPUT=$(cat)
FILE_PATH=$(echo "$INPUT" | jq -r '.tool_input.file_path // empty')

# Only trigger on .codex-task file
if [[ "$FILE_PATH" != *".codex-task" ]]; then
    exit 0
fi

log "TRIGGERED for: $FILE_PATH"

if [ ! -f "$FILE_PATH" ]; then
    log "SKIP: .codex-task not found"
    exit 0
fi

# Skip if file is empty (cleared after previous run)
TASK_CONTENT=$(cat "$FILE_PATH")
if [ -z "$TASK_CONTENT" ]; then
    log "SKIP: .codex-task is empty"
    exit 0
fi

# Check codex CLI availability
export PATH="/opt/homebrew/bin:/usr/local/bin:$PATH"
if ! command -v codex &> /dev/null; then
    echo "CODEX_TASK: codex CLI not found in PATH"
    log "ERROR: codex not found"
    exit 0
fi

PROJECT_ROOT=$(echo "$INPUT" | jq -r '.cwd // empty')
if [ -z "$PROJECT_ROOT" ]; then
    PROJECT_ROOT="$(cd "$(dirname "$0")/../.." && pwd)"
fi

# Parse .codex-task file
PROMPT=$(echo "$TASK_CONTENT" | grep "^PROMPT:" | head -1 | sed 's/^PROMPT:[[:space:]]*//')
TASK_FILE=$(echo "$TASK_CONTENT" | grep "^FILE:" | head -1 | sed 's/^FILE:[[:space:]]*//')

if [ -z "$PROMPT" ]; then
    # No PROMPT: prefix — treat entire file as the prompt
    PROMPT="$TASK_CONTENT"
fi

log "PROMPT: $PROMPT"
[ -n "$TASK_FILE" ] && log "FILE: $TASK_FILE"

echo ""
echo "============================================"
echo "CODEX TASK RUNNER: Starting..."
echo "Prompt: $PROMPT"
[ -n "$TASK_FILE" ] && echo "File: $TASK_FILE"
echo "============================================"
echo ""

# Build full prompt — append file path if given
if [ -n "$TASK_FILE" ] && [ -f "$TASK_FILE" ]; then
    FULL_PROMPT="$PROMPT

Target file: $TASK_FILE"
elif [ -n "$TASK_FILE" ]; then
    FULL_PROMPT="$PROMPT

Note: file '$TASK_FILE' was specified but not found."
else
    FULL_PROMPT="$PROMPT"
fi

RESULT_FILE=$(mktemp)

codex exec \
    -s read-only \
    -C "$PROJECT_ROOT" \
    -o "$RESULT_FILE" \
    "$FULL_PROMPT" > /dev/null 2>&1
CODEX_EXIT=$?

log "Codex finished with exit code: $CODEX_EXIT"

TASK_OUTPUT=$(cat "$RESULT_FILE" 2>/dev/null)
rm -f "$RESULT_FILE"

if [ -z "$TASK_OUTPUT" ]; then
    echo "CODEX_TASK: No output received from Codex (exit code: $CODEX_EXIT)"
    log "ERROR: empty output from codex"
    exit 0
fi

# Save result to .codex-review-result.md
# This is the same file read by codex-inject-review.sh (PreToolUse hook)
# — so result will be injected into Claude's context on the next tool call
REVIEW_FILE="$PROJECT_ROOT/.codex-review-result.md"
{
    echo "# Codex Task Result"
    echo ""
    echo "**Task:** $PROMPT"
    [ -n "$TASK_FILE" ] && echo "**File:** $TASK_FILE"
    echo "**Time:** $(date '+%Y-%m-%d %H:%M:%S')"
    echo ""
    echo "## Result"
    echo ""
    echo "$TASK_OUTPUT"
} > "$REVIEW_FILE"

log "Task result saved to: $REVIEW_FILE"

echo "$TASK_OUTPUT"
echo ""
echo "============================================"
echo ">>> Claude: Codex task complete. Results injected into next context."
echo "============================================"

# Clear the trigger file to prevent re-triggering on next Edit/Write
> "$FILE_PATH"

exit 0
