"""
Family budget (household) services
"""
from __future__ import annotations

from asgiref.sync import sync_to_async
from datetime import timedelta
from django.utils import timezone
from django.db import transaction
from secrets import token_urlsafe
from typing import Optional

from expenses.models import Profile, Household, FamilyInvite


@sync_to_async
def get_or_create_household_for_user(telegram_id: int) -> Household:
    profile = Profile.objects.get(telegram_id=telegram_id)
    if profile.household_id:
        return profile.household
    with transaction.atomic():
        hh = Household.objects.create()
        profile.household = hh
        profile.save(update_fields=["household"])
        return hh


@sync_to_async
def generate_family_invite(telegram_id: int, ttl_hours: int = 168) -> FamilyInvite:
    """Generate or refresh a family invite token for user's household.
    ttl_hours default 7 days.
    """
    profile = Profile.objects.get(telegram_id=telegram_id)
    if not profile.household_id:
        # create household on first invite
        hh = Household.objects.create()
        profile.household = hh
        profile.save(update_fields=["household"])
    else:
        hh = profile.household

    # create a fresh token every time
    token = token_urlsafe(24)
    invite = FamilyInvite.objects.create(
        inviter=profile,
        household=hh,
        token=token,
        expires_at=timezone.now() + timedelta(hours=ttl_hours),
        is_active=True,
    )
    return invite


@sync_to_async
def get_invite_by_token(token: str) -> Optional[FamilyInvite]:
    try:
        inv = FamilyInvite.objects.select_related("inviter", "household").get(token=token)
        return inv
    except FamilyInvite.DoesNotExist:
        return None


@sync_to_async
def accept_invite(joiner_telegram_id: int, token: str) -> tuple[bool, str]:
    """Accept family invite.
    Returns (success, message_key)
    message_key examples: 'ok', 'invalid', 'already_in_same', 'moved_from_old'
    """
    try:
        invite = FamilyInvite.objects.select_related("inviter", "household").get(token=token)
    except FamilyInvite.DoesNotExist:
        return False, 'invalid'

    if not invite.is_valid():
        return False, 'invalid'

    joiner = Profile.objects.get(telegram_id=joiner_telegram_id)
    target_hh = invite.household

    # Check capacity before joining
    if not target_hh.is_active or target_hh.profiles.count() >= target_hh.max_members:
        return False, 'full'

    if joiner.household_id == target_hh.id:
        return False, 'already_in_same'

    with transaction.atomic():
        # Move joiner to target household
        joiner.household = target_hh
        joiner.save(update_fields=["household"])
        # we keep invite active for reuse (multiple members may join)
    return True, 'ok'
