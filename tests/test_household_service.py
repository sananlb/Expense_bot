from datetime import date, timedelta
from decimal import Decimal

import pytest
from asgiref.sync import sync_to_async
from django.utils import timezone

from bot.services.household import HouseholdService, get_invite_by_token
from expenses.models import (
    Expense,
    ExpenseCategory,
    FamilyInvite,
    Household,
    Income,
    IncomeCategory,
    Profile,
    Subscription,
    UserSettings,
)


async def _create_profile(profile_data: dict, telegram_id: int, **extra_fields) -> Profile:
    data = {**profile_data, "telegram_id": telegram_id, **extra_fields}
    return await sync_to_async(Profile.objects.create)(**data)


@pytest.mark.asyncio
@pytest.mark.django_db(transaction=True)
async def test_create_household_creates_and_prevents_duplicate_membership(test_profile):
    success, message, household = await sync_to_async(HouseholdService.create_household)(
        test_profile,
        "  Моя семья  ",
    )

    await sync_to_async(test_profile.refresh_from_db)()

    assert success is True
    assert message == "Семейный бюджет успешно создан"
    assert household is not None
    assert household.name == "Моя семья"
    assert test_profile.household_id == household.id

    second_success, second_message, second_household = await sync_to_async(HouseholdService.create_household)(
        test_profile,
        "Другая семья",
    )

    assert second_success is False
    assert second_message == "Вы уже состоите в семейном бюджете"
    assert second_household is None


@pytest.mark.asyncio
@pytest.mark.django_db(transaction=True)
async def test_create_household_validates_name_and_uses_default_name(test_profile):
    short_success, short_message, short_household = await sync_to_async(HouseholdService.create_household)(
        test_profile,
        "ab",
    )

    assert short_success is False
    assert "не менее" in short_message
    assert short_household is None

    success, _, household = await sync_to_async(HouseholdService.create_household)(test_profile)

    assert success is True
    assert household is not None
    assert household.name == f"Семья #{test_profile.telegram_id}"


@pytest.mark.asyncio
@pytest.mark.django_db(transaction=True)
async def test_generate_invite_link_rotates_previous_invites_and_restricts_creator(test_profile, profile_data):
    _, _, household = await sync_to_async(HouseholdService.create_household)(test_profile, "Семья")
    await sync_to_async(test_profile.refresh_from_db)()
    member = await _create_profile(profile_data, 123456790, household=household)

    first_success, first_link = await sync_to_async(HouseholdService.generate_invite_link)(
        test_profile,
        "expense_bot",
    )
    second_success, second_link = await sync_to_async(HouseholdService.generate_invite_link)(
        test_profile,
        "expense_bot",
    )
    member_success, member_message = await sync_to_async(HouseholdService.generate_invite_link)(
        member,
        "expense_bot",
    )

    first_token = first_link.split("family_", 1)[1]
    second_token = second_link.split("family_", 1)[1]
    first_invite = await sync_to_async(FamilyInvite.objects.get)(token=first_token)
    second_invite = await get_invite_by_token(second_token)

    assert first_success is True
    assert second_success is True
    assert first_link.startswith("https://t.me/expense_bot?start=family_")
    assert second_link.startswith("https://t.me/expense_bot?start=family_")
    assert first_token != second_token
    assert first_invite.is_active is False
    assert second_invite is not None
    assert second_invite.is_active is True
    assert second_invite.household_id == household.id
    assert member_success is False
    assert "Только создатель" in member_message


@pytest.mark.asyncio
@pytest.mark.django_db(transaction=True)
async def test_join_household_requires_subscription_and_marks_invite_used(test_profile, profile_data):
    _, _, household = await sync_to_async(HouseholdService.create_household)(test_profile, "Семья")
    await sync_to_async(test_profile.refresh_from_db)()
    joiner = await _create_profile(profile_data, 123456791)
    invite_success, invite_link = await sync_to_async(HouseholdService.generate_invite_link)(
        test_profile,
        "expense_bot",
    )
    token = invite_link.split("family_", 1)[1]

    blocked_success, blocked_message = await sync_to_async(HouseholdService.join_household)(joiner, token)

    await sync_to_async(Subscription.objects.create)(
        profile=joiner,
        type="month",
        payment_method="stars",
        amount=299,
        start_date=timezone.now() - timedelta(days=1),
        end_date=timezone.now() + timedelta(days=3),
        is_active=True,
    )
    join_success, join_message = await sync_to_async(HouseholdService.join_household)(joiner, token)

    invite = await sync_to_async(FamilyInvite.objects.get)(token=token)
    await sync_to_async(joiner.refresh_from_db)()

    assert invite_success is True
    assert blocked_success is False
    assert "активная подписка" in blocked_message
    assert join_success is True
    assert household is not None
    assert join_message == "Вы успешно присоединились к Семья"
    assert joiner.household_id == household.id
    assert invite.is_active is False
    assert invite.used_by_id == joiner.id
    assert invite.used_at is not None


@pytest.mark.asyncio
@pytest.mark.django_db(transaction=True)
async def test_join_household_allows_beta_tester_and_rejects_missing_token(test_profile, profile_data):
    _, _, household = await sync_to_async(HouseholdService.create_household)(test_profile, "Семья")
    await sync_to_async(test_profile.refresh_from_db)()
    joiner = await _create_profile(profile_data, 123456792, is_beta_tester=True)
    invite_success, invite_link = await sync_to_async(HouseholdService.generate_invite_link)(
        test_profile,
        "expense_bot",
    )
    token = invite_link.split("family_", 1)[1]

    missing_success, missing_message = await sync_to_async(HouseholdService.join_household)(joiner, "missing-token")
    join_success, _ = await sync_to_async(HouseholdService.join_household)(joiner, token)

    await sync_to_async(joiner.refresh_from_db)()

    assert invite_success is True
    assert missing_success is False
    assert missing_message == "Приглашение не найдено"
    assert join_success is True
    assert joiner.household_id == household.id


@pytest.mark.asyncio
@pytest.mark.django_db(transaction=True)
async def test_join_household_rejects_user_already_in_other_household(test_profile, profile_data):
    _, _, first_household = await sync_to_async(HouseholdService.create_household)(test_profile, "Семья A")
    await sync_to_async(test_profile.refresh_from_db)()
    inviter_b = await _create_profile(profile_data, 123456797)
    _, _, second_household = await sync_to_async(HouseholdService.create_household)(inviter_b, "Семья B")
    await sync_to_async(inviter_b.refresh_from_db)()
    invite_success, invite_link = await sync_to_async(HouseholdService.generate_invite_link)(
        inviter_b,
        "expense_bot",
    )
    token = invite_link.split("family_", 1)[1]

    success, message = await sync_to_async(HouseholdService.join_household)(test_profile, token)

    await sync_to_async(test_profile.refresh_from_db)()
    invite = await sync_to_async(FamilyInvite.objects.get)(token=token)

    assert invite_success is True
    assert success is False
    assert message == "Вы уже состоите в семейном бюджете"
    assert first_household is not None
    assert second_household is not None
    assert test_profile.household_id == first_household.id
    assert invite.is_active is True
    assert invite.used_by_id is None


@pytest.mark.asyncio
@pytest.mark.django_db(transaction=True)
async def test_leave_household_disbands_creator_household_and_resets_member_settings(test_profile, profile_data):
    _, _, household = await sync_to_async(HouseholdService.create_household)(test_profile, "Семья")
    await sync_to_async(test_profile.refresh_from_db)()
    member = await _create_profile(profile_data, 123456793, household=household)
    await sync_to_async(UserSettings.objects.create)(profile=test_profile, view_scope="household")
    await sync_to_async(UserSettings.objects.create)(profile=member, view_scope="household")
    invite = await sync_to_async(FamilyInvite.objects.create)(
        inviter=test_profile,
        household=household,
        token="invite-token-creator",
        expires_at=timezone.now() + timedelta(hours=48),
        is_active=True,
    )

    success, message = await sync_to_async(HouseholdService.leave_household)(test_profile)

    await sync_to_async(test_profile.refresh_from_db)()
    await sync_to_async(member.refresh_from_db)()
    await sync_to_async(household.refresh_from_db)()
    creator_settings = await sync_to_async(UserSettings.objects.get)(profile=test_profile)
    member_settings = await sync_to_async(UserSettings.objects.get)(profile=member)
    invite = await sync_to_async(FamilyInvite.objects.get)(id=invite.id)

    assert success is True
    assert message == "Домохозяйство 'Семья' расформировано"
    assert test_profile.household_id is None
    assert member.household_id is None
    assert household.is_active is False
    assert creator_settings.view_scope == "personal"
    assert member_settings.view_scope == "personal"
    assert invite.is_active is False


@pytest.mark.asyncio
@pytest.mark.django_db(transaction=True)
async def test_leave_household_detaches_member_without_disbanding_household(test_profile, profile_data):
    _, _, household = await sync_to_async(HouseholdService.create_household)(test_profile, "Семья")
    await sync_to_async(test_profile.refresh_from_db)()
    member = await _create_profile(profile_data, 123456794, household=household)
    await sync_to_async(UserSettings.objects.create)(profile=member, view_scope="household")

    success, message = await sync_to_async(HouseholdService.leave_household)(member)

    await sync_to_async(member.refresh_from_db)()
    await sync_to_async(test_profile.refresh_from_db)()
    await sync_to_async(household.refresh_from_db)()
    member_settings = await sync_to_async(UserSettings.objects.get)(profile=member)

    assert success is True
    assert message == "Вы вышли из Семья"
    assert member.household_id is None
    assert test_profile.household_id == household.id
    assert household.is_active is True
    assert member_settings.view_scope == "personal"


@pytest.mark.asyncio
@pytest.mark.django_db(transaction=True)
async def test_household_queries_return_members_and_filtered_operations(test_profile, profile_data):
    _, _, household = await sync_to_async(HouseholdService.create_household)(test_profile, "Семья")
    await sync_to_async(test_profile.refresh_from_db)()
    member = await _create_profile(profile_data, 123456795, household=household)
    outsider = await _create_profile(profile_data, 123456796)
    member_expense_category = await sync_to_async(ExpenseCategory.objects.create)(
        profile=member,
        name="🚕 Такси",
        name_ru="Такси",
        name_en="Taxi",
        icon="🚕",
        original_language="ru",
    )
    outsider_expense_category = await sync_to_async(ExpenseCategory.objects.create)(
        profile=outsider,
        name="☕ Кофе",
        name_ru="Кофе",
        name_en="Coffee",
        icon="☕",
        original_language="ru",
    )
    member_income_category = await sync_to_async(IncomeCategory.objects.create)(
        profile=member,
        name="💰 Фриланс",
        name_ru="Фриланс",
        name_en="Freelance",
        icon="💰",
        original_language="ru",
    )
    outsider_income_category = await sync_to_async(IncomeCategory.objects.create)(
        profile=outsider,
        name="💵 Подработка",
        name_ru="Подработка",
        name_en="Side gig",
        icon="💵",
        original_language="ru",
    )

    await sync_to_async(Expense.objects.create)(
        profile=test_profile,
        category=member_expense_category,
        amount=Decimal("100.00"),
        currency="RUB",
        description="creator expense",
        expense_date=date.today() - timedelta(days=2),
    )
    current_expense = await sync_to_async(Expense.objects.create)(
        profile=member,
        category=member_expense_category,
        amount=Decimal("200.00"),
        currency="RUB",
        description="member expense",
        expense_date=date.today(),
    )
    await sync_to_async(Expense.objects.create)(
        profile=outsider,
        category=outsider_expense_category,
        amount=Decimal("300.00"),
        currency="RUB",
        description="outsider expense",
        expense_date=date.today(),
    )

    await sync_to_async(Income.objects.create)(
        profile=test_profile,
        category=member_income_category,
        amount=Decimal("1000.00"),
        currency="RUB",
        description="creator income",
        income_date=date.today() - timedelta(days=3),
    )
    current_income = await sync_to_async(Income.objects.create)(
        profile=member,
        category=member_income_category,
        amount=Decimal("2000.00"),
        currency="RUB",
        description="member income",
        income_date=date.today(),
    )
    await sync_to_async(Income.objects.create)(
        profile=outsider,
        category=outsider_income_category,
        amount=Decimal("3000.00"),
        currency="RUB",
        description="outsider income",
        income_date=date.today(),
    )

    members = await sync_to_async(HouseholdService.get_household_members)(household)
    expenses = await sync_to_async(lambda: list(HouseholdService.get_household_expenses(household, start_date=date.today() - timedelta(days=1))))()
    incomes = await sync_to_async(lambda: list(HouseholdService.get_household_incomes(household, start_date=date.today() - timedelta(days=1))))()

    assert {profile.id for profile in members} == {test_profile.id, member.id}
    assert [expense.id for expense in expenses] == [current_expense.id]
    assert [income.id for income in incomes] == [current_income.id]


@pytest.mark.asyncio
@pytest.mark.django_db(transaction=True)
async def test_rename_household_validates_length_and_strips_whitespace(test_profile):
    _, _, household = await sync_to_async(HouseholdService.create_household)(test_profile, "Семья")

    short_success, short_message = await sync_to_async(HouseholdService.rename_household)(household, "ab")
    success, message = await sync_to_async(HouseholdService.rename_household)(household, "  Новый бюджет  ")

    await sync_to_async(household.refresh_from_db)()

    assert short_success is False
    assert "не менее" in short_message
    assert success is True
    assert message == "Название семейного бюджета изменено"
    assert household.name == "Новый бюджет"
