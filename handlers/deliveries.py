import logging

from aiogram import F, Router
from aiogram.types import Message

from keyboards.menus import back_inline_keyboard

logger = logging.getLogger(__name__)
router = Router()


@router.message(F.text == "🚚 Поставки")
async def show_deliveries(message: Message) -> None:
    try:
        await message.answer(
            "🚚 <b>Поставки</b>\n\nРаздел «Поставки» в разработке.",
            reply_markup=back_inline_keyboard(),
            parse_mode="HTML",
        )
    except Exception as exc:
        logger.exception("Ошибка раздела поставки: %s", exc)
        await message.answer("⚠️ Не удалось открыть раздел «Поставки».")
