from aiogram import F, Router
from aiogram.filters import Command
from aiogram.types import Message, CallbackQuery, InlineKeyboardMarkup, InlineKeyboardButton

from database.db import register_user, get_dashboard_stats, get_archived_items, unarchive_item
from keyboards.menus import main_menu_keyboard, back_inline_keyboard
from utils.formatters import format_warehouse

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
        await message.answer(f"⚠️ Ошибка: {e}")


@router.callback_query(F.data == "back:menu")
async def back_to_menu(callback: CallbackQuery):
    await callback.message.delete()
    await callback.message.answer("Главное меню:", reply_markup=main_menu_keyboard())
    await callback.answer()


# ===================================================
# === АРХИВ ===
# ===================================================

@router.message(F.text == "📂 Архив")
async def show_archive(message: Message) -> None:
    try:
        user_id = message.from_user.id
        items = await get_archived_items(user_id)
        if not items:
            await message.answer(
                "📂 Архив пуст.",
                reply_markup=back_inline_keyboard()
            )
            return

        text = format_warehouse(items)
        keyboard = _build_archive_keyboard(items)
        await message.answer(text, reply_markup=keyboard, parse_mode="HTML")
    except Exception as exc:
        logger.exception("Ошибка загрузки архива: %s", exc)
        await message.answer("⚠️ Не удалось загрузить архив.")


def _build_archive_keyboard(items: list[dict]) -> InlineKeyboardMarkup:
    buttons = []
    for item in items:
        item_id = item["item_id"]
        buttons.append([
            InlineKeyboardButton(
                text=f"↩️ Восстановить {item['name']}",
                callback_data=f"unarchive:{item_id}"
            )
        ])
    buttons.append([InlineKeyboardButton(text="🔙 Назад", callback_data="back:menu")])
    return InlineKeyboardMarkup(inline_keyboard=buttons)


@router.callback_query(F.data.startswith("unarchive:"))
async def unarchive_item_callback(callback: CallbackQuery) -> None:
    try:
        user_id = callback.from_user.id
        _, item_id_str = callback.data.split(":", 1)
        item_id = int(item_id_str)

        success, msg = await unarchive_item(user_id, item_id)
        if not success:
            await callback.answer(msg, show_alert=True)
            return

        items = await get_archived_items(user_id)
        if not items:
            await callback.message.edit_text(
                "📂 Архив пуст.",
                reply_markup=back_inline_keyboard()
            )
            await callback.answer(f"✅ {msg}")
            return

        text = format_warehouse(items)
        keyboard = _build_archive_keyboard(items)
        await callback.message.edit_text(text, reply_markup=keyboard, parse_mode="HTML")
        await callback.answer(f"✅ {msg}")
    except Exception as exc:
        logger.exception("Ошибка восстановления из архива: %s", exc)
        await callback.answer("⚠️ Не удалось восстановить товар", show_alert=True)