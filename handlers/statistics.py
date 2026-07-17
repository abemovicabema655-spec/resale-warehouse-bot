import logging

from aiogram import F, Router
from aiogram.types import Message

from database.db import get_statistics
from keyboards.menus import back_inline_keyboard
from utils.formatters import format_statistics

logger = logging.getLogger(__name__)
router = Router()


@router.message(F.text == "📈 Статистика")
async def show_statistics(message: Message) -> None:
    try:
        stats = await get_statistics()
        await message.answer(
            format_statistics(stats),
            reply_markup=back_inline_keyboard(),
            parse_mode="HTML",
        )
    except Exception as exc:
        logger.exception("Ошибка раздела статистика: %s", exc)
        await message.answer("⚠️ Не удалось загрузить статистику.")
