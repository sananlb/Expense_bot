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


def should_force_telegram_ipv4() -> bool:
    value = os.getenv("TELEGRAM_FORCE_IPV4", "")
    return value.strip().lower() in {"1", "true", "yes", "on"}


def create_telegram_session() -> AiohttpSession:
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
    timeout = aiohttp.ClientTimeout(total=timeout_seconds)

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
