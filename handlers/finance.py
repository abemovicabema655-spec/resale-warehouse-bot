from aiogram import F, Router
from aiogram.types import Message
from database.db import get_finance_stats
from keyboards.menus import back_inline_keyboard

router = Router()

@router.message(F.text == "💰 Финансы")
async def show_finance(message: Message) -> None:
    try:
        user_id = message.from_user.id
        stats = await get_finance_stats(user_id)
        text = (
            f"💰 Финансовый отчёт:\n"
            f"• Выручка: {stats['revenue']:.2f} ₽\n"
            f"• Себестоимость проданных товаров: {stats['cost']:.2f} ₽\n"
            f"• Прибыль: {stats['profit']:.2f} ₽\n"
            f"• Количество продаж: {stats['sold_count']}"
        )
        await message.answer(text, reply_markup=back_inline_keyboard())
    except Exception as e:
        await message.answer(f"⚠️ Не удалось загрузить финансы: {e}")