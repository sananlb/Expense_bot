from typing import Optional


def extract_leading_bot_mention_payload(
    text: str,
    bot_username: Optional[str],
) -> Optional[str]:
    """Return text after a leading ``@bot_username``, or ``None`` if it is not ours."""
    if not bot_username or not text.startswith("@"):
        return None

    parts = text.split(maxsplit=1)
    mention = parts[0][1:]
    if mention.lower() != bot_username.lower():
        return None

    return parts[1].strip() if len(parts) > 1 else ""
