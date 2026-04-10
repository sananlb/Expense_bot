import logging
import os
import socket
import ssl
from typing import Optional

import aiohttp
import certifi
from aiogram import Bot
from aiogram.client.default import DefaultBotProperties
from aiogram.client.session.aiohttp import AiohttpSession
from aiogram.enums import ParseMode

logger = logging.getLogger(__name__)


def _get_telegram_proxy() -> Optional[str]:
    """Получить URL прокси для Telegram из переменных окружения."""
    return os.getenv("TELEGRAM_PROXY", "").strip() or None


def should_force_telegram_ipv4() -> bool:
    value = os.getenv("TELEGRAM_FORCE_IPV4", "")
    return value.strip().lower() in {"1", "true", "yes", "on"}


def create_telegram_session() -> AiohttpSession:
    proxy = _get_telegram_proxy()

    if proxy:
        session = AiohttpSession(proxy=proxy)
        logger.info("Telegram session created with proxy")
    else:
        session = AiohttpSession()

    if should_force_telegram_ipv4():
        session._connector_init["family"] = socket.AF_INET
        session._connector_init["ttl_dns_cache"] = 0

    return session


def create_telegram_bot(
    token: Optional[str] = None,
    *,
    parse_mode: Optional[str] = None,
) -> Bot:
    bot_token = token or os.getenv("BOT_TOKEN") or os.getenv("TELEGRAM_BOT_TOKEN")
    if not bot_token:
        raise ValueError("Bot token not found in environment variables")

    kwargs = {"session": create_telegram_session()}
    if parse_mode is not None:
        kwargs["default"] = DefaultBotProperties(parse_mode=cast_parse_mode(parse_mode))

    return Bot(token=bot_token, **kwargs)


def create_telegram_http_session(timeout_seconds: int = 10) -> aiohttp.ClientSession:
    proxy = _get_telegram_proxy()
    timeout = aiohttp.ClientTimeout(total=timeout_seconds)

    if proxy:
        # Для SOCKS5 прокси используем ProxyConnector из aiohttp_socks
        try:
            from aiohttp_socks import ProxyConnector
            connector = ProxyConnector.from_url(
                proxy,
                ssl=ssl.create_default_context(cafile=certifi.where()),
            )
            logger.info("Telegram HTTP session created with proxy")
            return aiohttp.ClientSession(connector=connector, timeout=timeout)
        except ImportError:
            logger.warning("aiohttp-socks not installed, proxy ignored for HTTP session")

    connector_kwargs = {
        "ssl": ssl.create_default_context(cafile=certifi.where()),
    }

    if should_force_telegram_ipv4():
        connector_kwargs["family"] = socket.AF_INET
        connector_kwargs["ttl_dns_cache"] = 0

    connector = aiohttp.TCPConnector(**connector_kwargs)
    return aiohttp.ClientSession(connector=connector, timeout=timeout)


def cast_parse_mode(parse_mode: str) -> ParseMode:
    if isinstance(parse_mode, ParseMode):
        return parse_mode
    return ParseMode(parse_mode)
