#!/usr/bin/env bash
# Hook: UserPromptSubmit
# Sends 👀 to Telegram only when message comes from Telegram channel

INPUT=$(cat)

# Log input for debugging
echo "$INPUT" >> /tmp/telegram-ack-debug.log

# Only trigger for messages from Telegram channel
if ! echo "$INPUT" | grep -q 'plugin:telegram:telegram\|source="plugin:telegram'; then
    exit 0
fi

ENV_FILE="${HOME}/.claude/channels/telegram/.env"

if [[ ! -f "$ENV_FILE" ]]; then
    exit 0
fi

source "$ENV_FILE"

if [[ -z "$TELEGRAM_BOT_TOKEN" ]]; then
    exit 0
fi

CHAT_ID="881292737"

curl -sS --max-time 5 \
    "https://api.telegram.org/bot${TELEGRAM_BOT_TOKEN}/sendMessage?chat_id=${CHAT_ID}&text=.&disable_notification=true" > /dev/null 2>&1

exit 0
