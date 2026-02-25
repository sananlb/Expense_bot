#!/bin/bash
# Hook: auto code review via Codex on Stop
# Reviews git diff when Claude finishes work
# Resumes plan session so Codex has full context

INPUT=$(cat)

PROJECT_ROOT=$(echo "$INPUT" | jq -r '.cwd // empty')
if [ -z "$PROJECT_ROOT" ]; then
    PROJECT_ROOT="$(cd "$(dirname "$0")/.." && pwd)"
fi

cd "$PROJECT_ROOT" || exit 0

# Check for code changes (exclude .md files)
CODE_DIFF=$(git diff --name-only HEAD 2>/dev/null | grep -v '\.md$')
STAGED_DIFF=$(git diff --cached --name-only 2>/dev/null | grep -v '\.md$')
UNTRACKED=$(git ls-files --others --exclude-standard 2>/dev/null | grep -v '\.md$')

ALL_CHANGES=$(printf "%s\n%s\n%s" "$CODE_DIFF" "$STAGED_DIFF" "$UNTRACKED" | sort -u | sed '/^$/d')

if [ -z "$ALL_CHANGES" ]; then
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

echo "$REVIEW_OUTPUT"
echo ""
echo "============================================"

if echo "$REVIEW_OUTPUT" | grep -qi "CRITICAL\|HIGH"; then
    echo ">>> Claude: Codex found CRITICAL/HIGH issues. Fix them before finishing."
elif echo "$REVIEW_OUTPUT" | grep -qi "NO_FINDINGS"; then
    echo ">>> Claude: Code passed Codex review. All clean."
else
    echo ">>> Claude: Review Codex findings and fix what is needed."
fi

exit 0
