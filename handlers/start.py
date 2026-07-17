from aiogram import F, Router
from aiogram.filters import Command
from aiogram.types import Message

from database.db import register_user
from keyboards.menus import main_menu_keyboard

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