from aiogram import F, Router
from aiogram.filters import Command
from aiogram.types import Message, CallbackQuery, InlineKeyboardMarkup, InlineKeyboardButton

from database.db import (
    register_user,
    get_dashboard_stats,
    get_archived_items,
    unarchive_item,
    get_sales_history,
    get_sales_history_count,
    undo_sale,
)
from keyboards.menus import main_menu_keyboard, back_inline_keyboard
from utils.formatters import format_warehouse
import logging

logger = logging.getLogger(__name__)
router = Router()

# ===================================================
# === СТАРТ ===
# ===================================================

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


# ===================================================
# === ИСТОРИЯ ПРОДАЖ (исправлено) ===
# ===================================================

PERIODS = {
    "day": "Сегодня",
    "week": "Неделя",
    "month": "Месяц",
    "all": "Всё время",
}

def _build_history_keyboard(page: int, total_pages: int, period: str) -> InlineKeyboardMarkup:
    buttons = []
    # Кнопки фильтров
    row = []
    for key, label in PERIODS.items():
        row.append(InlineKeyboardButton(
            text=f"{label} ✅" if key == period else label,
            callback_data=f"history:filter:{key}"
        ))
    buttons.append(row)

    # Пагинация
    nav = []
    if page > 0:
        nav.append(InlineKeyboardButton(
            text="⬅️",
            callback_data=f"history:page:{page-1}:{period}"
        ))
    nav.append(InlineKeyboardButton(
        text=f"{page+1}/{total_pages if total_pages > 0 else 1}",
        callback_data="ignore"
    ))
    if page + 1 < total_pages:
        nav.append(InlineKeyboardButton(
            text="➡️",
            callback_data=f"history:page:{page+1}:{period}"
        ))
    buttons.append(nav)

    buttons.append([InlineKeyboardButton(text="🔙 Назад", callback_data="back:menu")])
    return InlineKeyboardMarkup(inline_keyboard=buttons)


@router.message(F.text == "📋 История продаж")
async def sales_history(message: Message) -> None:
    await _show_history_page(message, page=0, period="all")


@router.callback_query(F.data.startswith("history:"))
async def history_callback(callback: CallbackQuery) -> None:
    parts = callback.data.split(":")
    action = parts[1]

    if action == "filter":
        period = parts[2]
        await _show_history_page(callback.message, page=0, period=period, is_callback=True)
        await callback.answer()

    elif action == "page":
        page = int(parts[2])
        period = parts[3]
        await _show_history_page(callback.message, page=page, period=period, is_callback=True)
        await callback.answer()

    elif action == "undo":
        sale_id = int(parts[2])
        user_id = callback.from_user.id
        success, msg = await undo_sale(user_id, sale_id)
        if not success:
            await callback.answer(msg, show_alert=True)
            return
        await callback.answer(msg)
        # После отмены обновляем текущую страницу (возвращаемся на первую)
        await _show_history_page(callback.message, page=0, period="all", is_callback=True)

    elif action == "ignore":
        await callback.answer()


async def _show_history_page(
    source: Message | CallbackQuery,
    page: int,
    period: str,
    is_callback: bool = False,
):
    user_id = source.from_user.id if isinstance(source, Message) else source.from_user.id

    try:
        limit = 10
        offset = page * limit
        total = await get_sales_history_count(user_id, period)
        total_pages = (total + limit - 1) // limit if total > 0 else 1

        sales = await get_sales_history(user_id, limit, offset, period)

        if not sales:
            text = "📋 Продаж за выбранный период нет."
            keyboard = _build_history_keyboard(page, total_pages, period)
            if is_callback:
                await source.edit_text(text, reply_markup=keyboard)
            else:
                await source.answer(text, reply_markup=keyboard)
            return

        # Группировка по дням
        grouped = {}
        for sale in sales:
            date_key = sale["sold_at"].strftime("%Y-%m-%d")
            if date_key not in grouped:
                grouped[date_key] = {
                    "date": sale["sold_at"].strftime("%d %B %Y"),
                    "sales": []
                }
            grouped[date_key]["sales"].append(sale)

        text = "📋 *История продаж*\n"
        text += f"Фильтр: {PERIODS.get(period, 'Всё время')}\n\n"

        total_revenue = 0
        total_profit = 0
        count = 0

        for date_key, group in grouped.items():
            text += f"📅 *{group['date']}*\n"
            for sale in group["sales"]:
                time_str = sale["sold_at"].strftime("%H:%M")
                name = sale["name"]
                size = sale["size"]
                price = sale["price"]
                purchase_price = sale["purchase_price"]
                profit = price - purchase_price
                total_revenue += price
                total_profit += profit
                count += 1
                text += (
                    f"   {time_str} — {name} ({size}) — "
                    f"💰 {price:,.2f} ₽ (прибыль +{profit:,.2f} ₽)\n"
                )

        text += f"\n📊 *Итого за показанный период:*\n"
        text += f"   Выручка: {total_revenue:,.2f} ₽\n"
        text += f"   Прибыль: {total_profit:,.2f} ₽\n"
        text += f"   Продаж: {count}"

        keyboard = _build_history_keyboard(page, total_pages, period)

        if is_callback:
            await source.edit_text(text, reply_markup=keyboard, parse_mode="Markdown")
        else:
            await source.answer(text, reply_markup=keyboard, parse_mode="Markdown")

    except Exception as exc:
        logger.exception("Ошибка загрузки истории продаж: %s", exc)
        error_text = "⚠️ Не удалось загрузить историю продаж."
        if is_callback:
            await source.edit_text(error_text, reply_markup=back_inline_keyboard())
        else:
            await source.answer(error_text, reply_markup=back_inline_keyboard())