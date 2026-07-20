from aiogram import F, Router
from aiogram.types import Message, CallbackQuery
from database.db import get_dashboard_stats
from keyboards.menus import main_menu_keyboard, back_inline_keyboard

router = Router()

@router.message(F.text == "📦 Главный экран")
async def main_screen(message: Message) -> None:
    try:
        user_id = message.from_user.id
        stats = await get_dashboard_stats(user_id)
        text = (
            f"📦 Остаток на складе: {stats['total_stock']} шт.\n"
            f"💰 Прибыль за всё время: {stats['profit']:.2f} ₽\n"
            f"📈 Продано товаров: {stats['sold_count']}\n"
            f"Выручка: {stats['revenue']:.2f} ₽\n"
            f"Себестоимость: {stats['cost']:.2f} ₽"
        )
        await message.answer(text, reply_markup=back_inline_keyboard())
    except Exception as e:
        await message.answer(f"⚠️ Ошибка: {e}")

@router.callback_query(F.data == "back:menu")
async def back_to_menu(callback: CallbackQuery):
    await callback.message.delete()
    await callback.message.answer("Главное меню:", reply_markup=main_menu_keyboard())
    await callback.answer()