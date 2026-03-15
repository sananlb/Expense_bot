import os
from decimal import Decimal

DEFAULT_CURRENCY_CODE = "RUB"
DEFAULT_LANGUAGE_CODE = "ru"

ONE_YEAR_DAYS = 365
MAX_DAILY_OPERATIONS = 100
MAX_OPERATION_DESCRIPTION_LENGTH = 500
MAX_TRANSACTION_AMOUNT = Decimal("9999999999.99")

_DEFAULT_PRIVACY_URLS = {
    "ru": "https://www.coins-bot.ru/privacy.html",
    "en": "https://www.coins-bot.ru/privacy_en.html",
}

_DEFAULT_OFFER_URLS = {
    "ru": "https://www.coins-bot.ru/offer.html",
    "en": "https://www.coins-bot.ru/offer_en.html",
}


def _normalize_lang(lang: str | None) -> str:
    return "en" if lang == "en" else DEFAULT_LANGUAGE_CODE


def get_privacy_url_for(lang: str | None = None) -> str:
    normalized_lang = _normalize_lang(lang)
    env_key = f"PRIVACY_POLICY_URL_{normalized_lang.upper()}"
    return os.getenv(env_key, _DEFAULT_PRIVACY_URLS[normalized_lang])


def get_offer_url_for(lang: str | None = None) -> str:
    normalized_lang = _normalize_lang(lang)
    env_key = f"PUBLIC_OFFER_URL_{normalized_lang.upper()}"
    return os.getenv(env_key, _DEFAULT_OFFER_URLS[normalized_lang])
