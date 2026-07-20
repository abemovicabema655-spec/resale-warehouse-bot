from aiogram import F, Router
from aiogram.filters import Command
from aiogram.types import Message

from database.db import register_user, get_dashboard_stats
from keyboards.menus import main_menu_keyboard, back_inline_keyboard

router = Router()

@router.message(Command("start"))
async def start(message: Message) -> None:
    user_id = message.from_user.id
    username = message.from_user.username or "Нет юзернейма"
    first_name = message.from_user.first_name or ""
    last_name = message.from_user.last_name or ""

    await register_user(user_id, username, first_name, last_name)

    await message.answer(
        "👋 Привет! Я бот для учёта склада (ресейл).\n"
        "Твои данные сохраняются только для тебя.\n\n"
        "Выбери действие в меню:",
        reply_markup=main_menu_keyboard(),
    )

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
        await message.answer(f"⚠️ Ошибка загрузки главного экрана: {e}")