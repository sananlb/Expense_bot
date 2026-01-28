"""
Time helper utilities for timezone-aware operations.

This module provides utilities for working with user timezones,
particularly for determining appropriate notification times.
"""

import logging
import threading
from typing import Optional

import pytz
from django.utils import timezone

logger = logging.getLogger(__name__)

# Constants for notification time window
NOTIFICATION_START_HOUR = 10  # Inclusive (10:00:00)
NOTIFICATION_END_HOUR = 21    # Exclusive (21:00:00)

# Cache for invalid timezones to avoid log spam
_invalid_timezones: set = set()
_invalid_timezones_lock = threading.Lock()


def is_daytime_for_user(timezone_str: Optional[str]) -> bool:
    """
    Check if current time is daytime (notification-friendly) in user's timezone.

    Daytime is defined as 10:00:00 to 20:59:59 (NOTIFICATION_START_HOUR <= hour < NOTIFICATION_END_HOUR).
    Times from 21:00:00 onwards and before 10:00:00 are considered nighttime.

    Args:
        timezone_str: IANA timezone identifier (e.g., 'Europe/Moscow', 'America/New_York').
                     If None, empty, or invalid - fallback to 'UTC'.

    Returns:
        bool: True if current time in user's timezone is between 10:00:00 and 20:59:59,
              False otherwise.

    Examples:
        >>> # User in Moscow (UTC+3) at 14:00 local time
        >>> is_daytime_for_user('Europe/Moscow')  # Assuming it's 11:00 UTC
        True

        >>> # User in Moscow (UTC+3) at 22:00 local time
        >>> is_daytime_for_user('Europe/Moscow')  # Assuming it's 19:00 UTC
        False

        >>> # User with invalid timezone
        >>> is_daytime_for_user('Invalid/Timezone')  # Falls back to UTC
        True  # (assuming UTC time is daytime)

        >>> # User with None timezone
        >>> is_daytime_for_user(None)  # Falls back to UTC
        True  # (assuming UTC time is daytime)

    Notes:
        - Uses Django's timezone.now() for current UTC time
        - Properly handles DST (Daylight Saving Time) transitions via pytz
        - Invalid timezones are logged once per unique invalid value
        - Fallback to UTC ensures function always returns a valid result
    """
    # Handle None, empty, whitespace-only, or non-string timezone
    if not timezone_str:
        timezone_str = 'UTC'
    elif not isinstance(timezone_str, str):
        # Handle corrupt data (non-string values in DB)
        logger.warning(
            f"Non-string timezone value provided: {type(timezone_str).__name__}, "
            f"falling back to UTC"
        )
        timezone_str = 'UTC'
    elif not timezone_str.strip():
        # Handle whitespace-only strings
        timezone_str = 'UTC'
    else:
        timezone_str = timezone_str.strip()

    try:
        # Get current UTC time
        now_utc = timezone.now()

        # Convert to user's timezone
        user_tz = pytz.timezone(timezone_str)
        now_user = now_utc.astimezone(user_tz)

        # Check if hour is in daytime window
        return NOTIFICATION_START_HOUR <= now_user.hour < NOTIFICATION_END_HOUR

    except (pytz.UnknownTimeZoneError, AttributeError, TypeError, ValueError) as e:
        # Log warning only once per invalid timezone to avoid spam (thread-safe)
        with _invalid_timezones_lock:
            if timezone_str not in _invalid_timezones:
                _invalid_timezones.add(timezone_str)
                logger.warning(
                    f"Invalid timezone '{timezone_str}' provided (error: {type(e).__name__}), "
                    f"falling back to UTC. User should update their timezone setting."
                )

        # Fallback to UTC
        now_utc = timezone.now()
        return NOTIFICATION_START_HOUR <= now_utc.hour < NOTIFICATION_END_HOUR
