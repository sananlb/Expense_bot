"""
Тексты для локализации согласно ТЗ
"""

TEXTS = {
    'ru': {
        # Политики и оферта
        'short_privacy_for_acceptance': 'Для использования бота необходимо принять согласие на обработку персональных данных.',
        'btn_accept_privacy': '✅ Принимаю',
        'btn_decline_privacy': '✖️ Не принимаю',
        'privacy_decline_message': 'Без согласия на обработку персональных данных использование бота невозможно. Вы можете вернуться к началу командой /start.',
        'short_offer_for_acceptance': 'Нажимая «Оплатить», вы соглашаетесь с условиями публичной оферты.',
        'btn_accept_offer': '✅ Принимаю оферту',
        'btn_decline_offer': '✖️ Отказаться',
        'offer_decline_message': 'Без принятия оферты оплата невозможна. Вы можете оформить подписку позже.',
        # Семейный бюджет (домохозяйство)
        'household_default_name': 'Семейный бюджет',
        'household_intro': '🏠 <b>Семейный бюджет</b>\n\nСемейный бюджет позволяет нескольким пользователям вести общий учет доходов и расходов.\n\n• Все участники видят общие траты\n• Максимум 5 участников\n• Приглашение через ссылку',
        'household_subscription_required': '💎 Семейный бюджет доступен только с активной подпиской.',
        'household_full': '❌ В семейном бюджете достигнут максимум участников',
        'create_household_button': '➕ Создать семейный бюджет',
        'invite_member_button': '🔗 Пригласить участника',
        'members_list_button': '👥 Список участников',
        'rename_household_button': '✏️ Переименовать',
        'leave_household_button': '🚪 Выйти из семейного бюджета',
        'back_to_settings': '◀️ Назад к настройкам',
        'household_members_count': 'Участников: {count}/{max}',
        'enter_household_name': 'Введите название для вашего семейного бюджета\n(от 3 до 50 символов)',
        'enter_new_household_name': 'Введите новое название для семейного бюджета\n(от 3 до 50 символов)',
        'use_buttons_only': 'Пожалуйста, используйте кнопки \'Назад\' или \'Закрыть\'',
        'not_in_household': 'Вы не состоите в семейном бюджете',
        'only_creator_can_rename': 'Только создатель может переименовать семейный бюджет',
        'household_leave_confirm': '⚠️ <b>Вы уверены, что хотите выйти из семейного бюджета?</b>\n\nПосле выхода вы будете вести личный учет финансов.',
        'invite_link_title': '🔗 <b>Ссылка-приглашение в семейный бюджет:</b>',
        'invite_link_note': 'Отправьте эту ссылку тому, кого хотите пригласить.',
        'invite_link_valid': 'Ссылка действительна 48 часов.',
        'yes_join': '✅ Да, присоединиться',
        'yes_leave': '✅ Да, выйти',
        'action_cancelled': 'Действие отменено',
        'member_left_notification': '👤 Пользователь {user_id} вышел из семейного бюджета',
        'household_disbanded_notification': '⚠️ Домохозяйство расформировано создателем {user_id}',
        # Основные сообщения
        'welcome': '💰 Добро пожаловать в Coins!',
        'welcome_text': '''Я помогу вам вести учет трат и отслеживать кешбэки.

💸 Отправьте мне текстовое или голосовое сообщение:
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
        'manage_categories': '📁 <b>Управление категориями</b>\n\nВаши категории:',
        'no_categories_yet': 'У вас пока нет категорий.',
        'categories_subscription_note': '💎 <i>Редактирование категорий доступно только с подпиской</i>',
        'income_categories_subscription_note': '💎 Для управления категориями доходов необходима активная подписка',
        'add_button': '➕ Добавить',
        'edit_button': '✏️ Редактировать',
        'delete_button': '➖ Удалить',
        'adding_category': '➕ Добавление новой категории\n\nВведите название категории:',
        'choose_icon_for_category': '🎨 Выберите иконку для категории «{name}»:',
        'send_your_emoji': '✏️ Отправьте свой эмодзи для категории:',
        'choose_category_to_edit': '✏️ Выберите категорию для редактирования:',
        'choose_category_to_delete': '🗑 Выберите категорию для удаления:',
        'name_too_long': '❌ Название слишком длинное. Максимум 50 символов.',
        'send_only_one_emoji': '❌ Пожалуйста, отправьте только один эмодзи.',
        'no_categories_to_edit': 'У вас нет категорий для редактирования',
        'no_categories_to_delete': 'У вас нет категорий для удаления',
        'could_not_delete_category': '❌ Не удалось удалить категорию',
        'error_category_not_found': '❌ Ошибка: не найдена редактируемая категория',
        'could_not_update_category': '❌ Не удалось обновить категорию.',
        
        # Меню категорий
        'expense_categories_title': '📁 Категории трат',
        'income_categories_title': '📁 Категории доходов', 
        'expense_categories_button': '💸 Категории трат',
        'income_categories_button': '💰 Категории доходов',
        'editing_category': '✏️ Редактирование категории «{name}»\n\nВведите новое название категории или нажмите «Пропустить», чтобы оставить текущее:',
        'name_unchanged': 'Название категории оставлено без изменений',
        'choose_new_icon': '🎨 Выберите новую иконку для категории «{name}»:',
        'without_icon': '➡️ Без иконки',
        'enter_custom_emoji': '✏️ Ввести свой эмодзи',
        
        # Отчеты
        'today_spent': 'Сегодня потрачено',
        'summary': 'Сводка за',
        'total': 'Всего',
        'total_spent': 'Всего потрачено',
        'by_categories': 'По категориям',
        'potential_cashback': 'Кешбэк',
        'generate_pdf': '📄 Сформировать PDF отчет',
        'show_month_start': '📅 Показать с начала месяца',
        'pdf_report_generated': '📄 PDF отчет сформирован',
        'report_generation_error': '❌ Ошибка генерации отчета',
        
        # Кешбэки
        'cashbacks': 'Кешбэки на',
        'cashbacks_for': 'Кешбэки на',
        'cashback_menu': 'Кешбэк',
        'limit': 'лимит',
        'edit': '✏️ Редактировать',
        'all_categories': '🌐 Все категории',
        'choose_bank_or_enter': '🏦 Выберите банк или введите название:',
        'cashback_editing': '✏️ Редактирование кешбэка',
        'choose_cashback_to_edit': '✏️ Выберите кешбэк для редактирования:',
        'no_cashbacks_to_edit': 'У вас нет кешбэков для редактирования',
        'cashback_management_subscription': '💳 Управление кешбэками доступно только с подпиской.',
        'skip': '⏭️ Пропустить',
        'bank_list_ru': 'Т-Банк,Альфа,ВТБ,Сбер,Райффайзен,Яндекс,Озон',
        'choose_cashback_category': '💳 Выберите категорию для кешбэка:',
        'enter_cashback_info': '''Введите информацию о кешбэке для категории "{category}":

Пример: "альфабанк 5% 2000 руб"''',
        'cashback_added': '✅ Кешбэк добавлен',
        'cashback_deleted': '❌ Кешбэк удален',
        'add_cashback': '➕ Добавить',
        'remove_cashback': '➖ Удалить',
        'remove_all_cashback': '🗑 Удалить все',
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
        'enter_cashback_desc_percent': '💰 Введите описание (необязательно) и процент кешбэка:',
        'cashback_examples': '<b>Примеры:</b>\n• 5\n• Все покупки 3.5\n• Только онлайн 10%\n• В супермаркетах 7',
        'incorrect_format': '❌ Некорректный формат.\n\nВведите описание и процент.\nНапример: Все покупки 5',
        'incorrect_percent': '❌ Некорректный процент. Попробуйте еще раз.',
        'percent_over_100': '❌ Процент не может быть больше 100%',
        'percent_must_be_positive': '❌ Процент должен быть больше 0',
        'error_saving': '❌ Ошибка при сохранении: {error}',
        'editing_cashback': '💳 <b>Редактирование кешбэка</b>',
        'choose_new_bank': 'Выберите новый банк или введите название:',
        'current_bank': 'Текущий банк',
        'choose_new_bank_or_enter': 'Выберите новый банк или введите название:',
        'bank': 'Банк',
        'current_percent': 'Текущий процент',
        'current_description': 'Текущее описание',
        'enter_new_description_and_percent': 'Введите новое описание (необязательно) и процент:',
        'examples': 'Примеры',
        'all_purchases': 'Все покупки',
        'online_only': 'Только онлайн',
        'in_supermarkets': 'В супермаркетах',
        'incorrect_format_percent': '❌ Некорректный формат.\n\nВведите описание и процент.\nНапример: Все покупки 5',
        'percent_too_high': '❌ Процент не может быть больше 100%',
        'percent_too_low': '❌ Процент должен быть больше 0',
        'save_error': '❌ Ошибка при сохранении',
        'enter_description_and_percent': 'Введите описание (необязательно) и процент кешбэка:',
        'cashback_delete_failed': '❌ Не удалось удалить кешбэк',
        'confirm_delete_cashback': '⚠️ Вы уверены, что хотите удалить этот кешбэк?',
        'confirm_delete_all_cashbacks': '⚠️ Вы уверены, что хотите удалить ВСЕ кешбэки?\n\nЭто действие нельзя отменить!',
        'choose_month_for_cashback': '📅 На какой месяц действует кешбэк?',
        'choose_month': '📅 Выберите месяц:',
        'could_not_delete_cashback': '❌ Не удалось удалить кешбэк',
        'cashback_not_found': '❌ Кешбэк не найден',
        
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
        'household_button': '🏠 Семейный бюджет',
        'my_budget_button': '👤 Мой бюджет',
        'household_budget_button': '🏠 Семейный бюджет',
        'view_scope': 'Режим отображения',
        'view_scope_personal': '👤 Личный',
        'view_scope_household': '🏠 Семейный',
        'toggle_view_scope': 'Переключить режим (сейчас: {scope})',
        'scope_switched_to_personal': 'Режим переключен: Личный',
        'scope_switched_to_household': 'Режим переключен: Семейный',
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
        'change_language': '🌐 Язык / Language',
        'change_timezone': '🕰️ Изменить часовой пояс',
        'change_currency': '💵 Изменить валюту',
        'configure_reports': '📊 Настройка отчетов',
        'toggle_cashback': '💳 {status} кешбэк',
        'enable_cashback': 'Вкл',
        'disable_cashback': 'Откл',
        'cashback_enabled_message': '✅ Кешбэк включен',
        'cashback_disabled_message': '❌ Кешбэк отключен',
        'change_language_prompt': '🌐 Выберите язык / Select language:',
        'language_changed': '✅ Язык изменен',
        'timezone_changed': '✅ Часовой пояс изменен',
        'currency_changed': '✅ Валюта изменена',

        # Регулярные операции
        'recurring_hint': 'Добавьте ежемесячный платеж или ежемесячный доход, и он будет автоматически записываться в выбранный день.',
        
        # Кнопки
        'add': 'Добавить',
        'edit': 'Редактировать',
        'delete': 'Удалить',
        'back': '⬅️ Назад',
        'back_arrow': '⬅️ Назад',
        'back_button': '⬅️ Назад',
        'close': '❌ Закрыть',
        'menu': 'Меню',
        'help': '❓ Справка',
        'diary_button': '📋 Дневник',
        'diary_title': '📋 <b>Дневник</b>',
        'expense_list_title': '📋 Список трат',
        'no_expenses_found': '<i>Трат не найдено</i>',
        'month_start_button': '📅 С начала месяца',
        'today_arrow': 'Сегодня →',
        'prev_month_arrow': '← Предыдущий месяц',
        'top5_button': '🔥 Топ‑5',
        'top5_info_title': 'Ваши 5 самых популярных операций с одинаковой суммой, категорией и названием.',
        'top5_info_pin_hint': '💡 _Закрепите это сообщение для быстрой записи._',
        'top5_empty': 'Пока нет часто повторяющихся операций за 3 месяца.',
        
        # Меню
        'main_menu': '💰 Главное меню',
        'main_menu_title': '💰 Главное меню\n\nВыберите действие:',
        'choose_action': 'Выберите действие:',
        'expenses_today': 'Бюджет',
        'expenses_button': '📊 Расходы',
        'cashback_button': '💳 Кешбэк',
        'categories_menu': 'Категории',
        'categories_button': '📁 Категории',
        'recurring_button': '🔄 Ежемесячные операции',
        'subscription_button': '⭐ Подписка',
        'referral_button': '🎁 Реферальная программа',
        'settings_button': '⚙️ Настройки',
        'info_button': '📖 Информация',
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
Получайте красивые отчеты с графиками

📝 Обратная связь:
Если у вас есть вопросы или предложения, пишите @SMF_support

🔬 Бета-тестирование:
Спасибо за участие в тестировании! Ваши отзывы помогают улучшать бот.''',
        
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
        
        # Меню трат
        'spent_per_month': '💸 <b>Потрачено за месяц:</b>',
        'other_expenses': '📊 Остальные расходы',
        'show_other_period': '<i>Показать отчет за другой период?</i>',
        'no_data_for_report': '❌ <b>Нет данных для отчета</b>\n\nЗа выбранный месяц не найдено расходов.',
        'report_for_month': '📊 <b>Отчет за {month} {year}</b>',
        'report_contains': 'В отчете содержится:\n• Общая статистика расходов\n• Распределение по категориям\n• Динамика трат по дням\n• Информация о кешбэке\n\n💡 <i>Совет: сохраните отчет для отслеживания динамики расходов</i>',
        'error_generating_report': '❌ <b>Ошибка при генерации отчета</b>\n\nПопробуйте позже или обратитесь в поддержку.',
        'could_not_update_amount': '❌ Не удалось обновить сумму',
        'could_not_update_description': '❌ Не удалось обновить описание',
        'description_cannot_be_empty': '❌ Описание не может быть пустым',
        'could_not_recognize_amount': '❌ Не удалось распознать сумму.\nПожалуйста, введите число (например: 750 или 10.50):\n\n💡 Подсказка: Если хотите посмотреть траты, используйте команды:\n• /expenses - траты за сегодня\n• "покажи траты вчера" - траты за вчера\n• "траты за неделю" - траты за неделю',
        'want_to_add_expense': '💰 Вы хотите внести трату/доход "{text}"?\n\nУкажите сумму:',
        'total_shown': '💰 <b>Итого показано:</b>',
        'total_for_day': '💰 <b>Итого за день:</b>',
        'show_expenses_other_days': '\n<i>💡 Показать траты в другие дни?</i>',
        'diary_error': 'Произошла ошибка при загрузке дневника',
        'select_category_for_payment': '📁 Выберите категорию для платежа:',
        'editing_payment': '✏️ <b>Редактирование платежа</b>',
        'regular_payment': 'Регулярный платеж',
        'payment_amount': 'Сумма',
        'payment_date': 'Дата',
        'payment_status': 'Статус',
        'to_change_send': 'Чтобы изменить, отправьте:',
        'only_amount': '• Только сумму',
        'name_and_amount': '• Название и сумму',
        
        # Реферальная программа
        'get_referral_link': '🔗 Получить реферальную ссылку',
        'copy_link': '📋 Скопировать ссылку',
        'my_statistics': '📊 Моя статистика',
        'referral_program_text': '🎁 <b>Реферальная программа</b>\n\nПриглашайте друзей и получайте бонусы!\n\nКак только приглашённый оплатит свою первую подписку, мы продлим вашу на такой же срок (однократно).\n\nНажмите кнопку ниже, чтобы получить персональную ссылку.',
        'your_referral_link': '🎁 <b>Ваша реферальная ссылка</b>',
        'link_copied': '✅ Ссылка скопирована!',
        'referral_statistics': '📊 <b>Ваша статистика</b>',
        'invited_friends': '👥 Приглашено друзей',
        'with_subscription': '⭐ Бонусы выданы',
        'earned_days': '🎁 Получено месяцев',
        'referral_list': '📃 <b>Ваши рефералы:</b>',
        'no_referrals_yet': 'У вас пока нет рефералов',
        'invite_friends_bonus': 'Приглашайте друзей: первая покупка продлит вашу подписку!',
        'share_link': '📨 Поделиться ссылкой',
        'select_month_for_pdf': '📊 <b>Выберите месяц для PDF отчета</b>\n\nЯ сгенерирую для вас подробный отчет с графиками и статистикой.',
        'generating_report': '⏳ <b>Генерирую отчет...</b>\n\nЭто может занять несколько секунд.',
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
        'no_expenses_today': 'Сегодня операций пока нет',
        'no_expenses_period': 'За указанный период операций нет',
        'profile_not_found': 'Профиль пользователя не найден',
        'no_category': 'Без категории',
        'unknown_period': 'Неизвестный период',
        'for': 'за',
        'from': 'с',
        'to': 'по',
        'expenses': 'Траты',
        'expenses_count': 'трат',
        'amount_for': 'на сумму',
        'day_max_expenses': 'День с максимальными тратами',
        'category_statistics': 'Статистика по категориям',
        'and_more': 'и еще',
        'error': 'Ошибка',
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
        
        # Ежемесячные операции
        'recurring_payments': '🔄 Ежемесячные операции',
        'recurring_menu': '🔄 Ежемесячные операции',
        'no_recurring_payments': 'У вас пока нет регулярных операций.',
        'recurring_income_section': '💰 <b>Доходы</b>',
        'recurring_expense_section': '💸 <b>Расходы</b>',
        'add_recurring': '➕ Добавить',
        'edit_recurring': '✏️ Редактировать',
        'delete_recurring': '➖ Удалить',
        'add_recurring_payment': '➕ Добавление регулярного платежа или дохода',
        'recurring_payment_hint': 'Отправьте сумму или название и сумму:\n\nПримеры:\n• <i>50000</i> - только сумма (расход)\n• <i>Квартира 50000</i> - название и сумма (расход)\n• <i>+80000</i> - доход\n• <i>Зарплата +80000</i> - название и доход\n\nЕсли вы не укажете название, оно будет создано автоматически из категории.',
        'choose_category_for_payment': '📁 Выберите категорию для платежа:',
        'choose_payment_day': '📅 В какой день месяца записывать платеж?\n\nВыберите из списка или введите число от 1 до 30:',
        'day_number': '{day} число',
        'recurring_payment_added': '✅ Регулярный платеж добавлен',
        'choose_recurring_to_edit': '✏️ Выберите платеж для редактирования:',
        'select_payment_to_edit': '✏️ Выберите платеж для редактирования:',
        'choose_recurring_to_delete': '🗑 Выберите платеж для удаления:',
        'select_payment_to_delete': '🗑 Выберите платеж для удаления:',
        'editing_recurring': '✏️ Редактирование платежа',
        'edit_payment_text': '✏️ <b>Редактирование платежа</b>\n\nРегулярный платеж: <i>{description}</i>\nСумма: <i>{amount}</i>\nКатегория: <i>{category}</i>\nДата: <i>{day} число месяца</i>\nСтатус: <i>{status}</i>\n\nЧтобы изменить, отправьте:\n• Только сумму: <i>50000</i>\n• Название и сумму: <i>Квартира 50000</i>',
        'recurring_payment': 'Регулярный платеж',
        'status': 'Статус',
        'active': 'Активен ✅',
        'paused': 'Приостановлен ⏸',
        'payment_active': 'Активен ✅',
        'payment_paused': 'Приостановлен ⏸',
        'pause_payment': '⏸ Приостановить',
        'resume_payment': '▶️ Возобновить',
        'payment_status_changed': '✅ Статус платежа изменен',
        'payment_deleted': '✅ Платеж удален',
        'edit_amount': '💰 Сумму',
        'edit_description': '📝 Название',
        'edit_category': '📁 Категорию',
        'edit_day': '📅 День',
        'enter_new_amount': '💰 Введите новую сумму:',
        'enter_new_description': '📝 Введите новое название:',
        'choose_new_category': '📁 Выберите новую категорию:',
        'enter_new_day': '📅 Введите новый день месяца (1-30):',
        'day_of_month': '{day} число месяца',
        'recurring_amount': 'Сумма',
        'recurring_date': 'Дата',
        'recurring_category': 'Категория',
        'to_change_send': 'Чтобы изменить, отправьте:\n• Только сумму: <i>50000</i>\n• Название и сумму: <i>Квартира 50000</i>',
        'day_should_be_1_30': '❌ День должен быть от 1 до 30',
        'enter_day_1_30': '❌ Введите число от 1 до 30',
        'no_recurring_payments_to_edit': 'У вас нет регулярных платежей для редактирования',
        'no_recurring_payments_to_delete': 'У вас нет регулярных платежей для удаления',
        'payment_not_found': 'Платеж не найден',
        'delete_payment_failed': '❌ Не удалось удалить платеж',
        
        # Подписка
        'subscription': 'Подписка',
        'subscription_menu': '⭐ Подписка',
        'no_active_subscription': '❌ У вас нет активной подписки',
        'subscription_benefits': 'С подпиской вы получаете:\n• Голосовой ввод расходов\n• PDF-отчеты с графиками\n• Автоматические отчеты\n• Кастомные категории\n• Отслеживание кешбэков\n• Ежемесячные операции',
        'active_subscription': '✅ У вас есть активная подписка',
        'subscription_type': 'Тип',
        'trial_period': 'Пробный период',
        'subscription_expires': 'Действует до',
        'subscription_history': '📜 История платежей',
        'buy_subscription': '💳 Оплатить',
        'referral_program': '🎁 Реферальная программа',
        'back_to_subscription': 'Назад в меню подписки',
        'invalid_subscription_type': 'Неверный тип подписки',
        'subscription_advantages': '💎 Преимущества вашей подписки:\n• Безлимитные траты\n• PDF отчёты\n• Голосовой ввод\n• Ежемесячные операции\n• Отслеживание кешбэков',
        'you_received_days': 'Вы получили {days} дней подписки',
        'subscription_valid_until': 'Подписка действует до: {date}',
        'promocode_activated': '✅ Промокод активирован!',
        'friend_got_subscription': '🎉 Поздравляем!\n\nВаш друг оформил подписку по вашей реферальной ссылке.\nМы продлили вашу подписку на срок его первой покупки (один раз).\n\nСпасибо, что рекомендуете нас!',
        
        # Тексты меню подписки
        'month_stars': '⭐ На месяц - 150 звёзд',
        'six_months_stars': '⭐ На 6 месяцев - 600 звёзд',
        'have_promocode': '🎟️ У меня есть промокод',
        'subscription_month_title': 'Подписка на месяц',
        'subscription_month_desc': 'Полный доступ ко всем функциям на 1 месяц',
        'subscription_six_months_title': 'Подписка на 6 месяцев',
        'subscription_six_months_desc': 'Полный доступ ко всем функциям на 6 месяцев',
        'beta_tester_status': '🔬 <b>У вас статус бета-тестера</b>',
        'beta_access_text': 'Вы имеете полный доступ ко всем функциям бота.\nСпасибо за участие в тестировании! 🙏',
        'active_subscription_text': 'У вас есть активная подписка',
        'valid_until': 'Действует до',
        'days_left': 'Осталось дней',
        'can_extend_early': 'Вы можете продлить подписку заранее.',
        'enter_promocode': '🎟️ <b>Введите промокод</b>',
        'promocode_instruction': 'Отправьте промокод для активации специального предложения:',
        'promocode_not_found': '❌ <b>Промокод не найден</b>',
        'promocode_invalid': '❌ <b>Промокод недействителен</b>',
        'promocode_already_used': '❌ <b>Вы уже использовали этот промокод</b>',
        'promocode_accepted': '✅ <b>Промокод принят!</b>',
        'payment_successful': '✨ <b>Оплата прошла успешно!</b>',
        'subscription_benefits_title': '💎 <b>Преимущества вашей подписки:</b>',
        'unlimited_expenses': '• Безлимитные траты',
        'pdf_reports': '• PDF отчёты',
        'priority_support': '• Приоритетная поддержка',
        'thanks_support': 'Спасибо за поддержку проекта! 💙',
        'subscription_required': '❌ <b>Требуется подписка</b>',
        'subscription_required_text': 'Для использования этой функции необходима активная подписка.\n\nНажмите кнопку ниже, чтобы оформить подписку:',
        'get_subscription': '⭐ Оформить подписку',
        'back_to_menu': 'Назад в меню подписки',
        
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
        'editing_expense': 'Редактирование траты',
        'choose_field_to_edit': 'Выберите поле для изменения:',
        'choose_new_category': 'Выберите новую категорию',
        'learning_message': 'Меняя категорию вы обучаете систему, с каждым редактированием подбор категорий становится точнее для вас',
        'editing_amount': 'Изменение суммы',
        'enter_new_amount': 'Введите новую сумму:',
        'editing_description': 'Изменение описания',
        'enter_new_description': 'Введите новое описание:',
        'edit_done': 'Готово',
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
        'add_button': '➕ Добавить',
        'edit_button': '✏️ Редактировать', 
        'delete_button': '➖ Удалить',
        'adding_category': '➕ Добавление новой категории\n\nВведите название категории:',
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
        'expenses_for_today': 'Операции за сегодня',
        'expenses_for_month': 'Операции за текущий месяц',
        
        # Настройки
        'lang_russian': '🇷🇺 Русский',
        'lang_english': '🇬🇧 English',
        
        # Месяцы
        'january': 'январь',
        'february': 'февраль',
        'march': 'март',
        'april': 'апрель',
        'may': 'май',
        'june': 'июнь',
        'july': 'июль',
        'august': 'август',
        'september': 'сентябрь',
        'october': 'октябрь',
        'november': 'ноябрь',
        'december': 'декабрь',
        
        # Голосовые сообщения
        'voice_too_long': '⚠️ Голосовое сообщение слишком длинное. Максимум 60 секунд.',
        'voice_download_error': '❌ Ошибка загрузки голосового сообщения',
        'voice_recognition_error': '❌ Не удалось распознать речь.\nПопробуйте говорить четче или отправьте текстовое сообщение.',
        'recognized': '📝 Распознано: {text}',

        # Справка
        # Старый текст справки (закомментирован)
        # 'help_main_text': '''<b>📖 Справка по использованию бота</b>
        #
        # <b>🚀 Быстрый старт:</b>
        # Просто отправьте сообщение с тратой: "кофе 200" или "такси 500"
        # Бот автоматически определит категорию и сохранит трату.
        #
        # <b>💸 Как записать расходы:</b>
        # • Текст: "продукты 1500", "бензин 3000"
        # • С датой: "вчера кофе 200", "10.09 обед 450"
        # • Голосом: запишите голосовое сообщение
        #
        # <b>💰 Как записать доходы:</b>
        # • Добавьте плюс: "+50000 зарплата", "премия +10000"
        # • Или используйте меню "➕ Доход"
        #
        # <b>📊 Отчеты:</b>
        # • "покажи траты за июль"
        # • "сколько потратил на продукты"
        # • "отчет за месяц"
        #
        # <b>💳 Кешбэки:</b>
        # Настройте карты с кешбэками в меню "💳 Кешбэки".
        # Бот автоматически посчитает выгоду по каждой категории.
        #
        # <b>🏠 Семейный бюджет:</b>
        # Создайте семью в настройках и ведите общий учет.
        # Все участники видят общие траты и доходы.
        #
        # <b>⚙️ Полезные команды:</b>
        # • /start - главное меню
        # • /help - эта справка
        # • /cashback - настройка кешбэков
        # • /report - запросить отчет
        # • /settings - настройки
        #
        # <b>💡 Советы:</b>
        # • Закрепите сообщение с кешбэками для быстрого доступа
        # • Используйте голосовые сообщения в дороге
        # • Добавляйте траты сразу, чтобы ничего не забыть''',

        # Новый текст справки
        'help_main_text': '''<b>📖 Справка по использованию бота</b>

<b>💸 Ввод траты/дохода:</b>
Можно писать или отправить голосовое сообщение.
Примеры:
• Трата: "Такси 550", "Кофе 200"
• Доход: "+3500 заказ" (знак "+" = доход)

Бот сделает запись и ответит вам. Нажав кнопку "Редактировать", вы можете изменить любые параметры записи.

Отредактируйте категорию - бот запомнит, к какой категории относится ваша трата, и в следующий раз будет выбирать категорию правильно.

Можно вводить трату/доход без суммы одним словом, если у вас уже была подобная запись - бот возьмет всю информацию из предыдущей записи.

Можно делать запись задним числом - для этого в конце траты напишите дату в формате 23.09.2025

<b>💳 Кешбэк:</b>
Кешбэк можно вводить через меню, а можно и сообщением боту в формате:
"кешбэк X% категория XXXX банк"

Закрепите заметку с кешбэками в чате с ботом, чтобы иметь быстрый доступ.

<b>💬 Вопросы боту естественным языком:</b>
Спрашивайте бота о ваших финансах простыми словами:
• "Сколько я потратил на продукты в этом месяце?"
• "Сколько я потратил на кофе в августе?"
• "Какая моя самая большая трата за неделю?"
• "Сколько я заработал в сентябре?"
• "На что я трачу больше всего денег?"

Бот понимает разговорный язык и поможет с анализом ваших финансов.''',
    },
    'en': {
        # Policies and offer
        'short_privacy_for_acceptance': 'To use the bot, you need to accept the privacy consent.',
        'btn_accept_privacy': '✅ Accept',
        'btn_decline_privacy': '✖️ Decline',
        'privacy_decline_message': 'You cannot use the bot without accepting the privacy consent. You can come back with /start.',
        'short_offer_for_acceptance': 'By clicking “Pay”, you accept the public offer terms.',
        'btn_accept_offer': '✅ Accept offer',
        'btn_decline_offer': '✖️ Decline',
        'offer_decline_message': 'Payment is not possible without accepting the offer. You can subscribe later.',
        # Household (family budget)
        'household_default_name': 'Household',
        'household_intro': '🏠 <b>Household</b>\n\nThe household lets multiple users track finances together.\n\n• All participants see shared expenses\n• Up to 5 members\n• Invitation via link',
        'household_subscription_required': '💎 Household budgeting is available only with an active subscription.',
        'household_full': '❌ The household is full',
        'create_household_button': '➕ Create household',
        'invite_member_button': '🔗 Invite member',
        'members_list_button': '👥 Members',
        'rename_household_button': '✏️ Rename',
        'leave_household_button': '🚪 Leave household',
        'back_to_settings': '◀️ Back to settings',
        'household_members_count': 'Members: {count}/{max}',
        'enter_household_name': 'Enter a name for your household\n(3 to 50 characters)',
        'use_buttons_only': 'Please use Back or Close buttons',
        'enter_new_household_name': 'Enter a new name for your household\n(3 to 50 characters)',
        'not_in_household': 'You are not in a household',
        'only_creator_can_rename': 'Only the household creator can rename it',
        'household_leave_confirm': '⚠️ <b>Are you sure you want to leave the household?</b>\n\nAfter leaving you will track finances personally.',
        'invite_link_title': '🔗 <b>Household invite link:</b>',
        'invite_link_note': 'Send this link to the person you want to invite.',
        'invite_link_valid': 'The link is valid for 48 hours.',
        'yes_join': '✅ Yes, join',
        'yes_leave': '✅ Yes, leave',
        'action_cancelled': 'Action cancelled',
        'member_left_notification': '👤 User {user_id} left the household',
        'household_disbanded_notification': '⚠️ Household was disbanded by creator {user_id}',
        # Basic messages
        'welcome': '💰 Welcome to Coins!',
        'welcome_text': '''I'll help you track expenses and monitor cashbacks.

💸 Send me a text or voice message:
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
        'manage_categories': '📁 <b>Category management</b>\n\nYour categories:',
        'no_categories_yet': 'You have no categories yet.',
        'categories_subscription_note': '💎 <i>Category editing is available only with subscription</i>',
        'income_categories_subscription_note': '💎 Income categories management is available only with an active subscription',
        'add_button': '➕ Add',
        'edit_button': '✏️ Edit',
        'delete_button': '➖ Delete',
        'adding_category': '➕ Adding new category\n\nEnter category name:',
        'choose_icon_for_category': '🎨 Choose icon for category «{name}»:',
        'send_your_emoji': '✏️ Send your emoji for category:',
        'choose_category_to_edit': '✏️ Choose category to edit:',
        'choose_category_to_delete': '🗑 Choose category to delete:',
        'name_too_long': '❌ Name is too long. Maximum 50 characters.',
        'send_only_one_emoji': '❌ Please send only one emoji.',
        'no_categories_to_edit': 'You have no categories to edit',
        'no_categories_to_delete': 'You have no categories to delete',
        'could_not_delete_category': '❌ Could not delete category',
        'error_category_not_found': '❌ Error: edited category not found',
        'could_not_update_category': '❌ Could not update category.',
        
        # Categories menu
        'expense_categories_title': '📁 Expense Categories',
        'income_categories_title': '📁 Income Categories',
        'expense_categories_button': '💸 Expense Categories', 
        'income_categories_button': '💰 Income Categories',
        'editing_category': '✏️ Editing category «{name}»\n\nEnter new category name or press «Skip» to keep current:',
        'name_unchanged': 'Category name unchanged',
        'choose_new_icon': '🎨 Choose new icon for category «{name}»:',
        'without_icon': '➡️ Without icon',
        'enter_custom_emoji': '✏️ Enter custom emoji',
        
        # Reports
        'today_spent': 'Spent today',
        'summary': 'Summary for',
        'total': 'Total',
        'total_spent': 'Total spent',
        'by_categories': 'By categories',
        'potential_cashback': 'Cashback',
        'generate_pdf': '📄 Generate PDF report',
        'show_month_start': '📅 Show from month start',
        'pdf_report_generated': '📄 PDF report generated',
        'report_generation_error': '❌ Report generation error',
        
        # Cashbacks
        'cashbacks': 'Cashbacks for',
        'cashback_menu': 'Cashback',
        'edit': '✏️ Edit',
        'all_categories': '🌐 All categories',
        'choose_bank_or_enter': '🏦 Choose bank or enter name:',
        'cashback_editing': '✏️ Editing cashback',
        'choose_cashback_to_edit': '✏️ Choose cashback to edit:',
        'no_cashbacks_to_edit': 'You have no cashbacks to edit',
        'cashback_management_subscription': '💳 Cashback management is available only with subscription.',
        'skip': '⏭️ Skip',
        'bank_list_en': 'Tinkoff,Alfa,VTB,Sber,Raiffeisen,Yandex,Ozon',
        'choose_cashback_category': '💳 Choose category for cashback:',
        'enter_cashback_info': '''Enter cashback info for category "{category}":

Example: "alphabank 5% 2000 rub"''',
        'cashback_added': '✅ Cashback added',
        'cashback_deleted': '❌ Cashback deleted',
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
        'enter_cashback_desc_percent': '💰 Enter description (optional) and cashback percent:',
        'cashback_examples': '<b>Examples:</b>\n• 5\n• All purchases 3.5\n• Online only 10%\n• In supermarkets 7',
        'incorrect_format': '❌ Incorrect format.\n\nEnter description and percent.\nFor example: All purchases 5',
        'incorrect_percent': '❌ Incorrect percent. Try again.',
        'percent_over_100': '❌ Percent cannot be over 100%',
        'percent_must_be_positive': '❌ Percent must be greater than 0',
        'error_saving': '❌ Error saving: {error}',
        'editing_cashback': '💳 <b>Editing cashback</b>',
        'choose_new_bank': 'Choose new bank or enter name:',
        'current_bank': 'Current bank',
        'choose_new_bank_or_enter': 'Choose new bank or enter name:',
        'bank': 'Bank',
        'current_percent': 'Current percent',
        'current_description': 'Current description',
        'enter_new_description_and_percent': 'Enter new description (optional) and percent:',
        'examples': 'Examples',
        'all_purchases': 'All purchases',
        'online_only': 'Online only',
        'in_supermarkets': 'In supermarkets',
        'incorrect_format_percent': '❌ Incorrect format.\n\nEnter description and percent.\nFor example: All purchases 5',
        'percent_too_high': '❌ Percent cannot be over 100%',
        'percent_too_low': '❌ Percent must be greater than 0',
        'save_error': '❌ Error saving',
        'enter_description_and_percent': 'Enter description (optional) and cashback percent:',
        'cashback_delete_failed': '❌ Failed to delete cashback',
        'confirm_delete_cashback': '⚠️ Are you sure you want to delete this cashback?',
        'confirm_delete_all_cashbacks': '⚠️ Are you sure you want to delete ALL cashbacks?\n\nThis action cannot be undone!',
        'choose_month_for_cashback': '📅 Which month is the cashback valid for?',
        'choose_month': '📅 Choose month:',
        'could_not_delete_cashback': '❌ Could not delete cashback',
        'cashback_not_found': '❌ Cashback not found',
        
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
        'household_button': '🏠 Household',
        'my_budget_button': '👤 My budget',
        'household_budget_button': '🏠 Household budget',
        'view_scope': 'View scope',
        'view_scope_personal': '👤 Personal',
        'view_scope_household': '🏠 Household',
        'toggle_view_scope': 'Toggle view (now: {scope})',
        'scope_switched_to_personal': 'Scope switched: Personal',
        'scope_switched_to_household': 'Scope switched: Household',
        'language': 'Language',
        'timezone': 'Timezone',
        'currency': 'Main currency',
        'notifications': 'Notifications',
        'daily_reports': 'Daily',
        'weekly_reports': 'Weekly',
        'change_language': '🌐 Язык / Language',
        'change_timezone': '🕰️ Change timezone',
        'change_currency': '💵 Change currency',
        'configure_reports': '📊 Configure reports',
        'toggle_cashback': '💳 {status} cashback',
        'enable_cashback': 'Enable',
        'disable_cashback': 'Disable',
        'cashback_enabled_message': '✅ Cashback enabled',
        'cashback_disabled_message': '❌ Cashback disabled',
        'change_language_prompt': '🌐 Select language / Выберите язык:',
        'language_changed': '✅ Language changed',
        'timezone_changed': '✅ Timezone changed',
        'currency_changed': '✅ Currency changed',

        # Recurring operations
        'recurring_hint': 'Add a monthly payment or monthly income, and it will be recorded automatically on the selected day.',
        
        # Buttons
        'add': 'Add',
        'edit': 'Edit',
        'delete': 'Delete',
        'back': '⬅️ Back',
        'back_arrow': '⬅️ Back',
        'back_button': '⬅️ Back',
        'close': '❌ Close',
        'menu': 'Menu',
        'help': '❓ Help',
        'diary_button': '📋 Diary',
        'diary_title': '📋 <b>Diary</b>',
        'expense_list_title': '📋 Expense list',
        'no_expenses_found': '<i>No expenses found</i>',
        'month_start_button': '📅 From month start',
        'today_arrow': 'Today →',
        'prev_month_arrow': '← Previous month',
        'top5_button': '🔥 Top‑5',
        'top5_info_title': 'Your 5 most frequent operations with the same amount, category and title.',
        'top5_info_pin_hint': '💡 _Pin this message for quick entry._',
        'top5_empty': 'No frequently repeated operations for the last 3 months yet.',
        
        # Menu
        'main_menu': '💰 Main menu',
        'main_menu_title': '💰 Main menu\n\nChoose action:',
        'choose_action': 'Choose action:',
        'expenses_today': 'Budget',
        'expenses_button': '📊 Expenses',
        'cashback_button': '💳 Cashback',
        'categories_menu': 'Categories',
        'categories_button': '📁 Categories',
        'recurring_button': '🔄 Recurring operations',
        'subscription_button': '⭐ Subscription',
        'referral_button': '🎁 Referral program',
        'settings_button': '⚙️ Settings',
        'info_button': '📖 Information',
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
Get beautiful reports with charts

📝 Feedback:
If you have questions or suggestions, write @SMF_support

🔬 Beta testing:
Thank you for participating in testing! Your feedback helps improve the bot.''',
        
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
        
        # Expense menu
        'spent_per_month': '💸 <b>Spent per month:</b>',
        'other_expenses': '📊 Other expenses',
        'show_other_period': '<i>Show report for another period?</i>',
        'no_data_for_report': '❌ <b>No data for report</b>\n\nNo expenses found for selected month.',
        'report_for_month': '📊 <b>Report for {month} {year}</b>',
        'report_contains': 'Report contains:\n• General expense statistics\n• Category distribution\n• Daily expense dynamics\n• Cashback information\n\n💡 <i>Tip: save the report to track expense dynamics</i>',
        'error_generating_report': '❌ <b>Error generating report</b>\n\nTry later or contact support.',
        'could_not_update_amount': '❌ Could not update amount',
        'could_not_update_description': '❌ Could not update description',
        'description_cannot_be_empty': '❌ Description cannot be empty',
        'could_not_recognize_amount': '❌ Could not recognize amount.\nPlease enter a number (e.g. 750 or 10.50):\n\n💡 Tip: To view expenses, use commands:\n• /expenses - today\'s expenses\n• "show expenses yesterday" - yesterday\'s expenses\n• "expenses for week" - weekly expenses',
        'want_to_add_expense': '💰 Do you want to add expense/income "{text}"?\n\nEnter amount:',
        'total_shown': '💰 <b>Total shown:</b>',
        'total_for_day': '💰 <b>Day total:</b>',
        'show_expenses_other_days': '\n<i>💡 Show expenses for other days?</i>',
        'diary_error': 'Error loading diary',
        'select_category_for_payment': '📁 Select category for payment:',
        'editing_payment': '✏️ <b>Editing payment</b>',
        'regular_payment': 'Regular payment',
        'payment_amount': 'Amount',
        'payment_date': 'Date',
        'payment_status': 'Status',
        'to_change_send': 'To change, send:',
        'only_amount': '• Amount only',
        'name_and_amount': '• Name and amount',
        
        # Referral program
        'get_referral_link': '🔗 Get referral link',
        'copy_link': '📋 Copy link',
        'my_statistics': '📊 My statistics',
        'referral_program_text': '🎁 <b>Referral Program</b>\n\nInvite friends and get bonuses!\n\nWhen a friend purchases their first plan, we extend your subscription for the same duration (once).\n\nPress the button below to get your personal link.',
        'your_referral_link': '🎁 <b>Your referral link</b>',
        'link_copied': '✅ Link copied!',
        'referral_statistics': '📊 <b>Your statistics</b>',
        'invited_friends': '👥 Friends invited',
        'with_subscription': '⭐ Bonuses granted',
        'earned_days': '🎁 Months rewarded',
        'referral_list': '📃 <b>Your referrals:</b>',
        'no_referrals_yet': 'You have no referrals yet',
        'invite_friends_bonus': 'Invite friends: the first paid plan extends your subscription!',
        'share_link': '📨 Share link',
        'select_month_for_pdf': '📊 <b>Select month for PDF report</b>\n\nI will generate a detailed report with charts and statistics.',
        'generating_report': '⏳ <b>Generating report...</b>\n\nThis may take a few seconds.',
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
        'profile_not_found': 'User profile not found',
        'no_category': 'No category',
        'unknown_period': 'Unknown period',
        'for': 'for',
        'from': 'from',
        'to': 'to',
        'expenses': 'Expenses',
        'expenses_count': 'expenses',
        'amount_for': 'for',
        'day_max_expenses': 'Day with maximum expenses',
        'category_statistics': 'Category statistics',
        'and_more': 'and more',
        'error': 'Error',
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
        
        # Recurring payments
        'recurring_payments': '🔄 Recurring payments',
        'recurring_menu': '🔄 Recurring payments',
        'no_recurring_payments': 'You have no recurring operations yet.',
        'recurring_income_section': '💰 <b>Income</b>',
        'recurring_expense_section': '💸 <b>Expenses</b>',
        'add_recurring': '➕ Add',
        'edit_recurring': '✏️ Edit',
        'delete_recurring': '➖ Delete',
        'add_recurring_payment': '➕ Adding recurring payment or income',
        'recurring_payment_hint': 'Send amount or name and amount:\n\nExamples:\n• <i>50000</i> - amount only (expense)\n• <i>Rent 50000</i> - name and amount (expense)\n• <i>+80000</i> - income\n• <i>Salary +80000</i> - name and income\n\nIf you don\'t specify a name, it will be created automatically from the category.',
        'choose_category_for_payment': '📁 Choose category for payment:',
        'choose_payment_day': '📅 Which day of the month to record the payment?\n\nChoose from the list or enter a number from 1 to 30:',
        'day_number': 'Day {day}',
        'recurring_payment_added': '✅ Recurring payment added',
        'choose_recurring_to_edit': '✏️ Choose payment to edit:',
        'choose_recurring_to_delete': '🗑 Choose payment to delete:',
        'editing_recurring': '✏️ Editing payment',
        'recurring_payment': 'Recurring payment',
        'status': 'Status',
        'active': 'Active ✅',
        'paused': 'Paused ⏸',
        'pause_payment': '⏸ Pause',
        'resume_payment': '▶️ Resume',
        'payment_status_changed': '✅ Payment status changed',
        'payment_deleted': '✅ Payment deleted',
        'day_of_month': 'Day {day} of month',
        'recurring_amount': 'Amount',
        'recurring_date': 'Date',
        'recurring_category': 'Category',
        'to_change_send': 'To change, send:\n• Amount only: <i>50000</i>\n• Name and amount: <i>Rent 50000</i>',
        'day_should_be_1_30': '❌ Day must be between 1 and 30',
        'enter_day_1_30': '❌ Enter a number between 1 and 30',
        'no_recurring_payments_to_edit': 'You have no recurring payments to edit',
        'no_recurring_payments_to_delete': 'You have no recurring payments to delete',
        'payment_not_found': 'Payment not found',
        'delete_payment_failed': '❌ Failed to delete payment',
        'edit_amount': '💰 Amount',
        'edit_description': '📝 Name',
        'edit_category': '📁 Category',
        'edit_day': '📅 Day',
        'enter_new_amount': '💰 Enter new amount:',
        'enter_new_description': '📝 Enter new name:',
        'choose_new_category': '📁 Choose new category:',
        'enter_new_day': '📅 Enter new day of month (1-30):',
        
        # Subscription
        'subscription': 'Subscription',
        'subscription_menu': '⭐ Subscription',
        'no_active_subscription': '❌ You have no active subscription',
        'subscription_benefits': 'With subscription you get:\n• Voice expense input\n• PDF reports with charts\n• Automatic reports\n• Custom categories\n• Cashback tracking\n• Recurring payments',
        'active_subscription': '✅ You have an active subscription',
        'subscription_type': 'Type',
        'trial_period': 'Trial period',
        'subscription_expires': 'Valid until',
        'subscription_history': '📜 Payment history',
        'buy_subscription': '💳 Pay',
        'referral_program': '🎁 Referral program',
        'back_to_subscription': 'Back to subscription menu',
        'invalid_subscription_type': 'Invalid subscription type',
        'subscription_advantages': '💎 Your subscription advantages:\n• Unlimited expenses\n• PDF reports\n• Voice input\n• Recurring payments\n• Cashback tracking',
        'you_received_days': 'You received {days} days of subscription',
        'subscription_valid_until': 'Subscription valid until: {date}',
        'promocode_activated': '✅ Promo code activated!',
        'friend_got_subscription': '🎉 Congratulations!\n\nYour friend purchased a subscription using your referral link.\nWe extended your subscription for the same duration as their first plan (one time).\n\nThank you for recommending us!',
        
        # Subscription menu texts
        'month_stars': '⭐ Monthly - 150 stars',
        'six_months_stars': '⭐ 6 months - 600 stars',
        'have_promocode': '🎟️ I have a promo code',
        'subscription_month_title': 'Monthly subscription',
        'subscription_month_desc': 'Full access to all features for 1 month',
        'subscription_six_months_title': '6-month subscription',
        'subscription_six_months_desc': 'Full access to all features for 6 months',
        'beta_tester_status': '🔬 <b>You have beta tester status</b>',
        'beta_access_text': 'You have full access to all bot features.\nThank you for participating in testing! 🙏',
        'active_subscription_text': 'You have an active subscription',
        'valid_until': 'Valid until',
        'days_left': 'Days left',
        'can_extend_early': 'You can extend your subscription in advance.',
        'enter_promocode': '🎟️ <b>Enter promo code</b>',
        'promocode_instruction': 'Send promo code to activate special offer:',
        'promocode_not_found': '❌ <b>Promo code not found</b>',
        'promocode_invalid': '❌ <b>Promo code is invalid</b>',
        'promocode_already_used': '❌ <b>You have already used this promo code</b>',
        'promocode_accepted': '✅ <b>Promo code accepted!</b>',
        'payment_successful': '✨ <b>Payment successful!</b>',
        'subscription_benefits_title': '💎 <b>Your subscription benefits:</b>',
        'unlimited_expenses': '• Unlimited expenses',
        'pdf_reports': '• PDF reports',
        'priority_support': '• Priority support',
        'thanks_support': 'Thank you for supporting the project! 💙',
        'subscription_required': '❌ <b>Subscription required</b>',
        'subscription_required_text': 'An active subscription is required to use this feature.\n\nPress the button below to get a subscription:',
        'get_subscription': '⭐ Get subscription',
        'back_to_menu': 'Back to subscription menu',
        
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
        'editing_expense': 'Editing expense',
        'choose_field_to_edit': 'Choose field to edit:',
        'choose_new_category': 'Choose new category',
        'learning_message': 'By changing the category you train the system, with each edit category selection becomes more accurate for you',
        'editing_amount': 'Editing amount',
        'enter_new_amount': 'Enter new amount:',
        'editing_description': 'Editing description',
        'enter_new_description': 'Enter new description:',
        'edit_done': 'Done',
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
        
        # Months
        'january': 'january',
        'february': 'february',
        'march': 'march',
        'april': 'april',
        'may': 'may',
        'june': 'june',
        'july': 'july',
        'august': 'august',
        'september': 'september',
        'october': 'october',
        'november': 'november',
        'december': 'december',
        
        # Voice messages
        'voice_too_long': '⚠️ Voice message is too long. Maximum 60 seconds.',
        'voice_download_error': '❌ Error downloading voice message',
        'voice_recognition_error': '❌ Failed to recognize speech.\nTry speaking more clearly or send a text message.',
        'recognized': '📝 Recognized: {text}',

        # Help
        # Old help text (commented)
        # 'help_main_text': '''<b>📖 Bot Usage Help</b>
        #
        # <b>🚀 Quick Start:</b>
        # Just send a message with expense: "coffee 200" or "taxi 500"
        # The bot will automatically determine the category and save the expense.
        #
        # <b>💸 How to record expenses:</b>
        # • Text: "groceries 1500", "gas 3000"
        # • With date: "yesterday coffee 200", "10.09 lunch 450"
        # • Voice: send a voice message
        #
        # <b>💰 How to record income:</b>
        # • Add plus sign: "+50000 salary", "bonus +10000"
        # • Or use menu "➕ Income"
        #
        # <b>📊 Reports:</b>
        # • "show expenses for July"
        # • "how much spent on groceries"
        # • "monthly report"
        #
        # <b>💳 Cashbacks:</b>
        # Set up cards with cashbacks in "💳 Cashbacks" menu.
        # The bot will automatically calculate benefits for each category.
        #
        # <b>🏠 Household Budget:</b>
        # Create a household in settings and track finances together.
        # All members see shared expenses and income.
        #
        # <b>⚙️ Useful commands:</b>
        # • /start - main menu
        # • /help - this help
        # • /cashback - cashback setup
        # • /report - request report
        # • /settings - settings
        #
        # <b>💡 Tips:</b>
        # • Pin cashback message for quick access
        # • Use voice messages on the go
        # • Add expenses immediately to not forget''',

        # New help text
        'help_main_text': '''<b>📖 Bot Usage Help</b>

<b>💸 Recording expenses/income:</b>
You can type or send a voice message.
Examples:
• Expense: "Taxi 550", "Coffee 200"
• Income: "+3500 order" (sign "+" = income)

The bot will make a record and respond to you. By pressing the "Edit" button, you can change any record parameters.

Edit the category - the bot will remember which category your expense belongs to and will insert the category correctly next time.

You can enter expense/income without amount in one word if you already had a similar record - the bot will take all information from the previous record.

You can make a record retroactively - for this, write the date at the end of the expense in the format 23.09.2025

<b>💳 Cashback:</b>
Cashback can be entered through the menu, or by message to the bot in the format:
"cashback X% category XXXX bank"

Pin the note with cashbacks in the chat with the bot for quick access.

<b>💬 Natural language questions to the bot:</b>
Ask the bot about your finances in simple words:
• "How much did I spend on groceries this month?"
• "How much did I spend on coffee in August?"
• "What's my biggest expense this week?"
• "How much did I earn in September?"
• "What do I spend the most money on?"

The bot understands natural language and will help analyze your finances.''',

        # Recurring payments translations
        'no_categories_create_first': '❌ You have no categories. Please create categories first.',
        'to_categories': '📁 To Categories',
        'select_payment_category': '📁 Select payment category:',
        'select_payment_to_edit': '✏️ Select payment to edit:',
        'payment_not_found': 'Payment not found',
        'payment_active': 'Active ✅',
        'payment_paused': 'Paused ⏸',
        'pause_payment': '⏸ Pause',
        'resume_payment': '▶️ Resume',
        'edit_payment_text': '✏️ <b>Edit Payment</b>\n\nRecurring payment: <i>{description}</i>\nAmount: <i>{amount}</i>\nCategory: <i>{category}</i>\nDate: <i>Day {day} of month</i>\nStatus: <i>{status}</i>\n\nTo change, send:\n• Amount only: <i>50000</i>\n• Name and amount: <i>Apartment 50000</i>',
        'payment_status_changed': '✅ Payment status changed',
        'select_payment_to_delete': '🗑 Select payment to delete:',
        'payment_deleted': '✅ Payment deleted',
        'payment_delete_failed': '❌ Failed to delete payment',
        
        # Referral program translations
        'get_referral_link': '🔗 Get Referral Link',
        'copy_link': '📋 Copy Link',
        'my_statistics': '📊 My Statistics',
        'referral_program_text': '🎁 <b>Referral Program</b>\n\nInvite friends and get bonuses!\n\nWhen a friend subscribes for the first time, we extend your access for the same duration (one time).\n\nClick the button below to get your personal link.',
        'referral_your_program': '🎁 <b>Your Referral Program</b>\n\nYour link:\n<code>{link}</code>\n\n📊 Statistics:\nFriends invited: {total_referrals}\nBonuses granted: {rewarded_referrals}\nWaiting for first payment: {pending_referrals}\nTotal months rewarded: {rewarded_months}\n\nThe first paid plan of a friend extends your subscription for the same duration (one time).',
        'referral_subscription_required': 'Referral program is only available with an active subscription',
        'referral_link_created': '✅ Referral link created!',
        'create_referral_first': 'Please create a referral link first',
        'your_referral_link': '<b>Your referral link:</b>\n\n<code>{link}</code>\n\nClick on the link to copy it.',
        'link_sent_for_copy': '📋 Link sent for copying',
        'referral_stats_title': '📊 <b>Detailed Referral Statistics</b>',
        'no_referrals_yet': 'You have no invited friends yet.',
        'active_subscription': '✅ Active subscription',
        'waiting_subscription': '⏳ Waiting for subscription',
        'bonus_received': ' (bonus received)',
        'referral_sub_required_full': '❌ Referral program is only available with an active subscription.\nSubscribe to start inviting friends!',
        
        # PDF Report translations
        'select_month_pdf': '📊 <b>Select month for PDF report</b>\n\nI will generate a detailed report with charts and statistics for you.',
        'generating_report': '⏳ <b>Generating report...</b>\n\nThis may take a few seconds.',
        'pdf_report_caption': '📊 <b>Report for {month} {year}</b>\n\nThe report contains:\n• Overall expense statistics\n• Distribution by categories\n• Daily spending dynamics\n• Cashback information\n\n💡 <i>Tip: save the report to track expense dynamics</i>',
        'report_generation_error': '❌ <b>Error generating report</b>\n\nPlease try later or contact support.',
        
        # Cashback translations
        'cashbacks_for': 'Cashbacks for',
        'limit': 'limit',
        'cashbacks': 'Cashbacks',
        'no_cashback_info': 'No cashback information for this month',
        'add_cashback_hint': 'Click "Add" to set up cashback',
        'add_cashback': '➕ Add',
        'remove_cashback': '➖ Remove',
        'remove_all_cashback': '🗑 Remove All',
        
        # Categories translations
        'manage_categories': '<b>Category Management</b>',
        'no_categories_yet': 'You have no categories yet',
        'categories_subscription_note': 'Category management is available with subscription',
        'get_subscription': 'Get Subscription',
        'adding_category': '<b>Adding Category</b>\n\nEnter category name (e.g., "Food", "Transport"):',
        'add_button': '➕ Add',
        'edit_button': '✏️ Edit',
        'delete_button': '➖ Delete',
    }
}


def get_text(key: str, lang: str = 'ru') -> str:
    """Получить текст по ключу и языку"""
    return TEXTS.get(lang, TEXTS['ru']).get(key, key)
