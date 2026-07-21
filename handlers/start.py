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
    reset_user_data,
    get_warehouse_items,
    set_threshold,
)
from keyboards.menus import main_menu_keyboard, back_inline_keyboard, cancel_inline_keyboard
from utils.formatters import format_warehouse
from states.purchase import ResetStates, ThresholdStates
from aiogram.fsm.context import FSMContext
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
        "⚠️ *ВНИМАНИЕ: РАННИЙ ДОСТУП!*\n\n"
        "Этот бот находится в стадии активной разработки и тестирования.\n"
        "Некоторые функции могут работать нестабильно, а данные могут быть сброшены без предупреждения.\n"
        "Мы делаем всё, чтобы сделать его удобным и надёжным, но пока просим отнестись с пониманием.\n\n"
        "👋 Привет! Я бот для учёта склада (ресейл).\n"
        "Твои данные сохраняются только для тебя.\n\n"
        "Выбери действие в меню:",
        reply_markup=main_menu_keyboard(),
        parse_mode="Markdown"
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
# === ИСТОРИЯ ПРОДАЖ ===
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
    print("📋 Нажата кнопка 'История продаж'")
    await _show_history_page(message, page=0, period="all", user_id=message.from_user.id)


@router.callback_query(F.data.startswith("history:"))
async def history_callback(callback: CallbackQuery) -> None:
    print(f"🔍 history_callback: data={callback.data}")
    parts = callback.data.split(":")
    action = parts[1]

    if action == "filter":
        period = parts[2]
        print(f"🔍 Фильтр: {period}")
        await _show_history_page(callback, page=0, period=period, is_callback=True)
        await callback.answer()

    elif action == "page":
        page = int(parts[2])
        period = parts[3]
        print(f"🔍 Страница: {page}, период: {period}")
        await _show_history_page(callback, page=page, period=period, is_callback=True)
        await callback.answer()

    elif action == "undo":
        sale_id = int(parts[2])
        user_id = callback.from_user.id
        success, msg = await undo_sale(user_id, sale_id)
        if not success:
            await callback.answer(msg, show_alert=True)
            return
        await callback.answer(msg)
        await _show_history_page(callback, page=0, period="all", is_callback=True)

    elif action == "ignore":
        await callback.answer()


async def _show_history_page(
    source: Message | CallbackQuery,
    page: int,
    period: str,
    is_callback: bool = False,
    user_id: int = None,
):
    if user_id is None:
        if is_callback:
            user_id = source.from_user.id
        else:
            user_id = source.from_user.id

    print(f"🔍 _show_history_page: user_id={user_id}, page={page}, period={period}, is_callback={is_callback}")

    try:
        limit = 10
        offset = page * limit
        total = await get_sales_history_count(user_id, period)
        print(f"🔍 total count = {total}")
        total_pages = (total + limit - 1) // limit if total > 0 else 1

        sales = await get_sales_history(user_id, limit, offset, period)
        print(f"🔍 получили {len(sales)} продаж")

        if not sales:
            text = "📋 Продаж за выбранный период нет."
            keyboard = _build_history_keyboard(page, total_pages, period)
            if is_callback:
                await source.message.edit_text(text, reply_markup=keyboard)
            else:
                await source.answer(text, reply_markup=keyboard)
            return

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
            await source.message.edit_text(text, reply_markup=keyboard, parse_mode="Markdown")
        else:
            await source.answer(text, reply_markup=keyboard, parse_mode="Markdown")

    except Exception as exc:
        print(f"❌ Ошибка в _show_history_page: {exc}")
        logger.exception("Ошибка загрузки истории продаж: %s", exc)
        error_text = "⚠️ Не удалось загрузить историю продаж."
        if is_callback:
            await source.message.edit_text(error_text, reply_markup=back_inline_keyboard())
        else:
            await source.answer(error_text, reply_markup=back_inline_keyboard())


# ===================================================
# === ОБНУЛЕНИЕ ===
# ===================================================

@router.message(F.text == "🗑️ Обнулить всё")
async def reset_confirm(message: Message, state: FSMContext) -> None:
    await state.set_state(ResetStates.confirm)
    await message.answer(
        "⚠️ *Вы уверены, что хотите полностью обнулить склад и статистику?*\n\n"
        "Это действие *необратимо*! Все товары, продажи и финансы будут удалены.\n\n"
        "Напишите *«Да»* для подтверждения или *«Нет»* для отмены.",
        parse_mode="Markdown"
    )

@router.message(ResetStates.confirm)
async def reset_execute(message: Message, state: FSMContext) -> None:
    user_id = message.from_user.id
    answer = message.text.strip().lower()

    if answer == "да":
        success, msg = await reset_user_data(user_id)
        await message.answer(msg, reply_markup=main_menu_keyboard())
    elif answer == "нет":
        await message.answer("❌ Обнуление отменено.", reply_markup=main_menu_keyboard())
    else:
        await message.answer(
            "⚠️ Пожалуйста, напишите *«Да»* или *«Нет»*.",
            parse_mode="Markdown"
        )
        return
    await state.clear()


# ===================================================
# === УМНЫЕ УВЕДОМЛЕНИЯ (настройка порогов) ===
# ===================================================

@router.message(F.text == "🔔 Умные уведомления")
async def show_thresholds(message: Message) -> None:
    try:
        user_id = message.from_user.id
        items = await get_warehouse_items(user_id)
        if not items:
            await message.answer(
                "📦 У вас пока нет товаров на складе.\n"
                "Сначала добавьте товары через «➕ Новая закупка».",
                reply_markup=back_inline_keyboard()
            )
            return

        text = "🔔 *Настройка умных уведомлений*\n\n"
        text += "_Порог — это минимальное количество товара, при котором бот пришлёт уведомление, что товар заканчивается._\n\n"

        keyboard = []
        for item in items:
            item_id = item["item_id"]
            name = item["name"]
            threshold = item.get("threshold", 3)
            text += f"• *{name}*\n"
            text += f"   Текущий порог: {threshold} шт.\n\n"
            keyboard.append([
                InlineKeyboardButton(
                    text=f"✏️ Изменить порог для {name}",
                    callback_data=f"set_threshold:{item_id}"
                )
            ])

        keyboard.append([InlineKeyboardButton(text="🔙 Назад", callback_data="back:menu")])
        await message.answer(text, reply_markup=InlineKeyboardMarkup(inline_keyboard=keyboard), parse_mode="Markdown")
    except Exception as exc:
        logger.exception("Ошибка загрузки порогов: %s", exc)
        await message.answer("⚠️ Не удалось загрузить настройки уведомлений.")


@router.callback_query(F.data.startswith("set_threshold:"))
async def start_set_threshold(callback: CallbackQuery, state: FSMContext) -> None:
    try:
        _, item_id_str = callback.data.split(":", 1)
        item_id = int(item_id_str)
        await state.update_data(item_id=item_id)
        await state.set_state(ThresholdStates.waiting_for_value)
        await callback.answer()
        await callback.message.answer(
            "✏️ Введите новый порог для этого товара (целое число):\n\n"
            "Например: *3* — значит, когда останется 3 или меньше штук, вы получите уведомление.",
            reply_markup=cancel_inline_keyboard(),
            parse_mode="Markdown"
        )
    except Exception as exc:
        logger.exception("Ошибка начала настройки порога: %s", exc)
        await callback.answer("⚠️ Ошибка", show_alert=True)


@router.message(ThresholdStates.waiting_for_value)
async def process_set_threshold(message: Message, state: FSMContext) -> None:
    try:
        user_id = message.from_user.id
        text = message.text.strip()
        if not text.isdigit() or int(text) < 0:
            await message.answer(
                "⚠️ Введите целое неотрицательное число (например, 3).",
                reply_markup=cancel_inline_keyboard()
            )
            return
        threshold = int(text)
        data = await state.get_data()
        item_id = data.get("item_id")
        if not item_id:
            await state.clear()
            await message.answer(
                "⚠️ Сессия устарела. Попробуйте снова.",
                reply_markup=main_menu_keyboard()
            )
            return
        success, msg = await set_threshold(user_id, item_id, threshold)
        await state.clear()
        if not success:
            await message.answer(f"⚠️ {msg}", reply_markup=main_menu_keyboard())
            return
        await show_thresholds(message)
    except Exception as exc:
        logger.exception("Ошибка установки порога: %s", exc)
        await state.clear()
        await message.answer(
            "⚠️ Не удалось установить порог.",
            reply_markup=main_menu_keyboard()
        )


# ===================================================
# === ИНФОРМАЦИЯ О БОТЕ ===
# ===================================================

@router.message(F.text == "ℹ️ О боте")
async def about_bot(message: Message) -> None:
    text = (
        "ℹ️ *О боте «Stocky 0.1»*\n\n"
        "🤖 *Что это:*\n"
        "Бот для учёта склада реселлеров. Помогает отслеживать товары, продажи, прибыль и остатки.\n\n"
        "⚙️ *Технологии:*\n"
        "• Язык: Python 3.14\n"
        "• Фреймворк: aiogram 3.x\n"
        "• База данных: PostgreSQL (Neon)\n"
        "• Хостинг: Render\n\n"
        "🔒 *Безопасность:*\n"
        "• Данные каждого пользователя изолированы (только вы видите свой склад).\n"
        "• Подключение к БД защищено SSL.\n\n"
        "📦 *Функции:*\n"
        "• Добавление, продажа, пополнение товаров\n"
        "• История продаж с фильтрами\n"
        "• Архив и восстановление\n"
        "• Умные уведомления о низких остатках\n"
        "• Поиск по складу\n\n"
        "👨‍💻 *Разработчик:*\n"
        "@acneev\n\n"
        "📩 *Обратная связь:*\n"
        "Все пожелания, недочеты, баги и ошибки сообщайте сюда: @acneev\n\n"
        "🔄 *Статус:*\n"
        "Ранний доступ (бот активно дорабатывается)."
    )
    await message.answer(text, reply_markup=back_inline_keyboard(), parse_mode="Markdown")