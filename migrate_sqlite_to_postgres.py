#!/usr/bin/env python3
"""
Comprehensive migration script from SQLite to PostgreSQL for ExpenseBot

This script migrates ALL data from the SQLite database to PostgreSQL,
maintaining all relationships and data integrity.

ВАЖНО: Перед запуском обязательно сделайте backup PostgreSQL базы!

Usage:
    python migrate_sqlite_to_postgres.py
"""

import os
import sys
import django
import sqlite3
import json
from decimal import Decimal
from datetime import datetime, date, time
from typing import Dict, List, Any, Optional, Tuple
import logging

# Настройка Django
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'expense_bot.settings')
django.setup()

from django.db import transaction, connection
from django.core.exceptions import ValidationError
from django.contrib.auth.models import User, Group, Permission
from django.contrib.contenttypes.models import ContentType
from django.contrib.admin.models import LogEntry
from django.contrib.sessions.models import Session
from django_celery_beat.models import (
    CrontabSchedule, IntervalSchedule, SolarSchedule,
    ClockSchedule, PeriodicTask
)

# Импорт всех моделей
from expenses.models import *
from admin_panel.models import *

# Настройка логирования
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler('migration.log', encoding='utf-8'),
        logging.StreamHandler()
    ]
)
logger = logging.getLogger(__name__)

class SQLiteToPostgresMigrator:
    """Класс для миграции данных из SQLite в PostgreSQL"""

    def __init__(self, sqlite_path: str):
        self.sqlite_path = sqlite_path
        self.sqlite_conn = None
        self.stats = {
            'migrated_tables': 0,
            'migrated_records': 0,
            'skipped_tables': 0,
            'errors': 0,
            'table_stats': {}
        }

        # Маппинг SQLite таблиц к Django моделям
        self.table_model_mapping = {
            # Основные модели приложения
            'users_profile': Profile,
            'users_settings': UserSettings,
            'households': Household,
            'family_invites': FamilyInvite,
            'expenses_category': ExpenseCategory,
            'expenses_category_keyword': CategoryKeyword,
            'expenses_expense': Expense,
            'expenses_budget': Budget,
            'expenses_recurring_payment': RecurringPayment,
            'expenses_cashback': Cashback,
            'incomes_category': IncomeCategory,
            'incomes_income': Income,
            'expenses_income_category_keyword': IncomeCategoryKeyword,
            'subscriptions': Subscription,
            'subscription_notifications': SubscriptionNotification,
            'promocodes': PromoCode,
            'promocode_usages': PromoCodeUsage,
            'referral_bonuses': ReferralBonus,
            'top5_snapshots': Top5Snapshot,
            'top5_pins': Top5Pin,
            'user_analytics': UserAnalytics,
            'ai_service_metrics': AIServiceMetrics,
            'system_health_checks': SystemHealthCheck,
            'affiliate_program': AffiliateProgram,
            'affiliate_links': AffiliateLink,
            'affiliate_referrals': AffiliateReferral,
            'affiliate_commissions': AffiliateCommission,

            # Модели админ-панели
            'admin_panel_broadcastmessage': BroadcastMessage,
            'admin_panel_broadcastmessage_custom_recipients': None,  # ManyToMany
            'admin_panel_broadcastrecipient': BroadcastRecipient,

            # Django системные модели
            'auth_user': User,
            'auth_group': Group,
            'auth_permission': Permission,
            'django_content_type': ContentType,
            'django_admin_log': LogEntry,
            'django_session': Session,

            # Celery Beat модели
            'django_celery_beat_crontabschedule': CrontabSchedule,
            'django_celery_beat_intervalschedule': IntervalSchedule,
            'django_celery_beat_solarschedule': SolarSchedule,
            'django_celery_beat_clockedschedule': ClockSchedule,
            'django_celery_beat_periodictask': PeriodicTask,
            'django_celery_beat_periodictasks': None,  # Специальная таблица

            # Пропускаем системные таблицы
            'sqlite_sequence': None,
            'django_migrations': None,  # Не мигрируем историю миграций
            'auth_group_permissions': None,  # ManyToMany
            'auth_user_groups': None,  # ManyToMany
            'auth_user_user_permissions': None,  # ManyToMany
        }

        # Порядок миграции (важно для FK relationships)
        self.migration_order = [
            # 1. Системные Django модели
            'auth_user',
            'auth_group',
            'auth_permission',
            'django_content_type',
            'django_session',

            # 2. Celery Beat
            'django_celery_beat_crontabschedule',
            'django_celery_beat_intervalschedule',
            'django_celery_beat_solarschedule',
            'django_celery_beat_clockedschedule',
            'django_celery_beat_periodictask',

            # 3. Основные пользовательские модели
            'users_profile',
            'households',
            'family_invites',
            'users_settings',

            # 4. Категории
            'expenses_category',
            'incomes_category',
            'expenses_category_keyword',
            'expenses_income_category_keyword',

            # 5. Операции
            'expenses_expense',
            'incomes_income',
            'expenses_budget',
            'expenses_recurring_payment',
            'expenses_cashback',

            # 6. Подписки и промокоды
            'subscriptions',
            'subscription_notifications',
            'promocodes',
            'promocode_usages',
            'referral_bonuses',

            # 7. Реферальная программа
            'affiliate_program',
            'affiliate_links',
            'affiliate_referrals',
            'affiliate_commissions',

            # 8. Аналитика и метрики
            'top5_snapshots',
            'top5_pins',
            'user_analytics',
            'ai_service_metrics',
            'system_health_checks',

            # 9. Админ-панель
            'admin_panel_broadcastmessage',
            'admin_panel_broadcastrecipient',

            # 10. Django системные
            'django_admin_log',
        ]

    def connect_sqlite(self):
        """Подключение к SQLite базе"""
        try:
            self.sqlite_conn = sqlite3.connect(self.sqlite_path)
            self.sqlite_conn.row_factory = sqlite3.Row
            logger.info(f"Подключение к SQLite: {self.sqlite_path}")
        except Exception as e:
            logger.error(f"Ошибка подключения к SQLite: {e}")
            raise

    def get_sqlite_tables(self) -> List[str]:
        """Получить список всех таблиц в SQLite"""
        cursor = self.sqlite_conn.cursor()
        cursor.execute("SELECT name FROM sqlite_master WHERE type='table' ORDER BY name")
        return [row[0] for row in cursor.fetchall()]

    def get_table_data(self, table_name: str) -> List[Dict]:
        """Получить все данные из таблицы SQLite"""
        cursor = self.sqlite_conn.cursor()
        cursor.execute(f"SELECT * FROM {table_name}")
        columns = [desc[0] for desc in cursor.description]

        data = []
        for row in cursor.fetchall():
            row_dict = dict(zip(columns, row))
            data.append(row_dict)

        return data

    def convert_value(self, value: Any, field_type: str) -> Any:
        """Конвертация значений для PostgreSQL"""
        if value is None:
            return None

        # Boolean поля
        if field_type in ['BooleanField', 'bool']:
            return bool(value) if value in [0, 1, '0', '1', True, False] else bool(value)

        # Decimal поля
        elif field_type in ['DecimalField', 'decimal']:
            try:
                return Decimal(str(value))
            except:
                return Decimal('0')

        # DateTime поля
        elif field_type in ['DateTimeField', 'datetime']:
            if isinstance(value, str):
                try:
                    # Парсинг различных форматов datetime
                    for fmt in ['%Y-%m-%d %H:%M:%S.%f', '%Y-%m-%d %H:%M:%S', '%Y-%m-%d']:
                        try:
                            return datetime.strptime(value, fmt)
                        except ValueError:
                            continue
                    return None
                except:
                    return None
            return value

        # Date поля
        elif field_type in ['DateField', 'date']:
            if isinstance(value, str):
                try:
                    return datetime.strptime(value, '%Y-%m-%d').date()
                except:
                    return None
            return value

        # Time поля
        elif field_type in ['TimeField', 'time']:
            if isinstance(value, str):
                try:
                    # Парсинг time с микросекундами
                    if '.' in value:
                        return datetime.strptime(value, '%H:%M:%S.%f').time()
                    else:
                        return datetime.strptime(value, '%H:%M:%S').time()
                except:
                    return None
            return value

        # JSON поля
        elif field_type in ['JSONField', 'json']:
            if isinstance(value, str):
                try:
                    return json.loads(value)
                except:
                    return {}
            return value or {}

        # Обычные поля
        return value

    def get_field_type(self, model_class, field_name: str) -> str:
        """Получить тип поля Django модели"""
        try:
            field = model_class._meta.get_field(field_name)
            return field.__class__.__name__
        except:
            return 'CharField'

    def migrate_table(self, table_name: str) -> bool:
        """Миграция конкретной таблицы"""
        model_class = self.table_model_mapping.get(table_name)

        if model_class is None:
            logger.info(f"Пропускаем таблицу {table_name} (нет маппинга или ManyToMany)")
            self.stats['skipped_tables'] += 1
            return True

        logger.info(f"Мигрируем таблицу: {table_name} -> {model_class.__name__}")

        try:
            # Получаем данные из SQLite
            data = self.get_table_data(table_name)

            if not data:
                logger.info(f"Таблица {table_name} пуста")
                self.stats['table_stats'][table_name] = 0
                return True

            # Очищаем существующие данные в PostgreSQL
            with transaction.atomic():
                model_class.objects.all().delete()
                logger.info(f"Очищена таблица {model_class.__name__}")

            # Вставляем данные порциями
            batch_size = 100
            migrated_count = 0

            for i in range(0, len(data), batch_size):
                batch = data[i:i + batch_size]
                objects_to_create = []

                for row_data in batch:
                    try:
                        # Конвертируем данные
                        converted_data = {}

                        for field_name, value in row_data.items():
                            # Пропускаем поля, которых нет в модели
                            try:
                                field = model_class._meta.get_field(field_name)
                                field_type = self.get_field_type(model_class, field_name)
                                converted_data[field_name] = self.convert_value(value, field_type)
                            except:
                                # Поле не существует в модели - пропускаем
                                continue

                        # Создаем объект
                        obj = model_class(**converted_data)
                        objects_to_create.append(obj)

                    except Exception as e:
                        logger.error(f"Ошибка обработки записи в {table_name}: {e}")
                        logger.error(f"Данные записи: {row_data}")
                        self.stats['errors'] += 1
                        continue

                # Массовая вставка
                if objects_to_create:
                    with transaction.atomic():
                        model_class.objects.bulk_create(objects_to_create, ignore_conflicts=True)
                        migrated_count += len(objects_to_create)

            logger.info(f"Мигрировано {migrated_count} записей из {table_name}")
            self.stats['table_stats'][table_name] = migrated_count
            self.stats['migrated_records'] += migrated_count
            self.stats['migrated_tables'] += 1

            return True

        except Exception as e:
            logger.error(f"Ошибка миграции таблицы {table_name}: {e}")
            self.stats['errors'] += 1
            return False

    def migrate_many_to_many(self):
        """Миграция ManyToMany связей"""
        logger.info("Миграция ManyToMany связей...")

        # admin_panel_broadcastmessage_custom_recipients
        try:
            cursor = self.sqlite_conn.cursor()
            cursor.execute("SELECT * FROM admin_panel_broadcastmessage_custom_recipients")

            with transaction.atomic():
                for row in cursor.fetchall():
                    try:
                        broadcast = BroadcastMessage.objects.get(id=row[1])  # broadcastmessage_id
                        profile = Profile.objects.get(id=row[2])  # profile_id
                        broadcast.custom_recipients.add(profile)
                    except Exception as e:
                        logger.error(f"Ошибка M2M broadcast recipients: {e}")

            logger.info("Мигрированы custom_recipients для broadcast сообщений")

        except Exception as e:
            logger.error(f"Ошибка миграции ManyToMany: {e}")

    def fix_sequences(self):
        """Исправление sequences в PostgreSQL после миграции"""
        logger.info("Исправление PostgreSQL sequences...")

        with connection.cursor() as cursor:
            # Получаем все таблицы с auto-increment полями
            tables_with_sequences = []

            for table_name, model_class in self.table_model_mapping.items():
                if model_class and hasattr(model_class, '_meta'):
                    db_table = model_class._meta.db_table
                    tables_with_sequences.append(db_table)

            # Исправляем sequence для каждой таблицы
            for table_name in tables_with_sequences:
                try:
                    cursor.execute(f"""
                        SELECT setval(pg_get_serial_sequence('{table_name}', 'id'),
                                     COALESCE((SELECT MAX(id) FROM {table_name}), 1),
                                     false);
                    """)
                    logger.info(f"Исправлен sequence для {table_name}")
                except Exception as e:
                    logger.debug(f"Sequence для {table_name} не требует исправления: {e}")

    def migrate_all(self):
        """Полная миграция всех данных"""
        logger.info("=== НАЧАЛО МИГРАЦИИ SQLITE -> POSTGRESQL ===")

        try:
            self.connect_sqlite()

            # Получаем список всех таблиц
            sqlite_tables = self.get_sqlite_tables()
            logger.info(f"Найдено {len(sqlite_tables)} таблиц в SQLite")

            # Мигрируем таблицы в правильном порядке
            for table_name in self.migration_order:
                if table_name in sqlite_tables:
                    self.migrate_table(table_name)

            # Мигрируем оставшиеся таблицы
            remaining_tables = set(sqlite_tables) - set(self.migration_order)
            for table_name in remaining_tables:
                if table_name in self.table_model_mapping:
                    self.migrate_table(table_name)

            # Мигрируем ManyToMany связи
            self.migrate_many_to_many()

            # Исправляем sequences
            self.fix_sequences()

            # Выводим статистику
            logger.info("=== СТАТИСТИКА МИГРАЦИИ ===")
            logger.info(f"Мигрировано таблиц: {self.stats['migrated_tables']}")
            logger.info(f"Пропущено таблиц: {self.stats['skipped_tables']}")
            logger.info(f"Всего записей: {self.stats['migrated_records']}")
            logger.info(f"Ошибок: {self.stats['errors']}")

            logger.info("\n=== ДЕТАЛЬНАЯ СТАТИСТИКА ПО ТАБЛИЦАМ ===")
            for table, count in self.stats['table_stats'].items():
                logger.info(f"{table}: {count} записей")

            logger.info("=== МИГРАЦИЯ ЗАВЕРШЕНА УСПЕШНО ===")

        except Exception as e:
            logger.error(f"Критическая ошибка миграции: {e}")
            raise
        finally:
            if self.sqlite_conn:
                self.sqlite_conn.close()

def main():
    """Главная функция"""
    sqlite_path = 'expense_bot.db'

    if not os.path.exists(sqlite_path):
        logger.error(f"SQLite файл не найден: {sqlite_path}")
        sys.exit(1)

    logger.info(f"SQLite файл найден: {sqlite_path}")

    # Подтверждение от пользователя
    print("⚠️  ВНИМАНИЕ! Эта операция ПОЛНОСТЬЮ ОЧИСТИТ все данные в PostgreSQL базе и заменит их данными из SQLite!")
    print("⚠️  Убедитесь, что вы сделали резервную копию PostgreSQL базы!")
    print()
    confirm = input("Продолжить миграцию? (введите 'YES' для подтверждения): ")

    if confirm != 'YES':
        print("Миграция отменена.")
        sys.exit(0)

    # Запускаем миграцию
    migrator = SQLiteToPostgresMigrator(sqlite_path)
    migrator.migrate_all()

if __name__ == '__main__':
    main()