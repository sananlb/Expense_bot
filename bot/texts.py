"""
Тексты для локализации согласно ТЗ
"""

TEXTS = {
    'ru': {
        # Основные сообщения
        'welcome': '💰 Добро пожаловать в ExpenseBot!',
        'welcome_text': '''Я помогу вам вести учет расходов и отслеживать кешбэки.

💸 Просто отправьте мне текстовое или голосовое сообщение:
"Кофе 200" или "Дизель 4095 АЗС"

📊 Попросите отчет:
"Покажи траты за июль"''',
        'expense_added': '✅ Расход добавлен: {amount} {currency}',
        'expense_deleted': '❌ Расход удален',
        'expense_updated': '✏️ Расход обновлен',
        'expense_not_found': '❌ Расход не найден',
        
        # Категории
        'category': 'Категория',
        'categories': 'Категории',
        'your_categories': '📁 Ваши категории:',
        'category_added': '✅ Категория "{name}" добавлена',
        'category_deleted': '❌ Категория "{name}" удалена',
        'category_exists': '⚠️ Категория "{name}" уже существует',
        'category_not_found': '❌ Категория не найдена',
        'enter_category_name': 'Придумайте название новой категории:',
        'choose_category_to_delete': 'Выберите какую категорию вы хотите удалить:',
        'add_category': '➕ Добавить категорию',
        'delete_category': '➖ Удалить категорию',
        
        # Отчеты
        'today_spent': 'Сегодня потрачено',
        'summary': 'Сводка за',
        'total': 'Всего',
        'total_spent': 'Всего потрачено',
        'by_categories': 'По категориям',
        'potential_cashback': 'Потенциальный кешбэк',
        'generate_pdf': '📄 Сформировать PDF отчет',
        'show_month_start': '📅 Показать с начала месяца',
        'pdf_report_generated': '📄 PDF отчет сформирован',
        'report_generation_error': '❌ Ошибка генерации отчета',
        
        # Кешбэки
        'cashbacks': 'Кешбэки на',
        'cashback_menu': '💳 Кешбэк',
        'choose_cashback_category': '💳 Выберите категорию для кешбэка:',
        'enter_cashback_info': '''Введите информацию о кешбэке для категории "{category}":

Пример: "альфабанк 5% 2000 руб"''',
        'cashback_added': '✅ Кешбэк добавлен',
        'cashback_deleted': '❌ Кешбэк удален',
        'add_cashback': '➕ Добавить',
        'remove_cashback': '➖ Удалить',
        'remove_all_cashback': '🗑️ Удалить все',
        
        # Бюджет
        'budget': 'Бюджет',
        'budget_exceeded': '⚠️ Превышен бюджет по категории "{category}"!',
        'budget_set': '✅ Бюджет установлен',
        'budget_removed': '❌ Бюджет удален',
        'enter_budget_amount': 'Введите сумму бюджета:',
        'no_budgets': 'У вас пока нет установленных бюджетов',
        'add_budget': '➕ Добавить бюджет',
        'delete_budget': '➖ Удалить бюджет',
        'choose_category_for_budget': 'Выберите категорию для бюджета:',
        'choose_budget_to_delete': 'Выберите бюджет для удаления:',
        'confirm_delete_budget': 'Вы уверены, что хотите удалить этот бюджет?',
        'invalid_amount': '❌ Неверная сумма. Введите число больше 0',
        'no_categories': 'У вас пока нет категорий',
        
        # Настройки
        'settings': 'Настройки',
        'settings_menu': '⚙️ Настройки',
        'language': 'Язык',
        'timezone': 'Часовой пояс',
        'currency': 'Основная валюта',
        'notifications': 'Уведомления',
        'daily_reports': 'Ежедневные',
        'weekly_reports': 'Еженедельные',
        'monthly_reports': 'Ежемесячные отчеты',
        'report_settings': '📊 Настройки отчетов',
        'report_time': 'Время отправки отчетов',
        'report_types': 'Типы отчетов',
        'enabled_by_default': 'включены по умолчанию',
        'change_time': 'Изменить время',
        'sunday': 'воскресенье',
        'select_time': 'Выберите время отправки отчетов',
        'time_saved': 'Время сохранено',
        'change_language': '🌐 Изменить язык',
        'change_timezone': '🕰️ Изменить часовой пояс',
        'change_currency': '💵 Изменить валюту',
        'configure_reports': '📊 Настройка отчетов',
        'language_changed': '✅ Язык изменен',
        'timezone_changed': '✅ Часовой пояс изменен',
        'currency_changed': '✅ Валюта изменена',
        
        # Кнопки
        'add': 'Добавить',
        'edit': 'Редактировать',
        'delete': 'Удалить',
        'back': '◀️',
        'close': '❌ Закрыть',
        'menu': 'Меню',
        'help': '❓ Справка',
        
        # Меню
        'main_menu': '💰 Главное меню',
        'choose_action': 'Выберите действие:',
        'expenses_today': '📊 Расходы',
        'categories_menu': '📁 Категории',
        'info': 'ℹ️ Инфо',
        
        # Информация
        'info_text': '''💰 ExpenseBot - ваш помощник в учете расходов

Основные возможности:

🔹 Добавление расходов:
Просто отправьте текст или голосовое сообщение:
"Кофе 200" или "Дизель 4095 АЗС"

🔹 Отчеты о тратах:
Попросите отчет естественным языком:
"Покажи траты за июль" или "Сколько я потратил сегодня"

🔹 Кешбэки:
Отслеживайте кешбэки по банковским картам

🔹 Категории:
Создавайте свои категории или используйте готовые

🔹 PDF отчеты:
Получайте красивые отчеты с графиками''',
        
        # Дополнительные
        'auto_detected': 'определена автоматически',
        'description': 'Описание',
        'today': 'Сегодня',
        'yesterday': 'Вчера',
        'this_month': 'Этот месяц',
        'last_month': 'Прошлый месяц',
        'january': 'Январь',
        'february': 'Февраль',
        'march': 'Март',
        'april': 'Апрель',
        'may': 'Май',
        'june': 'Июнь',
        'july': 'Июль',
        'august': 'Август',
        'september': 'Сентябрь',
        'october': 'Октябрь',
        'november': 'Ноябрь',
        'december': 'Декабрь',
        'monday': 'Понедельник',
        'tuesday': 'Вторник',
        'wednesday': 'Среда',
        'thursday': 'Четверг',
        'friday': 'Пятница',
        'saturday': 'Суббота',
        'sunday': 'Воскресенье',
        'rub': '₽',
        'usd': '$',
        'eur': '€',
        'unknown_command': '❓ Команда не распознана. Используйте /menu для вызова главного меню.',
        'error_occurred': '❌ Произошла ошибка. Попробуйте позже.',
        'choose_month': 'Выберите месяц:',
        'other_month': 'Другой месяц',
        'voice_not_recognized': '❌ Не удалось распознать голосовое сообщение',
        'voice_processing': '🎤 Обрабатываю голосовое сообщение...',
        'ai_thinking': '🤔 AI анализирует...',
        'no_expenses_today': 'Сегодня расходов пока нет',
        'no_expenses_period': 'За указанный период расходов нет',
        'expense_report': '📊 Отчет о расходах',
        'general_statistics': 'Общая статистика',
        'total_expenses': 'Всего расходов',
        'expense_count': 'Количество записей',
        'average_expense': 'Средний расход',
        'expenses_by_day': 'Расходы по дням',
        'expenses_by_category': 'Расходы по категориям',
        'date': 'Дата',
        'amount': 'Сумма',
        'percentage': 'Процент',
        'expense_details': 'Детализация расходов',
        'other': 'Прочее',
        'processing': '⏳ Обработка...',
        'done': '✅ Готово!',
        'cancelled': '❌ Отменено',
        'confirm_delete': 'Вы уверены, что хотите удалить этот расход?',
        'yes': 'Да',
        'no': 'Нет',
    },
    'en': {
        # Basic messages
        'welcome': '💰 Welcome to ExpenseBot!',
        'welcome_text': '''I'll help you track expenses and monitor cashbacks.

💸 Just send me a text or voice message:
"Coffee 200" or "Diesel 4095 gas station"

📊 Ask for a report:
"Show expenses for July"''',
        'expense_added': '✅ Expense added: {amount} {currency}',
        'expense_deleted': '❌ Expense deleted',
        'expense_updated': '✏️ Expense updated',
        'expense_not_found': '❌ Expense not found',
        
        # Categories
        'category': 'Category',
        'categories': 'Categories',
        'your_categories': '📁 Your categories:',
        'category_added': '✅ Category "{name}" added',
        'category_deleted': '❌ Category "{name}" deleted',
        'category_exists': '⚠️ Category "{name}" already exists',
        'category_not_found': '❌ Category not found',
        'enter_category_name': 'Enter new category name:',
        'choose_category_to_delete': 'Choose category to delete:',
        'add_category': '➕ Add category',
        'delete_category': '➖ Delete category',
        
        # Reports
        'today_spent': 'Spent today',
        'summary': 'Summary for',
        'total': 'Total',
        'total_spent': 'Total spent',
        'by_categories': 'By categories',
        'potential_cashback': 'Potential cashback',
        'generate_pdf': '📄 Generate PDF report',
        'show_month_start': '📅 Show from month start',
        'pdf_report_generated': '📄 PDF report generated',
        'report_generation_error': '❌ Report generation error',
        
        # Cashbacks
        'cashbacks': 'Cashbacks for',
        'cashback_menu': '💳 Cashback',
        'choose_cashback_category': '💳 Choose category for cashback:',
        'enter_cashback_info': '''Enter cashback info for category "{category}":

Example: "alphabank 5% 2000 rub"''',
        'cashback_added': '✅ Cashback added',
        'cashback_deleted': '❌ Cashback deleted',
        'add_cashback': '➕ Add',
        'remove_cashback': '➖ Delete',
        'remove_all_cashback': '🗑️ Delete all',
        
        # Budget
        'budget': 'Budget',
        'budget_exceeded': '⚠️ Budget exceeded for category "{category}"!',
        'budget_set': '✅ Budget set',
        'budget_removed': '❌ Budget removed',
        'enter_budget_amount': 'Enter budget amount:',
        'no_budgets': 'You have no budgets set yet',
        'add_budget': '➕ Add budget',
        'delete_budget': '➖ Delete budget',
        'choose_category_for_budget': 'Choose category for budget:',
        'choose_budget_to_delete': 'Choose budget to delete:',
        'confirm_delete_budget': 'Are you sure you want to delete this budget?',
        'invalid_amount': '❌ Invalid amount. Enter a number greater than 0',
        'no_categories': 'You have no categories yet',
        
        # Settings
        'settings': 'Settings',
        'settings_menu': '⚙️ Settings',
        'language': 'Language',
        'timezone': 'Timezone',
        'currency': 'Main currency',
        'notifications': 'Notifications',
        'daily_reports': 'Daily',
        'weekly_reports': 'Weekly',
        'change_language': '🌐 Change language',
        'change_timezone': '🕰️ Change timezone',
        'change_currency': '💵 Change currency',
        'configure_reports': '📊 Configure reports',
        'language_changed': '✅ Language changed',
        'timezone_changed': '✅ Timezone changed',
        'currency_changed': '✅ Currency changed',
        
        # Buttons
        'add': 'Add',
        'edit': 'Edit',
        'delete': 'Delete',
        'back': '🏠 Back',
        'close': '❌ Close',
        'menu': 'Menu',
        'help': '❓ Help',
        
        # Menu
        'main_menu': '💰 Main menu',
        'choose_action': 'Choose action:',
        'expenses_today': '📊 Expenses today',
        'categories_menu': '📁 Categories',
        'info': 'ℹ️ Инфо',
        
        # Information
        'info_text': '''💰 ExpenseBot - your expense tracking assistant

Main features:

🔹 Add expenses:
Just send text or voice message:
"Coffee 200" or "Diesel 4095 gas station"

🔹 Expense reports:
Ask for report in natural language:
"Show expenses for July" or "How much did I spend today"

🔹 Cashbacks:
Track bank card cashbacks

🔹 Categories:
Create your own categories or use default ones

🔹 PDF reports:
Get beautiful reports with charts''',
        
        # Additional
        'auto_detected': 'auto detected',
        'description': 'Description',
        'today': 'Today',
        'yesterday': 'Yesterday',
        'this_month': 'This month',
        'last_month': 'Last month',
        'january': 'January',
        'february': 'February',
        'march': 'March',
        'april': 'April',
        'may': 'May',
        'june': 'June',
        'july': 'July',
        'august': 'August',
        'september': 'September',
        'october': 'October',
        'november': 'November',
        'december': 'December',
        'monday': 'Monday',
        'tuesday': 'Tuesday',
        'wednesday': 'Wednesday',
        'thursday': 'Thursday',
        'friday': 'Friday',
        'saturday': 'Saturday',
        'sunday': 'Sunday',
        'rub': '₽',
        'usd': '$',
        'eur': '€',
        'unknown_command': '❓ Command not recognized. Use /menu for main menu.',
        'error_occurred': '❌ An error occurred. Please try later.',
        'choose_month': 'Choose month:',
        'other_month': 'Other month',
        'voice_not_recognized': '❌ Could not recognize voice message',
        'voice_processing': '🎤 Processing voice message...',
        'ai_thinking': '🤔 AI is analyzing...',
        'no_expenses_today': 'No expenses today yet',
        'no_expenses_period': 'No expenses for this period',
        'expense_report': '📊 Expense Report',
        'general_statistics': 'General Statistics',
        'total_expenses': 'Total Expenses',
        'expense_count': 'Number of Records',
        'average_expense': 'Average Expense',
        'expenses_by_day': 'Expenses by Day',
        'expenses_by_category': 'Expenses by Category',
        'date': 'Date',
        'amount': 'Amount',
        'percentage': 'Percentage',
        'expense_details': 'Expense Details',
        'other': 'Other',
        'processing': '⏳ Processing...',
        'done': '✅ Done!',
        'cancelled': '❌ Cancelled',
        'confirm_delete': 'Are you sure you want to delete this expense?',
        'yes': 'Yes',
        'no': 'No',
    }
}


def get_text(key: str, lang: str = 'ru') -> str:
    """Получить текст по ключу и языку"""
    return TEXTS.get(lang, TEXTS['ru']).get(key, key)