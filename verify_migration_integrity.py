#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
Проверка целостности данных после миграции категорий
"""

import os
import sys
import django
from pathlib import Path
from collections import Counter
from datetime import datetime, timedelta

# Добавляем корневую директорию проекта в PYTHONPATH
sys.path.insert(0, str(Path(__file__).parent))

# Настройка Django
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'expense_bot.settings')
django.setup()

from expenses.models import Profile, ExpenseCategory, IncomeCategory, Expense, Income, CategoryKeyword
from django.db.models import Count, Q
from django.db import connection


class MigrationIntegrityChecker:
    """Проверка целостности данных после миграции"""
    
    def __init__(self):
        self.report = {
            'timestamp': datetime.now(),
            'total_checks': 0,
            'passed_checks': 0,
            'failed_checks': 0,
            'warnings': 0,
            'critical_issues': 0,
            'issues': []
        }
    
    def add_issue(self, severity: str, category: str, message: str, details: dict = None):
        """Добавить проблему в отчет"""
        issue = {
            'severity': severity,  # 'INFO', 'WARNING', 'ERROR', 'CRITICAL'
            'category': category,
            'message': message,
            'details': details or {},
            'timestamp': datetime.now()
        }
        
        self.report['issues'].append(issue)
        
        if severity == 'WARNING':
            self.report['warnings'] += 1
        elif severity in ['ERROR', 'CRITICAL']:
            self.report['failed_checks'] += 1
            if severity == 'CRITICAL':
                self.report['critical_issues'] += 1
        else:
            self.report['passed_checks'] += 1
        
        # Выводим в консоль
        icon = {'INFO': '✅', 'WARNING': '⚠️', 'ERROR': '❌', 'CRITICAL': '🚨'}[severity]
        print(f"{icon} [{severity}] {category}: {message}")
        if details:
            for key, value in details.items():
                print(f"    {key}: {value}")
    
    def check_database_consistency(self):
        """Проверка консистентности базы данных"""
        print("\n" + "=" * 60)
        print("🔍 ПРОВЕРКА КОНСИСТЕНТНОСТИ БАЗЫ ДАННЫХ")
        print("=" * 60)
        
        # Проверка 1: Все активные категории имеют корректные мультиязычные поля
        print("\n1. Проверка мультиязычных полей категорий расходов...")
        
        empty_multilingual = ExpenseCategory.objects.filter(
            is_active=True
        ).filter(
            (Q(name_ru__isnull=True) | Q(name_ru='')) &
            (Q(name_en__isnull=True) | Q(name_en=''))
        )
        
        if empty_multilingual.exists():
            self.add_issue('ERROR', 'MULTILINGUAL_FIELDS', 
                         f"Найдено {empty_multilingual.count()} активных категорий без мультиязычных полей",
                         {'count': empty_multilingual.count(), 
                          'sample_ids': list(empty_multilingual.values_list('id', flat=True)[:5])})
        else:
            self.add_issue('INFO', 'MULTILINGUAL_FIELDS', 
                         "Все активные категории имеют мультиязычные поля")
        
        # Проверка 2: Синхронизация поля name
        print("2. Проверка синхронизации поля name...")
        
        inconsistent_names = []
        for category in ExpenseCategory.objects.filter(is_active=True):
            if category.name_ru or category.name_en:
                # Получаем ожидаемое название через метод модели
                expected_name = category.get_display_name('ru')  # Используем русский как базовый
                if category.name != expected_name:
                    inconsistent_names.append({
                        'id': category.id, 
                        'current': category.name, 
                        'expected': expected_name
                    })
        
        if inconsistent_names:
            self.add_issue('WARNING', 'NAME_SYNC', 
                         f"Найдено {len(inconsistent_names)} категорий с несинхронизированным полем name",
                         {'count': len(inconsistent_names), 
                          'samples': inconsistent_names[:3]})
        else:
            self.add_issue('INFO', 'NAME_SYNC', 
                         "Все категории имеют синхронизированное поле name")
        
        # Проверка 3: Дубликаты категорий
        print("3. Проверка дубликатов категорий...")
        
        profiles = Profile.objects.all()
        total_duplicates = 0
        
        for profile in profiles:
            categories = profile.categories.filter(is_active=True)
            name_groups = {}
            
            for category in categories:
                # Нормализуем названия для поиска дубликатов
                normalized_names = set()
                
                if category.name_ru:
                    normalized_names.add(category.name_ru.lower().strip())
                if category.name_en:
                    normalized_names.add(category.name_en.lower().strip())
                
                for norm_name in normalized_names:
                    if norm_name:
                        if norm_name not in name_groups:
                            name_groups[norm_name] = []
                        name_groups[norm_name].append(category)
            
            # Подсчитываем дубликаты
            profile_duplicates = 0
            for name, cats in name_groups.items():
                if len(cats) > 1:
                    profile_duplicates += len(cats) - 1
            
            total_duplicates += profile_duplicates
        
        if total_duplicates > 0:
            self.add_issue('WARNING', 'DUPLICATES', 
                         f"Найдено {total_duplicates} потенциальных дубликатов категорий")
        else:
            self.add_issue('INFO', 'DUPLICATES', 
                         "Дубликаты категорий не найдены")
        
        self.report['total_checks'] += 3
    
    def check_expense_category_bindings(self):
        """Проверка привязки расходов к категориям"""
        print("\n" + "=" * 60)
        print("💰 ПРОВЕРКА ПРИВЯЗКИ РАСХОДОВ К КАТЕГОРИЯМ")
        print("=" * 60)
        
        # Проверка 1: Расходы без категории
        print("1. Проверка расходов без категории...")
        
        orphaned_expenses = Expense.objects.filter(category__isnull=True).count()
        recent_orphaned = Expense.objects.filter(
            category__isnull=True,
            created_at__gte=datetime.now() - timedelta(days=30)
        ).count()
        
        if orphaned_expenses > 0:
            severity = 'ERROR' if recent_orphaned > 0 else 'WARNING'
            self.add_issue(severity, 'ORPHANED_EXPENSES', 
                         f"Найдено {orphaned_expenses} расходов без категории",
                         {'total': orphaned_expenses, 'recent': recent_orphaned})
        else:
            self.add_issue('INFO', 'ORPHANED_EXPENSES', 
                         "Все расходы имеют категории")
        
        # Проверка 2: Расходы с неактивными категориями
        print("2. Проверка расходов с неактивными категориями...")
        
        inactive_category_expenses = Expense.objects.filter(
            category__is_active=False
        ).count()
        
        if inactive_category_expenses > 0:
            self.add_issue('ERROR', 'INACTIVE_CATEGORIES', 
                         f"Найдено {inactive_category_expenses} расходов с неактивными категориями")
        else:
            self.add_issue('INFO', 'INACTIVE_CATEGORIES', 
                         "Все расходы привязаны к активным категориям")
        
        # Проверка 3: Распределение расходов по категориям
        print("3. Анализ распределения расходов по категориям...")
        
        category_stats = ExpenseCategory.objects.filter(
            is_active=True
        ).annotate(
            expense_count=Count('expenses')
        ).order_by('-expense_count')
        
        unused_categories = category_stats.filter(expense_count=0).count()
        heavily_used_categories = category_stats.filter(expense_count__gt=1000).count()
        
        if unused_categories > 0:
            self.add_issue('INFO', 'CATEGORY_USAGE', 
                         f"Найдено {unused_categories} неиспользуемых категорий")
        
        self.add_issue('INFO', 'CATEGORY_STATS', 
                     f"Статистика категорий: {category_stats.count()} активных, {heavily_used_categories} активно используемых")
        
        self.report['total_checks'] += 3
    
    def check_keyword_consistency(self):
        """Проверка консистентности ключевых слов"""
        print("\n" + "=" * 60)
        print("🔤 ПРОВЕРКА КЛЮЧЕВЫХ СЛОВ КАТЕГОРИЙ")
        print("=" * 60)
        
        # Проверка 1: Ключевые слова без категорий
        print("1. Проверка ключевых слов без категорий...")
        
        orphaned_keywords = CategoryKeyword.objects.filter(
            category__isnull=True
        ).count()
        
        if orphaned_keywords > 0:
            self.add_issue('ERROR', 'ORPHANED_KEYWORDS', 
                         f"Найдено {orphaned_keywords} ключевых слов без категорий")
        else:
            self.add_issue('INFO', 'ORPHANED_KEYWORDS', 
                         "Все ключевые слова привязаны к категориям")
        
        # Проверка 2: Ключевые слова с неактивными категориями
        print("2. Проверка ключевых слов с неактивными категориями...")
        
        inactive_keywords = CategoryKeyword.objects.filter(
            category__is_active=False
        ).count()
        
        if inactive_keywords > 0:
            self.add_issue('WARNING', 'INACTIVE_KEYWORDS', 
                         f"Найдено {inactive_keywords} ключевых слов для неактивных категорий")
        else:
            self.add_issue('INFO', 'INACTIVE_KEYWORDS', 
                         "Все ключевые слова привязаны к активным категориям")
        
        # Проверка 3: Дубликаты ключевых слов
        print("3. Проверка дубликатов ключевых слов...")
        
        with connection.cursor() as cursor:
            cursor.execute("""
                SELECT keyword, language, COUNT(*) as count
                FROM expenses_category_keyword 
                GROUP BY keyword, language 
                HAVING COUNT(*) > 1
            """)
            
            duplicate_keywords = cursor.fetchall()
        
        if duplicate_keywords:
            total_duplicates = sum(count - 1 for _, _, count in duplicate_keywords)
            self.add_issue('WARNING', 'DUPLICATE_KEYWORDS', 
                         f"Найдено {len(duplicate_keywords)} групп дублированных ключевых слов ({total_duplicates} дубликатов)",
                         {'groups': len(duplicate_keywords), 'total_duplicates': total_duplicates})
        else:
            self.add_issue('INFO', 'DUPLICATE_KEYWORDS', 
                         "Дубликаты ключевых слов не найдены")
        
        self.report['total_checks'] += 3
    
    def check_performance_indicators(self):
        """Проверка показателей производительности"""
        print("\n" + "=" * 60)
        print("⚡ ПРОВЕРКА ПОКАЗАТЕЛЕЙ ПРОИЗВОДИТЕЛЬНОСТИ")
        print("=" * 60)
        
        # Проверка 1: Количество запросов для получения категорий
        print("1. Тестирование производительности запросов...")
        
        import time
        from django.db import reset_queries
        from django import db
        
        # Тест запроса категорий с мультиязычными полями
        reset_queries()
        start_time = time.time()
        
        categories = list(ExpenseCategory.objects.filter(
            is_active=True,
            profile__telegram_id=881292737  # Тестовый пользователь
        ).select_related('profile'))
        
        query_time = time.time() - start_time
        query_count = len(db.connection.queries)
        
        if query_time > 1.0:
            self.add_issue('WARNING', 'QUERY_PERFORMANCE', 
                         f"Запрос категорий выполняется медленно: {query_time:.3f}s",
                         {'time': query_time, 'queries': query_count})
        else:
            self.add_issue('INFO', 'QUERY_PERFORMANCE', 
                         f"Производительность запросов в норме: {query_time:.3f}s")
        
        # Проверка 2: Размер таблиц
        print("2. Проверка размера таблиц...")
        
        category_count = ExpenseCategory.objects.count()
        keyword_count = CategoryKeyword.objects.count()
        expense_count = Expense.objects.count()
        
        self.add_issue('INFO', 'TABLE_SIZES', 
                     f"Размеры таблиц: {category_count} категорий, {keyword_count} ключевых слов, {expense_count} расходов")
        
        # Проверка 3: Индексы
        print("3. Проверка использования индексов...")
        
        with connection.cursor() as cursor:
            # Проверяем план выполнения для типичного запроса
            cursor.execute("""
                EXPLAIN QUERY PLAN
                SELECT * FROM expenses_category 
                WHERE profile_id = 1 AND is_active = 1
            """)
            
            plan = cursor.fetchall()
            uses_index = any('INDEX' in str(row).upper() for row in plan)
            
            if uses_index:
                self.add_issue('INFO', 'INDEX_USAGE', 
                             "Запросы используют индексы")
            else:
                self.add_issue('WARNING', 'INDEX_USAGE', 
                             "Возможны проблемы с использованием индексов")
        
        self.report['total_checks'] += 3
    
    def generate_summary_report(self):
        """Генерация итогового отчета"""
        print("\n" + "=" * 80)
        print("📊 ИТОГОВЫЙ ОТЧЕТ О ЦЕЛОСТНОСТИ ДАННЫХ")
        print("=" * 80)
        
        print(f"🕐 Время проверки: {self.report['timestamp'].strftime('%Y-%m-%d %H:%M:%S')}")
        print(f"📋 Всего проверок: {self.report['total_checks']}")
        print(f"✅ Успешно: {self.report['passed_checks']}")
        print(f"⚠️  Предупреждений: {self.report['warnings']}")
        print(f"❌ Ошибок: {self.report['failed_checks']}")
        print(f"🚨 Критических проблем: {self.report['critical_issues']}")
        
        # Группировка проблем по категориям
        issues_by_category = {}
        issues_by_severity = {'INFO': 0, 'WARNING': 0, 'ERROR': 0, 'CRITICAL': 0}
        
        for issue in self.report['issues']:
            category = issue['category']
            severity = issue['severity']
            
            if category not in issues_by_category:
                issues_by_category[category] = []
            issues_by_category[category].append(issue)
            
            issues_by_severity[severity] += 1
        
        # Рекомендации
        print(f"\n📋 РЕКОМЕНДАЦИИ:")
        
        if self.report['critical_issues'] > 0:
            print("🚨 КРИТИЧНО: Обнаружены критические проблемы! Необходимо немедленное вмешательство.")
        elif self.report['failed_checks'] > 0:
            print("❌ ВАЖНО: Обнаружены ошибки, которые требуют исправления.")
        elif self.report['warnings'] > 0:
            print("⚠️  ВНИМАНИЕ: Обнаружены предупреждения, рекомендуется исправление.")
        else:
            print("✅ ОТЛИЧНО: Все проверки пройдены успешно!")
        
        # Детальные рекомендации по категориям
        if 'MULTILINGUAL_FIELDS' in issues_by_category:
            print("\n🔧 Для исправления мультиязычных полей:")
            print("   python comprehensive_category_migration.py --execute")
        
        if 'DUPLICATES' in issues_by_category:
            print("\n🔧 Для устранения дубликатов:")
            print("   python comprehensive_category_migration.py --execute")
        
        if 'ORPHANED_EXPENSES' in issues_by_category:
            print("\n🔧 Для исправления расходов без категории:")
            print("   python quick_category_fix.py [user_id] fix --execute")
        
        return self.report
    
    def save_report_to_file(self):
        """Сохранение отчета в файл"""
        timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
        filename = f"migration_integrity_report_{timestamp}.json"
        
        import json
        
        # Подготавливаем данные для JSON (даты в строки)
        json_report = self.report.copy()
        json_report['timestamp'] = self.report['timestamp'].isoformat()
        
        for issue in json_report['issues']:
            issue['timestamp'] = issue['timestamp'].isoformat()
        
        with open(filename, 'w', encoding='utf-8') as f:
            json.dump(json_report, f, indent=2, ensure_ascii=False)
        
        print(f"\n💾 Подробный отчет сохранен в файл: {filename}")
        return filename
    
    def run_all_checks(self):
        """Запуск всех проверок"""
        print("🔍 ПРОВЕРКА ЦЕЛОСТНОСТИ ДАННЫХ ПОСЛЕ МИГРАЦИИ КАТЕГОРИЙ")
        print("Начато:", datetime.now().strftime('%Y-%m-%d %H:%M:%S'))
        
        try:
            self.check_database_consistency()
            self.check_expense_category_bindings()
            self.check_keyword_consistency()
            self.check_performance_indicators()
            
            report = self.generate_summary_report()
            filename = self.save_report_to_file()
            
            return report, filename
            
        except Exception as e:
            self.add_issue('CRITICAL', 'SYSTEM_ERROR', 
                         f"Критическая ошибка во время проверки: {str(e)}")
            print(f"\n🚨 КРИТИЧЕСКАЯ ОШИБКА: {e}")
            return self.report, None


def main():
    """Главная функция"""
    checker = MigrationIntegrityChecker()
    
    try:
        report, filename = checker.run_all_checks()
        
        # Определяем код возврата на основе результатов
        if report['critical_issues'] > 0:
            exit_code = 2  # Критические проблемы
        elif report['failed_checks'] > 0:
            exit_code = 1  # Есть ошибки
        else:
            exit_code = 0  # Все ОК
        
        print(f"\n🏁 Проверка завершена с кодом: {exit_code}")
        sys.exit(exit_code)
        
    except Exception as e:
        print(f"\n🚨 Фатальная ошибка: {e}")
        sys.exit(3)


if __name__ == "__main__":
    main()