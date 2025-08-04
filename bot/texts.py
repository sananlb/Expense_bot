"""
Тексты для локализации согласно ТЗ
"""

TEXTS = {
    'ru': {
        # Основные сообщения
        'welcome': '💰 Добро пожаловать в ExpenseBot!',
        'welcome_text': '''Я помогу вам вести учет трат и отслеживать кешбэки.

💸 Просто отправьте мне текстовое или голосовое сообщение:
"Кофе 200" или "Дизель 4095 АЗС"

📊 Попросите отчет:
"Покажи траты за июль"''',
        'expense_added': '✅ Трата добавлена: {amount} {currency}',
        'expense_deleted': '❌ Трата удалена',
        'expense_updated': '✏️ Трата обновлена',
        'expense_not_found': '❌ Трата не найдена',
        
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
        'cashback_menu': 'Кешбэк',
        'choose_cashback_category': '💳 Выберите категорию для кешбэка:',
        'enter_cashback_info': '''Введите информацию о кешбэке для категории "{category}":

Пример: "альфабанк 5% 2000 руб"''',
        'cashback_added': '✅ Кешбэк добавлен',
        'cashback_deleted': '❌ Кешбэк удален',
        'add_cashback': '➕ Добавить',
        'remove_cashback': '➖ Удалить',
        'remove_all_cashback': '🗑️ Удалить все',
        'no_cashback_info': 'У вас пока нет информации о кешбэках.',
        'add_cashback_hint': 'Добавьте кешбэки ваших банковских карт для отслеживания выгоды от покупок.',
        'choose_bank': '🏦 Выберите банк из списка или введите вручную:',
        'enter_cashback_percent': '💰 Укажите процент кешбэка:\n\nВыберите из списка или введите свой:',
        'cashback_limit_question': '💸 Есть ли лимит кешбэка в месяц?\n\nВыберите из списка или введите свою сумму:',
        'no_limit': 'Без лимита',
        'choose_month': '📅 Выберите месяц:',
        'cashback_month_question': '📅 На какой месяц действует кешбэк?',
        'choose_cashback_to_delete': '➖ Выберите кешбэк для удаления:',
        'no_cashbacks_to_delete': 'У вас нет кешбэков для удаления',
        'confirm_delete_cashback': '⚠️ Вы уверены, что хотите удалить этот кешбэк?',
        'confirm_delete_all_cashbacks': '⚠️ Вы уверены, что хотите удалить ВСЕ кешбэки?\n\nЭто действие нельзя отменить!',
        'cashbacks_deleted': '✅ Удалено кешбэков: {count}',
        'no_cashbacks_found': 'Нет кешбэков для удаления',
        'bank_name_too_long': '❌ Название банка слишком длинное. Максимум 100 символов.',
        'invalid_percent': '❌ Процент должен быть от 0 до 100',
        'invalid_percent_format': '❌ Введите корректный процент (например: 5 или 5.5)',
        'invalid_limit': '❌ Лимит должен быть больше 0',
        'invalid_limit_format': '❌ Введите корректную сумму (например: 1000 или 1000.50)',
        'cashback_details': '🏦 Банк: {bank}\n📁 Категория: {category}\n💰 Процент: {percent}%',
        'cashback_limit_info': '💸 Лимит: {limit}',
        'cashback_month_info': '📅 Месяц: {month}',
        'to_cashbacks': '💳 К кешбэкам',
        'yes_delete': '✅ Да, удалить',
        'yes_delete_all': '✅ Да, удалить все',
        'cancel': '❌ Отмена',
        'adding_cashback': '➕ Добавление кешбэка',
        'choose_category': 'Выберите категорию:',
        'first_create_categories': 'Сначала создайте категории расходов',
        
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
        'settings_menu': 'Настройки',
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
        'back': '⬅️',
        'close': '❌ Закрыть',
        'menu': 'Меню',
        'help': '❓ Справка',
        
        # Меню
        'main_menu': '💰 Главное меню',
        'choose_action': 'Выберите действие:',
        'expenses_today': 'Траты',
        'categories_menu': 'Категории',
        'info': 'Инфо',
        
        # Информация
        'info_text': '''💰 ExpenseBot - ваш помощник в учете трат

Основные возможности:

🔹 Добавление трат:
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
        'unknown_command': '❓ Команда не распознана. Используйте кнопку меню для доступа к функциям.',
        'error_occurred': '❌ Произошла ошибка. Попробуйте позже.',
        'choose_month': 'Выберите месяц:',
        'other_month': 'Другой месяц',
        'voice_not_recognized': '❌ Не удалось распознать голосовое сообщение',
        'voice_processing': '🎤 Обрабатываю голосовое сообщение...',
        'ai_thinking': '🤔 AI анализирует...',
        'no_expenses_today': 'Сегодня трат пока нет',
        'no_expenses_period': 'За указанный период трат нет',
        'expense_report': '📊 Отчет о тратах',
        'general_statistics': 'Общая статистика',
        'total_expenses': 'Всего трат',
        'expense_count': 'Количество записей',
        'average_expense': 'Средняя трата',
        'expenses_by_day': 'Траты по дням',
        'expenses_by_category': 'Траты по категориям',
        'date': 'Дата',
        'amount': 'Сумма',
        'percentage': 'Процент',
        'expense_details': 'Детализация трат',
        'other': 'Прочее',
        'processing': '⏳ Обработка...',
        'done': '✅ Готово!',
        'cancelled': '❌ Отменено',
        'confirm_delete': 'Вы уверены, что хотите удалить эту трату?',
        'yes': 'Да',
        'no': 'Нет',
        
        # Ошибки и сообщения
        'expense_not_recognized': '❌ Не удалось распознать трату.',
        'try_format_hint': 'Попробуйте написать в формате:',
        'voice_expense_not_recognized': '❌ Не удалось распознать трату из голосового сообщения.',
        'voice_try_clearer': 'Попробуйте сказать четче, например:',
        'expense_from_voice_added': '✅ Трата из голосового сообщения добавлена!',
        'ai_confidence': '🤖 AI уверенность: {confidence}%',
        'recognized_text': '🎤 Распознано: "{text}"',
        'receipt_processing_future': '📸 Обработка чеков будет добавлена в следующей версии.',
        'edit_future': 'Редактирование будет добавлено в следующей версии',
        'sum': 'Сумма',
        'description': 'Описание',
        'expenses': 'Траты',
        'change': 'Изменить',
        
        # Отчеты
        'summary_for': 'Сводка за',
        'total_spent_month': 'Всего потрачено',
        'no_expenses_this_month': 'В этом месяце трат пока нет.',
        'other_currencies': 'Другие валюты',
        
        # Категории меню
        'managing_categories': '📁 Управление категориями',
        'your_categories': 'Ваши категории:',
        'no_categories_yet': 'У вас пока нет категорий.',
        'add': '➕ Добавить',
        'edit': '✏️ Редактировать',
        'delete': '➖ Удалить',
        'adding_category': '➕ Добавление новой категории',
        'enter_category_name': 'Введите название категории:',
        'name_too_long': '❌ Название слишком длинное. Максимум 50 символов.',
        'suggest_icon': 'Для категории «{name}» предлагаю иконку: {icon}',
        'use_icon_question': 'Хотите использовать её или выбрать другую?',
        'use_this': '✅ Использовать эту',
        'choose_other': '🎨 Выбрать другую',
        'choose_icon': '🎨 Выберите иконку для категории:',
        'category_added_success': '✅ Категория «{name}» {icon} успешно добавлена!',
        'no_categories_to_edit': 'У вас нет категорий для редактирования',
        'choose_category_to_edit': '✏️ Выберите категорию для редактирования:',
        'choose_category_to_delete': '🗑 Выберите категорию для удаления:',
        'category_deleted_success': '✅ Категория «{name}» {icon} удалена',
        'failed_delete_category': '❌ Не удалось удалить категорию',
        'category_not_found': '❌ Категория не найдена',
        
        # Чат и AI
        'yesterday_expenses_future': 'Функция просмотра трат за вчера будет добавлена в следующей версии.',
        'can_show_today_or_month': 'Я могу показать траты за сегодня или за текущий месяц. Просто спросите!',
        'help_with_expenses': 'Я помогу вам учитывать расходы. Просто отправьте мне сообщение с тратой, например "Кофе 200" или спросите о ваших тратах.',
        'expenses_for_today': 'Траты за сегодня',
        'expenses_for_month': 'Траты за текущий месяц',
        
        # Настройки
        'lang_russian': '🇷🇺 Русский',
        'lang_english': '🇬🇧 English',
        
        # Голосовые сообщения
        'voice_too_long': '⚠️ Голосовое сообщение слишком длинное. Максимум 60 секунд.',
        'voice_download_error': '❌ Ошибка загрузки голосового сообщения',
        'voice_recognition_error': '❌ Не удалось распознать речь.\nПопробуйте говорить четче или отправьте текстовое сообщение.',
        'recognized': '📝 Распознано: {text}',
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
        'cashback_menu': 'Cashback',
        'choose_cashback_category': '💳 Choose category for cashback:',
        'enter_cashback_info': '''Enter cashback info for category "{category}":

Example: "alphabank 5% 2000 rub"''',
        'cashback_added': '✅ Cashback added',
        'cashback_deleted': '❌ Cashback deleted',
        'add_cashback': '➕ Add',
        'remove_cashback': '➖ Delete',
        'remove_all_cashback': '🗑️ Delete all',
        'no_cashback_info': 'You have no cashback information yet.',
        'add_cashback_hint': 'Add cashbacks from your bank cards to track savings from purchases.',
        'choose_bank': '🏦 Choose a bank from the list or enter manually:',
        'enter_bank_name': '🏦 Enter your bank name:',
        'enter_cashback_percent': '💰 Enter cashback percentage:\n\nChoose from list or enter your own:',
        'cashback_limit_question': '💸 Is there a monthly cashback limit?\n\nChoose from list or enter amount:',
        'no_limit': 'No limit',
        'choose_month': '📅 Choose month:',
        'cashback_month_question': '📅 Which month is the cashback valid for?',
        'choose_cashback_to_delete': '➖ Choose cashback to delete:',
        'no_cashbacks_to_delete': 'You have no cashbacks to delete',
        'confirm_delete_cashback': '⚠️ Are you sure you want to delete this cashback?',
        'confirm_delete_all_cashbacks': '⚠️ Are you sure you want to delete ALL cashbacks?\n\nThis action cannot be undone!',
        'cashbacks_deleted': '✅ Deleted cashbacks: {count}',
        'no_cashbacks_found': 'No cashbacks found to delete',
        'bank_name_too_long': '❌ Bank name is too long. Maximum 100 characters.',
        'invalid_percent': '❌ Percentage must be between 0 and 100',
        'invalid_percent_format': '❌ Enter a valid percentage (e.g.: 5 or 5.5)',
        'invalid_limit': '❌ Limit must be greater than 0',
        'invalid_limit_format': '❌ Enter a valid amount (e.g.: 1000 or 1000.50)',
        'cashback_details': '🏦 Bank: {bank}\n📁 Category: {category}\n💰 Percent: {percent}%',
        'cashback_limit_info': '💸 Limit: {limit}',
        'cashback_month_info': '📅 Month: {month}',
        'to_cashbacks': '💳 To cashbacks',
        'yes_delete': '✅ Yes, delete',
        'yes_delete_all': '✅ Yes, delete all',
        'cancel': '❌ Cancel',
        'adding_cashback': '➕ Adding cashback',
        'choose_category': 'Choose category:',
        'first_create_categories': 'First create expense categories',
        
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
        'settings_menu': 'Settings',
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
        'expenses_today': 'Expenses',
        'categories_menu': 'Categories',
        'info': 'Info',
        
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
        'unknown_command': '❓ Command not recognized. Use menu button to access features.',
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
        
        # Errors and messages
        'expense_not_recognized': '❌ Failed to recognize expense.',
        'try_format_hint': 'Try writing in format:',
        'voice_expense_not_recognized': '❌ Failed to recognize expense from voice message.',
        'voice_try_clearer': 'Try speaking more clearly, for example:',
        'expense_from_voice_added': '✅ Expense from voice message added!',
        'ai_confidence': '🤖 AI confidence: {confidence}%',
        'recognized_text': '🎤 Recognized: "{text}"',
        'receipt_processing_future': '📸 Receipt processing will be added in the next version.',
        'edit_future': 'Editing will be added in the next version',
        'sum': 'Amount',
        'description': 'Description',
        'expenses': 'Expenses',
        'change': 'Change',
        
        # Reports
        'summary_for': 'Summary for',
        'total_spent_month': 'Total spent',
        'no_expenses_this_month': 'No expenses this month yet.',
        'other_currencies': 'Other currencies',
        
        # Categories menu
        'managing_categories': '📁 Managing categories',
        'your_categories': 'Your categories:',
        'no_categories_yet': 'You have no categories yet.',
        'add': '➕ Add',
        'edit': '✏️ Edit',
        'delete': '➖ Delete',
        'adding_category': '➕ Adding new category',
        'enter_category_name': 'Enter category name:',
        'name_too_long': '❌ Name is too long. Maximum 50 characters.',
        'suggest_icon': 'For category «{name}» I suggest icon: {icon}',
        'use_icon_question': 'Would you like to use it or choose another?',
        'use_this': '✅ Use this',
        'choose_other': '🎨 Choose another',
        'choose_icon': '🎨 Choose icon for category:',
        'category_added_success': '✅ Category «{name}» {icon} successfully added!',
        'no_categories_to_edit': 'You have no categories to edit',
        'choose_category_to_edit': '✏️ Choose category to edit:',
        'choose_category_to_delete': '🗑 Choose category to delete:',
        'category_deleted_success': '✅ Category «{name}» {icon} deleted',
        'failed_delete_category': '❌ Failed to delete category',
        'category_not_found': '❌ Category not found',
        
        # Chat and AI
        'yesterday_expenses_future': 'Yesterday expenses view will be added in the next version.',
        'can_show_today_or_month': 'I can show expenses for today or current month. Just ask!',
        'help_with_expenses': 'I will help you track expenses. Just send me a message with expense, like "Coffee 200" or ask about your expenses.',
        'expenses_for_today': 'Expenses for today',
        'expenses_for_month': 'Expenses for current month',
        
        # Settings
        'lang_russian': '🇷🇺 Русский',
        'lang_english': '🇬🇧 English',
        
        # Voice messages
        'voice_too_long': '⚠️ Voice message is too long. Maximum 60 seconds.',
        'voice_download_error': '❌ Error downloading voice message',
        'voice_recognition_error': '❌ Failed to recognize speech.\nTry speaking more clearly or send a text message.',
        'recognized': '📝 Recognized: {text}',
    }
}


def get_text(key: str, lang: str = 'ru') -> str:
    """Получить текст по ключу и языку"""
    return TEXTS.get(lang, TEXTS['ru']).get(key, key)