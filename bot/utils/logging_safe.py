"""
Privacy-safe helpers for application logs.
"""
from __future__ import annotations

import hashlib


def log_safe_id(value: object, label: str = "id") -> str:
    """Return a stable non-reversible identifier for logs."""
    if value is None:
        return f"{label}:unknown"

    digest = hashlib.sha256(str(value).encode("utf-8")).hexdigest()[:8]
    return f"{label}:{digest}"


def summarize_text(text: str | None) -> str:
    """Return non-sensitive text metadata for logs."""
    if not text:
        return "len=0"

    flags = []
    if any(char.isdigit() for char in text):
        flags.append("digits")
    if text.startswith("/"):
        flags.append("command")

    suffix = f", flags={','.join(flags)}" if flags else ""
    return f"len={len(text)}{suffix}"


def sanitize_callback_action(callback_data: str | None) -> tuple[str, bool]:
    """Extract a stable action name without leaking callback params/tokens."""
    if not callback_data:
        return "", False

    if ":" in callback_data:
        action, _ = callback_data.split(":", 1)
        return action, True

    parts = callback_data.split("_")
    param_start_idx = len(parts)
    for index in range(len(parts) - 1, -1, -1):
        if parts[index].isdigit():
            param_start_idx = index
        else:
            break

    if param_start_idx < len(parts):
        return "_".join(parts[:param_start_idx]), True

    return callback_data, False
