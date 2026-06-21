"""
Group Chat Guard Middleware — привратник для групп/супергрупп.

В группах (group/supergroup) бот должен игнорировать обычную переписку и реагировать
ТОЛЬКО на явный bang-ввод («!кофе 200») или обращение к текущему боту
(«@username кофе 200»). Этот привратник дропает slash-команды, остальную болтовню и медиа до обращения
к БД, AI и парсингу.

ИСКЛЮЧЕНИЕ: обычное (без «/») текстовое сообщение ПРОПУСКАЕТСЯ, если отправитель прямо сейчас
в FSM-состоянии редактирования СВОЕЙ записи (правка суммы/описания) — иначе edit-шаги с вводом
текста в группе не сработают.

Доступ к FSM-состоянию и порядок регистрации:
    В aiogram 3.x ``FSMContextMiddleware`` зарегистрирован как outer-middleware на уровне
    наблюдателя ``update`` (Dispatcher), т.е. ВЫШЕ любых message-middleware — он кладёт
    ``data['state']`` (и ``data['raw_state']``) ещё до того, как начинают работать message-level
    middleware (как outer, так и inner). Поэтому ``data['state']`` гарантированно доступен в этом
    привратнике независимо от того, outer он или inner.

    Регистрируем привратник ПЕРВЫМ обычным ``dp.message.middleware()`` — раньше
    ``PrivacyCheckMiddleware`` (которому тоже нужен ``data['state']``) и раньше
    ``DatabaseMiddleware``. Так гард (a) срабатывает ДО privacy-чека и (b) не требует доступа к БД
    (отбрасывает мусор до того, как мы открываем соединение). См. wiring в ``bot/main.py``.
"""
import logging
from typing import Any, Awaitable, Callable, Dict

from aiogram import BaseMiddleware
from aiogram.fsm.context import FSMContext
from aiogram.types import Message

from bot.utils.group_input import extract_leading_bot_mention_payload

logger = logging.getLogger(__name__)

# Типы групповых чатов, где действует привратник
GROUP_CHAT_TYPES = frozenset({"group", "supergroup"})

# FSM-состояния редактирования СВОЕЙ записи, где ожидается ТЕКСТОВЫЙ ввод (без «/»).
# Только для них в группе пропускаем обычный текст, иначе edit-шаги не работают.
# См. ExpenseForm / EditExpenseForm в bot/routers/expense.py.
EDIT_TEXT_INPUT_STATES = frozenset({
    "EditExpenseForm:editing_amount",
    "EditExpenseForm:editing_description",
    "ExpenseForm:waiting_for_amount_clarification",
})


class GroupChatGuardMiddleware(BaseMiddleware):
    """Пропускает bang-ввод, прямой mention бота и edit-текст владельца."""

    async def __call__(
        self,
        handler: Callable[[Message, Dict[str, Any]], Awaitable[Any]],
        event: Message,
        data: Dict[str, Any],
    ) -> Any:
        # Привратник навешан только на dp.message, но проверяем тип на всякий случай.
        if not isinstance(event, Message):
            return await handler(event, data)

        chat = event.chat
        if chat is None or chat.type not in GROUP_CHAT_TYPES:
            # Личка/канал — поведение не меняем.
            return await handler(event, data)

        # Анонимные админы / sender_chat шлют сообщения с from_user is None. Если пустить их
        # дальше, ранние мидлвари (rate_limit) упадут на event.from_user.id ДО проверки в
        # group_router. Поэтому в группах такие сообщения дропаем здесь (тихо).
        if event.from_user is None:
            logger.debug(
                "[GroupGuard] dropped group message without from_user in chat_type=%s",
                chat.type,
            )
            return None

        text = event.text
        if text is not None and text.startswith("/"):
            # Slash-ввод в группах не поддерживаем. Дропаем здесь, чтобы приватные
            # command-хендлеры не отправили личные меню/данные в общий чат.
            return None

        if text is not None and text.startswith("!"):
            # Явный короткий ввод — пропускаем в group_router.
            return await handler(event, data)

        if text is not None and text.startswith("@"):
            try:
                bot_username = (await event.bot.me()).username
            except Exception as e:  # noqa: BLE001 - при ошибке безопасно дропаем mention
                logger.warning("[GroupGuard] failed to resolve bot username: %s", e)
                return None

            if extract_leading_bot_mention_payload(text, bot_username) is not None:
                # Явное обращение именно к этому боту — пропускаем в group_router.
                return await handler(event, data)

            # Mention другого бота не должен доходить до наших обработчиков.
            return None

        # Обычный текст без «/» пропускаем ТОЛЬКО если отправитель в edit-состоянии своей записи.
        if text is not None:
            current_state = await self._get_current_state(data)
            if current_state in EDIT_TEXT_INPUT_STATES:
                return await handler(event, data)

        # Всё остальное (болтовня, медиа, медиа с подписью) — дроп, не вызывая handler.
        logger.debug(
            "[GroupGuard] dropped non-explicit group message in chat_type=%s (has_text=%s)",
            chat.type,
            text is not None,
        )
        return None

    @staticmethod
    async def _get_current_state(data: Dict[str, Any]) -> str | None:
        """Возвращает текущее FSM-состояние строкой, без обращения к БД."""
        # raw_state кладётся FSMContextMiddleware вместе с state — используем без лишнего I/O.
        if "raw_state" in data:
            return data.get("raw_state")
        state: FSMContext | None = data.get("state")
        if state is None:
            return None
        return await state.get_state()
