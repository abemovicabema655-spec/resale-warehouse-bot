from aiogram import F, Router
from aiogram.types import Message
from database.db import get_statistics
from keyboards.menus import back_inline_keyboard

router = Router()

@router.message(F.text == "📈 Статистика")
async def show_statistics(message: Message) -> None:
    try:
        user_id = message.from_user.id
        stats = await get_statistics(user_id)
        text = (
            f"📊 Статистика продаж:\n"
            f"• Всего продано: {stats['sold_count']} шт.\n"
            f"• Общая выручка: {stats['revenue']:.2f} ₽\n"
            f"• Средняя цена продажи: {stats['avg_price']:.2f} ₽"
        )
        await message.answer(text, reply_markup=back_inline_keyboard())
    except Exception as e:
        await message.answer(f"⚠️ Не удалось загрузить статистику: {e}")
    