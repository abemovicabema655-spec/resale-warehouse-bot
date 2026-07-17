import logging

from aiogram import F, Router
from aiogram.types import Message

from database.db import get_finance_stats
from keyboards.menus import back_inline_keyboard
from utils.formatters import format_finance

logger = logging.getLogger(__name__)
router = Router()


@router.message(F.text == "💰 Финансы")
async def show_finance(message: Message) -> None:
    try:
        stats = await get_finance_stats()
        await message.answer(
            format_finance(stats),
            reply_markup=back_inline_keyboard(),
            parse_mode="HTML",
        )
    except Exception as exc:
        logger.exception("Ошибка раздела финансы: %s", exc)
        await message.answer("⚠️ Не удалось загрузить финансовый отчёт.")
