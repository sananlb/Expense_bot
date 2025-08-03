"""
Обработчик категорий
"""
from aiogram import Router, types
from aiogram.filters import Command

router = Router(name="category")


@router.message(Command("categories"))
async def cmd_categories(message: types.Message):
    """Команда /categories"""
    # TODO: Показать список категорий пользователя
    await message.answer("🚧 Раздел категорий в разработке")


# TODO: Реализовать callback_query для categories_menu
# TODO: Реализовать добавление категории
# TODO: Реализовать удаление категории
# TODO: Реализовать редактирование категории


