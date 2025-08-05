#!/bin/bash
# Скрипт настройки SSH пользователя с sudo правами и отключения root доступа

set -e

# Цвета для вывода
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m'

# Проверка, что скрипт запущен от root
if [ "$EUID" -ne 0 ]; then 
    echo -e "${RED}Этот скрипт должен быть запущен от root!${NC}"
    exit 1
fi

echo -e "${BLUE}======================================"
echo "  Настройка SSH пользователя"
echo -e "======================================${NC}"
echo ""

# Запрос имени пользователя
read -p "Введите имя нового пользователя (по умолчанию: deploy): " USERNAME
USERNAME=${USERNAME:-deploy}

# Проверка существования пользователя
if id "$USERNAME" &>/dev/null; then
    echo -e "${YELLOW}Пользователь $USERNAME уже существует${NC}"
    read -p "Продолжить с существующим пользователем? (y/n): " -n 1 -r
    echo
    if [[ ! $REPLY =~ ^[Yy]$ ]]; then
        exit 1
    fi
else
    # Создание пользователя
    echo -e "${GREEN}Создание пользователя $USERNAME...${NC}"
    adduser --gecos "" $USERNAME
fi

# Добавление пользователя в sudo группу
echo -e "${GREEN}Добавление пользователя в sudo группу...${NC}"
usermod -aG sudo $USERNAME

# Создание SSH директории
USER_HOME="/home/$USERNAME"
SSH_DIR="$USER_HOME/.ssh"

echo -e "${GREEN}Настройка SSH директории...${NC}"
mkdir -p "$SSH_DIR"
chmod 700 "$SSH_DIR"
chown -R $USERNAME:$USERNAME "$SSH_DIR"

# Копирование SSH ключей от root (если есть)
if [ -f "/root/.ssh/authorized_keys" ]; then
    echo -e "${GREEN}Копирование SSH ключей...${NC}"
    cp /root/.ssh/authorized_keys "$SSH_DIR/"
    chmod 600 "$SSH_DIR/authorized_keys"
    chown $USERNAME:$USERNAME "$SSH_DIR/authorized_keys"
else
    echo -e "${YELLOW}SSH ключи не найдены в /root/.ssh/${NC}"
    echo "Создайте файл $SSH_DIR/authorized_keys и добавьте туда ваш публичный ключ"
fi

# Настройка sudo без пароля (опционально)
echo -e "${GREEN}Настройка sudo...${NC}"
echo "Выберите режим sudo для пользователя $USERNAME:"
echo "1) Требовать пароль для sudo (рекомендуется)"
echo "2) Не требовать пароль для sudo"
read -p "Ваш выбор (1-2): " SUDO_CHOICE

if [ "$SUDO_CHOICE" = "2" ]; then
    echo "$USERNAME ALL=(ALL) NOPASSWD:ALL" > /etc/sudoers.d/$USERNAME
    chmod 0440 /etc/sudoers.d/$USERNAME
    echo -e "${GREEN}Настроен sudo без пароля${NC}"
else
    echo -e "${GREEN}Пользователь будет вводить пароль для sudo${NC}"
fi

# Настройка SSH конфигурации
echo -e "${GREEN}Настройка SSH сервера...${NC}"

# Бэкап текущей конфигурации
cp /etc/ssh/sshd_config /etc/ssh/sshd_config.bak.$(date +%Y%m%d_%H%M%S)

# Функция для изменения параметра в sshd_config
update_sshd_config() {
    local key=$1
    local value=$2
    
    # Удаляем существующие строки с этим параметром
    sed -i "/^#*\s*$key/d" /etc/ssh/sshd_config
    
    # Добавляем новое значение
    echo "$key $value" >> /etc/ssh/sshd_config
}

# Отключение входа по паролю (рекомендуется)
echo ""
read -p "Отключить вход по паролю (только SSH ключи)? (y/n): " -n 1 -r
echo
if [[ $REPLY =~ ^[Yy]$ ]]; then
    update_sshd_config "PasswordAuthentication" "no"
    update_sshd_config "ChallengeResponseAuthentication" "no"
    echo -e "${GREEN}Вход по паролю отключен${NC}"
fi

# Отключение root логина
echo ""
echo -e "${YELLOW}ВНИМАНИЕ: Следующий шаг отключит SSH доступ для root!${NC}"
echo "Убедитесь, что вы можете войти как пользователь $USERNAME"
read -p "Отключить SSH доступ для root? (y/n): " -n 1 -r
echo
if [[ $REPLY =~ ^[Yy]$ ]]; then
    update_sshd_config "PermitRootLogin" "no"
    echo -e "${GREEN}Root SSH доступ будет отключен после перезапуска SSH${NC}"
    ROOT_DISABLED=true
else
    echo -e "${YELLOW}Root SSH доступ оставлен включенным${NC}"
    ROOT_DISABLED=false
fi

# Дополнительные настройки безопасности
update_sshd_config "Protocol" "2"
update_sshd_config "ClientAliveInterval" "300"
update_sshd_config "ClientAliveCountMax" "2"

# Создание скрипта для финальной настройки
cat > /tmp/finalize_ssh_setup.sh << 'EOF'
#!/bin/bash
# Финальная настройка SSH

echo "Перезапуск SSH сервиса..."
systemctl restart sshd

echo ""
echo "======================================"
echo "  Настройка завершена!"
echo "======================================"
echo ""
echo "ВАЖНО:"
echo "1. Проверьте SSH доступ для пользователя: $USERNAME"
echo "2. НЕ ЗАКРЫВАЙТЕ текущую SSH сессию!"
echo "3. Откройте НОВОЕ SSH подключение и войдите как: $USERNAME"
echo "4. Убедитесь, что sudo работает: sudo -i"
echo ""
if [ "$ROOT_DISABLED" = "true" ]; then
    echo "⚠️  Root SSH доступ ОТКЛЮЧЕН!"
    echo "   Убедитесь, что можете войти как $USERNAME перед закрытием этой сессии!"
fi
echo ""
echo "Для проверки статуса SSH:"
echo "  systemctl status sshd"
echo ""
echo "В случае проблем, конфигурация сохранена в:"
echo "  /etc/ssh/sshd_config.bak.*"
EOF

chmod +x /tmp/finalize_ssh_setup.sh

# Установка переменных в скрипт
sed -i "s/\$USERNAME/$USERNAME/g" /tmp/finalize_ssh_setup.sh
sed -i "s/\$ROOT_DISABLED/$ROOT_DISABLED/g" /tmp/finalize_ssh_setup.sh

echo ""
echo -e "${GREEN}Подготовка завершена!${NC}"
echo ""
echo "Для завершения настройки выполните:"
echo -e "${YELLOW}  /tmp/finalize_ssh_setup.sh${NC}"
echo ""
echo "Это перезапустит SSH сервис с новыми настройками."
echo ""

# Создание инструкции для пользователя
cat > "$USER_HOME/ssh_setup_info.txt" << EOF
SSH Setup Information
=====================

Username: $USERNAME
Home Directory: $USER_HOME
SSH Directory: $SSH_DIR

SSH Connection:
  ssh $USERNAME@<server-ip>

Sudo Usage:
  sudo command     # Выполнить команду с правами root
  sudo -i          # Переключиться на root пользователя

Important Files:
  ~/.ssh/authorized_keys    # Ваши SSH ключи
  /etc/ssh/sshd_config      # SSH конфигурация сервера

Security Notes:
- Root SSH access: $([ "$ROOT_DISABLED" = "true" ] && echo "DISABLED" || echo "ENABLED")
- Password authentication: Check /etc/ssh/sshd_config
- Sudo requires password: $([ "$SUDO_CHOICE" = "2" ] && echo "NO" || echo "YES")

Created: $(date)
EOF

chown $USERNAME:$USERNAME "$USER_HOME/ssh_setup_info.txt"

echo -e "${BLUE}Информация сохранена в: $USER_HOME/ssh_setup_info.txt${NC}"