#!/bin/bash
# Hook: cleanup Codex sessions on new Claude Code session
# Ensures each new task starts with a fresh Codex context

INPUT=$(cat)
PROJECT_ROOT=$(echo "$INPUT" | jq -r '.cwd // empty')
if [ -z "$PROJECT_ROOT" ]; then
    exit 0
fi

# Remove old session files so next Codex call starts fresh
rm -f "$PROJECT_ROOT/.codex-plan-session" "$PROJECT_ROOT/.codex-code-session" 2>/dev/null

exit 0
