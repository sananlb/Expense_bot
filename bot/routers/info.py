"""
Обработчик информации о боте
"""
from aiogram import Router, types
from aiogram.filters import Command
from aiogram.types import InlineKeyboardButton, InlineKeyboardMarkup

router = Router(name="info")


# Info functionality is now merged with /start command