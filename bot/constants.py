"""
Глобальные константы и ссылки (с возможностью переопределения через окружение)
"""
import os

# Приоритет источников ссылок:
# 1) TELEGRAPH_*_URL (если опубликовано в Telegraph)
# 2) PRIVACY_URL / OFFER_URL (адрес лендинга — задаётся на сервере)
# 3) Значение по умолчанию (заглушка)

# Используем адреса лендинга (если заданы), иначе — Telegraph, иначе — заглушку
PRIVACY_URL_RU = (
    os.getenv('PRIVACY_URL')
    or os.getenv('TELEGRAPH_PRIVACY_URL')
    or 'https://www.coins-bot.ru/privacy.html'
)
PRIVACY_URL_EN = (
    os.getenv('PRIVACY_URL_EN')
    or os.getenv('TELEGRAPH_PRIVACY_URL_EN')
    or 'https://www.coins-bot.ru/privacy_en.html'
)

OFFER_URL_RU = (
    os.getenv('OFFER_URL')
    or os.getenv('TELEGRAPH_OFFER_URL')
    or 'https://www.coins-bot.ru/offer.html'
)
OFFER_URL_EN = (
    os.getenv('OFFER_URL_EN')
    or os.getenv('TELEGRAPH_OFFER_URL_EN')
    or 'https://www.coins-bot.ru/offer_en.html'
)

def get_privacy_url_for(lang: str | None) -> str:
    """Вернёт ссылку на политику с учётом языка пользователя."""
    l = (lang or 'en').lower()
    return PRIVACY_URL_RU if l.startswith('ru') else PRIVACY_URL_EN

def get_offer_url_for(lang: str | None) -> str:
    """Вернёт ссылку на оферту с учётом языка пользователя."""
    l = (lang or 'en').lower()
    return OFFER_URL_RU if l.startswith('ru') else OFFER_URL_EN
