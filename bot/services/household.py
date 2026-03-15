"""
Сервис для работы с семейным бюджетом (домохозяйствами)
"""
from typing import Optional, List, Tuple
from datetime import timedelta
from django.utils import timezone
from django.db import transaction
from expenses.models import Profile, Household, FamilyInvite, Expense, Income
import logging
from bot.utils.logging_safe import log_safe_id

logger = logging.getLogger(__name__)

# Константы
INVITE_EXPIRY_HOURS = 48
MAX_HOUSEHOLD_MEMBERS = 5
MIN_HOUSEHOLD_NAME_LENGTH = 3
MAX_HOUSEHOLD_NAME_LENGTH = 50


# Вспомогательные async-функции
from asgiref.sync import sync_to_async


@sync_to_async
def get_invite_by_token(token: str) -> Optional[FamilyInvite]:
    """Получение приглашения по токену"""
    try:
        return FamilyInvite.objects.select_related("inviter", "household").get(token=token)
    except FamilyInvite.DoesNotExist:
        return None


class HouseholdService:
    """Сервис для управления семейными бюджетами"""
    
    @staticmethod
    @transaction.atomic
    def create_household(profile: Profile, name: Optional[str] = None) -> Tuple[bool, str, Optional[Household]]:
        """
        Создание нового домохозяйства
        
        Args:
            profile: Профиль создателя
            name: Название домохозяйства
            
        Returns:
            Tuple[успех, сообщение, домохозяйство]
        """
        try:
            # Блокируем профиль для предотвращения race condition
            # (два одновременных запроса могут создать два household)
            profile = Profile.objects.select_for_update().get(id=profile.id)

            # Проверяем, не состоит ли пользователь уже в домохозяйстве
            if profile.household:
                return False, "Вы уже состоите в семейном бюджете", None

            # Валидация названия
            if name:
                name = name.strip()
                if len(name) < MIN_HOUSEHOLD_NAME_LENGTH:
                    return False, f"Название должно быть не менее {MIN_HOUSEHOLD_NAME_LENGTH} символов", None
                if len(name) > MAX_HOUSEHOLD_NAME_LENGTH:
                    return False, f"Название должно быть не более {MAX_HOUSEHOLD_NAME_LENGTH} символов", None
            
            # Создаем домохозяйство
            household = Household.objects.create(
                name=name or f"Семья #{profile.telegram_id}",
                creator=profile,
                is_active=True
            )
            
            # Добавляем создателя в домохозяйство
            profile.household = household
            profile.save()
            
            logger.info("Created household %s by %s", household.id, log_safe_id(profile.telegram_id, "user"))
            return True, "Семейный бюджет успешно создан", household
            
        except Exception as e:
            logger.error("Error creating household: %s", e)
            return False, "Ошибка при создании семейного бюджета", None
    
    @staticmethod
    def generate_invite_link(profile: Profile, bot_username: str) -> Tuple[bool, str]:
        """
        Генерация ссылки-приглашения в домохозяйство
        
        Args:
            profile: Профиль приглашающего
            bot_username: Username бота для формирования ссылки
            
        Returns:
            Tuple[успех, ссылка или сообщение об ошибке]
        """
        try:
            # Проверяем наличие домохозяйства
            if not profile.household:
                return False, "Сначала создайте семейный бюджет"
            
            # Только создатель семьи может приглашать
            if profile.household.creator_id != profile.id:
                return False, "Только создатель семейного бюджета может приглашать участников"
            
            household = profile.household
            
            # Проверяем количество участников
            if not household.can_add_member():
                return False, f"Достигнуто максимальное количество участников ({household.max_members})"
            
            # Деактивируем старые приглашения
            FamilyInvite.objects.filter(
                inviter=profile,
                household=household,
                is_active=True
            ).update(is_active=False)
            
            # Создаем новое приглашение
            invite = FamilyInvite.objects.create(
                inviter=profile,
                household=household,
                token=FamilyInvite.generate_token(),
                expires_at=timezone.now() + timedelta(hours=INVITE_EXPIRY_HOURS),
                is_active=True
            )
            
            # Формируем ссылку
            invite_link = f"https://t.me/{bot_username}?start=family_{invite.token}"
            
            logger.info("Generated invite for household %s by %s", household.id, log_safe_id(profile.telegram_id, "user"))
            return True, invite_link
            
        except Exception as e:
            logger.error("Error generating invite link: %s", e)
            return False, "Ошибка при создании приглашения"
    
    @staticmethod
    @transaction.atomic
    def join_household(profile: Profile, token: str) -> Tuple[bool, str]:
        """
        Присоединение к домохозяйству по токену приглашения
        
        Args:
            profile: Профиль присоединяющегося
            token: Токен приглашения
            
        Returns:
            Tuple[успех, сообщение]
        """
        try:
            # Проверяем, не состоит ли пользователь уже в домохозяйстве
            if profile.household:
                return False, "Вы уже состоите в семейном бюджете"

            # Проверяем наличие активной подписки (включая trial)
            # Бета-тестеры имеют полный доступ
            if not profile.is_beta_tester:
                has_subscription = profile.subscriptions.filter(
                    is_active=True,
                    end_date__gt=timezone.now()
                ).exists()
                if not has_subscription:
                    return False, "Для вступления в семейный бюджет необходима активная подписка"

            # Ищем и блокируем приглашение для предотвращения race condition
            # (два пользователя могут одновременно использовать один токен)
            invite = FamilyInvite.objects.select_for_update().filter(token=token).first()

            if not invite:
                return False, "Приглашение не найдено"

            # Перепроверяем валидность после блокировки
            if not invite.is_valid():
                return False, "Приглашение недействительно или истекло"

            # Блокируем household для предотвращения превышения лимита членов
            household = Household.objects.select_for_update().get(id=invite.household_id)

            # Проверяем количество участников (после блокировки)
            if not household.can_add_member():
                return False, f"В семейном бюджете достигнуто максимальное количество участников"

            # Сначала отмечаем приглашение как использованное (до присоединения!)
            invite.used_by = profile
            invite.used_at = timezone.now()
            invite.is_active = False
            invite.save()

            # Присоединяем к домохозяйству
            profile.household = household
            profile.save()
            
            logger.info("User %s joined household %s", log_safe_id(profile.telegram_id, "user"), household.id)
            
            household_name = household.name or "семейному бюджету"
            return True, f"Вы успешно присоединились к {household_name}"
            
        except Exception as e:
            logger.error("Error joining household: %s", e)
            return False, "Ошибка при присоединении к семейному бюджету"
    
    @staticmethod
    @transaction.atomic
    def leave_household(profile: Profile) -> Tuple[bool, str]:
        """
        Выход из домохозяйства

        Args:
            profile: Профиль пользователя

        Returns:
            Tuple[успех, сообщение]
        """
        try:
            if not profile.household_id:
                return False, "Вы не состоите в семейном бюджете"

            # Блокируем household для предотвращения race condition
            # (новый участник может присоединиться во время расформирования)
            household = Household.objects.select_for_update().get(id=profile.household_id)
            household_name = household.name or "семейного бюджета"

            # Если выходит создатель семьи — расформировываем домохозяйство для всех
            if household.creator_id == profile.id:
                # Сбрасываем view_scope у всех участников перед отвязкой
                from expenses.models import UserSettings
                member_ids = list(Profile.objects.filter(household=household).values_list('id', flat=True))
                UserSettings.objects.filter(profile_id__in=member_ids, view_scope='household').update(view_scope='personal')

                # Отвязываем всех участников
                Profile.objects.filter(household=household).update(household=None)
                # Деактивируем домохозяйство
                household.is_active = False
                household.save()
                # Деактивируем все приглашения
                FamilyInvite.objects.filter(household=household, is_active=True).update(is_active=False)
                logger.info("Household %s disbanded by creator %s", household.id, log_safe_id(profile.telegram_id, "user"))
                return True, f"Домохозяйство '{household_name}' расформировано"

            # Иначе — обычный выход участника
            # Сбрасываем view_scope на personal ПЕРЕД отвязкой (атомарно)
            from expenses.models import UserSettings
            UserSettings.objects.filter(profile=profile, view_scope='household').update(view_scope='personal')

            profile.household = None
            profile.save()

            # Если это был последний участник, деактивируем домохозяйство
            if household.members_count == 0:
                household.is_active = False
                household.save()
                # Деактивируем все приглашения
                FamilyInvite.objects.filter(household=household, is_active=True).update(is_active=False)
                logger.info("Household %s deactivated (no members)", household.id)

            logger.info("User %s left household %s", log_safe_id(profile.telegram_id, "user"), household.id)
            return True, f"Вы вышли из {household_name}"

        except Exception as e:
            logger.error("Error leaving household: %s", e)
            return False, "Ошибка при выходе из семейного бюджета"
    
    @staticmethod
    def get_household_expenses(household: Household, start_date=None, end_date=None) -> List[Expense]:
        """
        Получение расходов домохозяйства
        
        Args:
            household: Домохозяйство
            start_date: Начальная дата
            end_date: Конечная дата
            
        Returns:
            Список расходов
        """
        # Получаем всех участников домохозяйства
        member_ids = household.profiles.values_list('id', flat=True)
        
        # Формируем запрос
        expenses = Expense.objects.filter(profile_id__in=member_ids)

        if start_date:
            expenses = expenses.filter(expense_date__gte=start_date)
        if end_date:
            expenses = expenses.filter(expense_date__lte=end_date)

        return expenses.order_by('-expense_date', '-created_at')
    
    @staticmethod
    def get_household_incomes(household: Household, start_date=None, end_date=None) -> List[Income]:
        """
        Получение доходов домохозяйства
        
        Args:
            household: Домохозяйство
            start_date: Начальная дата
            end_date: Конечная дата
            
        Returns:
            Список доходов
        """
        # Получаем всех участников домохозяйства
        member_ids = household.profiles.values_list('id', flat=True)
        
        # Формируем запрос
        incomes = Income.objects.filter(profile_id__in=member_ids)

        if start_date:
            incomes = incomes.filter(income_date__gte=start_date)
        if end_date:
            incomes = incomes.filter(income_date__lte=end_date)

        return incomes.order_by('-income_date', '-created_at')
    
    @staticmethod
    def get_household_members(household: Household) -> List[Profile]:
        """
        Получение списка участников домохозяйства
        
        Args:
            household: Домохозяйство
            
        Returns:
            Список профилей участников
        """
        return list(household.profiles.all())
    
    @staticmethod
    def rename_household(household: Household, new_name: str) -> Tuple[bool, str]:
        """
        Переименование домохозяйства

        Args:
            household: Домохозяйство
            new_name: Новое название

        Returns:
            Tuple[успех, сообщение]
        """
        try:
            new_name = new_name.strip()

            if len(new_name) < MIN_HOUSEHOLD_NAME_LENGTH:
                return False, f"Название должно быть не менее {MIN_HOUSEHOLD_NAME_LENGTH} символов"
            if len(new_name) > MAX_HOUSEHOLD_NAME_LENGTH:
                return False, f"Название должно быть не более {MAX_HOUSEHOLD_NAME_LENGTH} символов"

            household.name = new_name
            household.save()

            return True, "Название семейного бюджета изменено"

        except Exception as e:
            logger.error(f"Error renaming household: {e}")
            return False, "Ошибка при изменении названия"

    @staticmethod
    def generate_invite_message_text(profile: Profile, lang: str = 'ru') -> str:
        """
        Генерирует красивый текст приглашения для inline mode

        Args:
            profile: Профиль приглашающего
            lang: Код языка ('ru' или 'en')

        Returns:
            Форматированный HTML текст приглашения

        ВАЖНО: НЕ включаем PII (имена, username) для GDPR compliance
        """
        household = profile.household

        if lang == 'ru':
            household_name = household.name or "Семейный бюджет"
            members_count = household.members_count
            max_members = household.max_members

            # Используем только User ID для privacy
            inviter_display = f"User {profile.telegram_id}"

            text = (
                f"🏠 <b>Приглашение в семейный бюджет!</b>\n\n"
                f"{inviter_display} приглашает вас в домохозяйство:\n"
                f"👥 <b>\"{household_name}\"</b>\n"
                f"Участников: {members_count}/{max_members}\n\n"
                f"<b>Вместе вы сможете:</b>\n"
                f"• Видеть расходы всех участников\n"
                f"• Строить отчёты по совместному бюджету\n"
                f"• Анализировать общую статистику\n\n"
                f"👇 Нажмите кнопку ниже, чтобы присоединиться!"
            )
        else:  # en
            household_name = household.name or "Household"
            members_count = household.members_count
            max_members = household.max_members

            # Используем только User ID для privacy
            inviter_display = f"User {profile.telegram_id}"

            text = (
                f"🏠 <b>Household invitation!</b>\n\n"
                f"{inviter_display} invites you to the household:\n"
                f"👥 <b>\"{household_name}\"</b>\n"
                f"Members: {members_count}/{max_members}\n\n"
                f"<b>Together you can:</b>\n"
                f"• See all members' expenses\n"
                f"• Build reports for shared budget\n"
                f"• Analyze combined statistics\n\n"
                f"👇 Click the button below to join!"
            )

        return text
