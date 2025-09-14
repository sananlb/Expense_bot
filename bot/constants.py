"""
Глобальные константы и ссылки (с возможностью переопределения через окружение)
"""
import os

# Приоритет источников ссылок:
# 1) TELEGRAPH_*_URL (если опубликовано в Telegraph)
# 2) PRIVACY_URL / OFFER_URL (адрес лендинга — задаётся на сервере)
# 3) Значение по умолчанию (заглушка)

# Используем адреса лендинга (если заданы), иначе — Telegraph, иначе — заглушку
PRIVACY_URL = (
    os.getenv('PRIVACY_URL')
    or os.getenv('TELEGRAPH_PRIVACY_URL')
    or 'https://example.com/privacy.html'
)

OFFER_URL = (
    os.getenv('OFFER_URL')
    or os.getenv('TELEGRAPH_OFFER_URL')
    or 'https://example.com/offer.html'
)
