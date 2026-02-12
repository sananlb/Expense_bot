#!/bin/bash

# Настройка DOCKER-USER правил iptables для блокировки прямого доступа к контейнерам
# Это defense-in-depth: даже если docker-compose.yml имеет ports без 127.0.0.1,
# внешний трафик к портам 8000/8001 будет заблокирован на уровне iptables.
#
# Использование: sudo bash scripts/setup_docker_firewall.sh
#
# ВАЖНО: Эти правила не переживают перезагрузку сервера!
# Для постоянного эффекта установите systemd unit: docker-firewall.service

set -euo pipefail

GREEN='\033[0;32m'
RED='\033[0;31m'
YELLOW='\033[1;33m'
NC='\033[0m'

# Проверка прав
if [ "$(id -u)" -ne 0 ]; then
    echo -e "${RED}❌ Этот скрипт требует root-прав. Запустите: sudo bash $0${NC}"
    exit 1
fi

echo -e "${YELLOW}🔒 Настройка DOCKER-USER firewall правил...${NC}"
echo ""

# Получаем имя внешнего сетевого интерфейса
EXT_IFACE=$(ip route get 8.8.8.8 | grep -oP 'dev \K\S+' | head -1)
echo -e "${YELLOW}  Внешний интерфейс: ${EXT_IFACE}${NC}"

# Удаляем ТОЛЬКО наши правила (если существуют), не трогая чужие
echo -e "${YELLOW}  Удаляю старые правила для портов 8000/8001...${NC}"
iptables -D DOCKER-USER -i "$EXT_IFACE" -p tcp --dport 8000 -j DROP 2>/dev/null || true
iptables -D DOCKER-USER -i "$EXT_IFACE" -p tcp --dport 8001 -j DROP 2>/dev/null || true
# Повторяем на случай дублей
iptables -D DOCKER-USER -i "$EXT_IFACE" -p tcp --dport 8000 -j DROP 2>/dev/null || true
iptables -D DOCKER-USER -i "$EXT_IFACE" -p tcp --dport 8001 -j DROP 2>/dev/null || true

# Добавляем наши правила в начало цепочки
iptables -I DOCKER-USER -i "$EXT_IFACE" -p tcp --dport 8000 -j DROP
echo -e "${GREEN}  ✓ Заблокирован внешний доступ к порту 8000 (web)${NC}"

iptables -I DOCKER-USER -i "$EXT_IFACE" -p tcp --dport 8001 -j DROP
echo -e "${GREEN}  ✓ Заблокирован внешний доступ к порту 8001 (bot)${NC}"

echo ""
echo -e "${GREEN}✅ DOCKER-USER правила настроены:${NC}"
iptables -L DOCKER-USER -n -v --line-numbers
echo ""
echo -e "${YELLOW}⚠️  Правила действуют до перезагрузки сервера.${NC}"
echo -e "${YELLOW}   Для постоянного эффекта установите systemd unit:${NC}"
echo -e "${YELLOW}   sudo cp scripts/docker-firewall.service /etc/systemd/system/${NC}"
echo -e "${YELLOW}   sudo systemctl daemon-reload && sudo systemctl enable docker-firewall.service${NC}"
echo ""

# Проверка
echo -e "${YELLOW}🔍 Верификация: проверяю что порты закрыты для внешнего доступа...${NC}"
DOCKER_USER_8000=$(iptables -L DOCKER-USER -n | grep "dpt:8000" | grep "DROP" || true)
DOCKER_USER_8001=$(iptables -L DOCKER-USER -n | grep "dpt:8001" | grep "DROP" || true)

if [ -n "$DOCKER_USER_8000" ] && [ -n "$DOCKER_USER_8001" ]; then
    echo -e "${GREEN}✅ Оба порта (8000, 8001) защищены правилами DOCKER-USER${NC}"
else
    echo -e "${RED}❌ Не все правила применены! Проверьте вручную: iptables -L DOCKER-USER -n${NC}"
    exit 1
fi
