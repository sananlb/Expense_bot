#!/bin/bash
INPUT=$(cat)
PROJECT_ROOT=$(echo "$INPUT" | jq -r '.cwd // empty')
if [ -z "$PROJECT_ROOT" ]; then exit 0; fi
REVIEW_FILE="$PROJECT_ROOT/.codex-review-result.md"
if [ ! -f "$REVIEW_FILE" ]; then exit 0; fi
CONTENT=$(cat "$REVIEW_FILE")
if [ -z "$CONTENT" ]; then exit 0; fi
ESCAPED=$(echo "$CONTENT" | jq -Rs .)
if [ -z "$ESCAPED" ] || [ "$ESCAPED" = "null" ]; then exit 0; fi
mv "$REVIEW_FILE" "$REVIEW_FILE.injected"
echo "{\"hookSpecificOutput\":{\"hookEventName\":\"PreToolUse\",\"additionalContext\":$ESCAPED}}"
exit 0
