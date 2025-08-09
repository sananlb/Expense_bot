#!/bin/bash

# Скрипт для добавления удобных алиасов в .bashrc

echo "Добавление алиасов для ExpenseBot..."

# Добавляем алиасы в .bashrc если их еще нет
if ! grep -q "# ExpenseBot aliases" ~/.bashrc; then
    cat >> ~/.bashrc << 'EOF'

# ExpenseBot aliases
alias bot-update='cd ~/expense_bot && ./scripts/update.sh'
alias bot-logs='cd ~/expense_bot && docker-compose logs -f'
alias bot-web-logs='cd ~/expense_bot && docker logs expense_bot_web -f'
alias bot-app-logs='cd ~/expense_bot && docker logs expense_bot_app -f'
alias bot-restart='cd ~/expense_bot && docker-compose restart'
alias bot-stop='cd ~/expense_bot && docker-compose stop'
alias bot-start='cd ~/expense_bot && docker-compose start'
alias bot-status='cd ~/expense_bot && docker-compose ps'
alias bot-shell='cd ~/expense_bot && docker exec -it expense_bot_web python manage.py shell'
alias bot-admin='cd ~/expense_bot && docker exec -it expense_bot_web python manage.py createsuperuser'
EOF
    echo "✅ Алиасы добавлены в .bashrc"
    echo ""
    echo "Теперь доступны команды:"
    echo "  bot-update     - Обновить бота из GitHub"
    echo "  bot-logs       - Смотреть все логи"
    echo "  bot-web-logs   - Логи веб-сервера"
    echo "  bot-app-logs   - Логи бота"
    echo "  bot-restart    - Перезапустить бота"
    echo "  bot-stop       - Остановить бота"
    echo "  bot-start      - Запустить бота"
    echo "  bot-status     - Статус контейнеров"
    echo "  bot-shell      - Django shell"
    echo "  bot-admin      - Создать админа"
    echo ""
    echo "Выполните: source ~/.bashrc"
    echo "Или перезайдите в SSH сессию"
else
    echo "✅ Алиасы уже настроены"
fi