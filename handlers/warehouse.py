import logging

from aiogram import F, Router
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
from aiogram.types import CallbackQuery, Message

from database.db import (
    get_warehouse_items,
    replenish_stock,
    sell_item,
    delete_size,
    update_price,
    search_warehouse_items,
    archive_item,
    check_low_stock,          # <-- добавлен импорт
)
from keyboards.menus import (
    back_inline_keyboard,
    cancel_inline_keyboard,
    main_menu_keyboard,
    warehouse_keyboard,
)
from states.purchase import ReplenishStates, SearchStates
from utils.formatters import format_warehouse

logger = logging.getLogger(__name__)
router = Router()


class EditPriceStates(StatesGroup):
    waiting_for_new_price = State()


async def _render_warehouse_message(items: list[dict]) -> tuple[str, object]:
    text = format_warehouse(items)
    keyboard = warehouse_keyboard(items) if items else back_inline_keyboard()
    return text, keyboard


@router.message(F.text == "📦 Склад")
async def show_warehouse(message: Message) -> None:
    try:
        user_id = message.from_user.id
        items = await get_warehouse_items(user_id)
        text, keyboard = await _render_warehouse_message(items)
        await message.answer(text, reply_markup=keyboard, parse_mode="HTML")
    except Exception as exc:
        logger.exception("Ошибка раздела склад: %s", exc)
        await message.answer("⚠️ Не удалось загрузить склад.")


@router.callback_query(F.data.startswith("sell:"))
async def process_sell(callback: CallbackQuery) -> None:
    try:
        user_id = callback.from_user.id
        _, item_id_str, size = callback.data.split(":", 2)
        success, msg = await sell_item(user_id, int(item_id_str), size)

        if not success:
            await callback.answer(msg, show_alert=True)
            return

        items = await get_warehouse_items(user_id)
        text, keyboard = await _render_warehouse_message(items)
        await callback.message.edit_text(text, reply_markup=keyboard, parse_mode="HTML")
        await callback.answer("✅ Продажа зафиксирована")

        # === УМНОЕ УВЕДОМЛЕНИЕ ===
        low = await check_low_stock(user_id)
        if low:
            text = "⚠️ *Внимание! Заканчиваются товары:*\n\n"
            for item in low:
                text += f"• {item['name']} (размер {item['size']}) — осталось {item['quantity']} шт. (порог {item['threshold']})\n"
            await callback.message.answer(text, parse_mode="Markdown")

    except Exception as exc:
        logger.exception("Ошибка продажи: %s", exc)
        await callback.answer("⚠️ Ошибка при продаже", show_alert=True)


@router.callback_query(F.data.startswith("replenish:"))
async def start_replenish(callback: CallbackQuery, state: FSMContext) -> None:
    try:
        user_id = callback.from_user.id
        _, item_id_str, size = callback.data.split(":", 2)
        await state.set_state(ReplenishStates.quantity)
        await state.update_data(user_id=user_id, item_id=int(item_id_str), size=size)
        await callback.answer()
        await callback.message.answer(
            f"➕ <b>Пополнение</b>\n\n"
            f"Размер: <b>{size}</b>\n"
            "Введите количество для добавления:",
            reply_markup=cancel_inline_keyboard(),
            parse_mode="HTML",
        )
    except Exception as exc:
        logger.exception("Ошибка начала пополнения: %s", exc)
        await callback.answer("⚠️ Ошибка", show_alert=True)


@router.message(ReplenishStates.quantity)
async def process_replenish(message: Message, state: FSMContext) -> None:
    try:
        user_id = message.from_user.id
        text = (message.text or "").strip()
        if not text.isdigit() or int(text) <= 0:
            await message.answer(
                "⚠️ Введите целое положительное число:",
                reply_markup=cancel_inline_keyboard(),
            )
            return

        data = await state.get_data()
        item_id = data.get("item_id")
        size = data.get("size")
        if not item_id or not size:
            await state.clear()
            await message.answer(
                "⚠️ Сессия пополнения устарела. Откройте склад заново.",
                reply_markup=main_menu_keyboard(),
            )
            return

        success, msg = await replenish_stock(user_id, item_id, size, int(text))
        await state.clear()

        if not success:
            await message.answer(f"⚠️ {msg}", reply_markup=main_menu_keyboard())
            return

        items = await get_warehouse_items(user_id)
        warehouse_text, keyboard = await _render_warehouse_message(items)
        await message.answer(
            f"✅ {msg}\n\n{warehouse_text}",
            reply_markup=keyboard,
            parse_mode="HTML",
        )
    except Exception as exc:
        logger.exception("Ошибка пополнения: %s", exc)
        await state.clear()
        await message.answer(
            "⚠️ Не удалось пополнить остаток.",
            reply_markup=main_menu_keyboard(),
        )


@router.callback_query(F.data.startswith("delete:"))
async def delete_size_callback(callback: CallbackQuery) -> None:
    try:
        user_id = callback.from_user.id
        _, item_id_str, size = callback.data.split(":", 2)
        item_id = int(item_id_str)

        success, msg = await delete_size(user_id, item_id, size)
        if not success:
            await callback.answer(msg, show_alert=True)
            return

        items = await get_warehouse_items(user_id)
        text, keyboard = await _render_warehouse_message(items)
        await callback.message.edit_text(text, reply_markup=keyboard, parse_mode="HTML")
        await callback.answer(f"✅ {msg}")
    except Exception as exc:
        logger.exception("Ошибка удаления размера: %s", exc)
        await callback.answer("⚠️ Не удалось удалить размер", show_alert=True)


@router.callback_query(F.data.startswith("edit_price:"))
async def edit_price_callback(callback: CallbackQuery, state: FSMContext) -> None:
    try:
        user_id = callback.from_user.id
        _, item_id_str = callback.data.split(":", 1)
        item_id = int(item_id_str)
        await state.update_data(user_id=user_id, item_id=item_id)
        await state.set_state(EditPriceStates.waiting_for_new_price)
        await callback.answer()
        await callback.message.answer(
            "✏️ Введите новую цену продажи (только число, например 2500):",
            reply_markup=cancel_inline_keyboard(),
        )
    except Exception as exc:
        logger.exception("Ошибка начала изменения цены: %s", exc)
        await callback.answer("⚠️ Ошибка", show_alert=True)


@router.message(EditPriceStates.waiting_for_new_price)
async def process_new_price(message: Message, state: FSMContext) -> None:
    try:
        user_id = message.from_user.id
        text = (message.text or "").strip()
        try:
            new_price = float(text)
            if new_price < 0:
                raise ValueError
        except ValueError:
            await message.answer(
                "⚠️ Введите положительное число (например, 1500):",
                reply_markup=cancel_inline_keyboard(),
            )
            return

        data = await state.get_data()
        item_id = data.get("item_id")
        if not item_id:
            await state.clear()
            await message.answer(
                "⚠️ Сессия устарела. Откройте склад заново.",
                reply_markup=main_menu_keyboard(),
            )
            return

        success, msg = await update_price(user_id, item_id, new_price)
        await state.clear()

        if not success:
            await message.answer(f"⚠️ {msg}", reply_markup=main_menu_keyboard())
            return

        items = await get_warehouse_items(user_id)
        warehouse_text, keyboard = await _render_warehouse_message(items)
        await message.answer(
            f"✅ {msg}\n\n{warehouse_text}",
            reply_markup=keyboard,
            parse_mode="HTML",
        )
    except Exception as exc:
        logger.exception("Ошибка обновления цены: %s", exc)
        await state.clear()
        await message.answer(
            "⚠️ Не удалось обновить цену.",
            reply_markup=main_menu_keyboard(),
        )


# ===================================================
# === ПОИСК ===
# ===================================================

@router.callback_query(F.data == "warehouse:search")
async def start_search(callback: CallbackQuery, state: FSMContext) -> None:
    await state.set_state(SearchStates.waiting_for_query)
    await callback.answer()
    await callback.message.answer(
        "🔍 Введите название товара для поиска:",
        reply_markup=cancel_inline_keyboard()
    )


@router.message(SearchStates.waiting_for_query)
async def process_search(message: Message, state: FSMContext) -> None:
    try:
        user_id = message.from_user.id
        query = message.text.strip()
        if not query:
            await message.answer(
                "⚠️ Введите название.",
                reply_markup=cancel_inline_keyboard()
            )
            return

        items = await search_warehouse_items(user_id, query)
        if not items:
            await message.answer(
                "🔍 Ничего не найдено.",
                reply_markup=back_inline_keyboard()
            )
            await state.clear()
            return

        text, keyboard = await _render_warehouse_message(items)
        await message.answer(
            text,
            reply_markup=keyboard,
            parse_mode="HTML"
        )
        await state.clear()
    except Exception as e:
        logger.exception("Ошибка поиска: %s", e)
        await message.answer(
            "⚠️ Не удалось выполнить поиск.",
            reply_markup=back_inline_keyboard()
        )
        await state.clear()


# ===================================================
# === АРХИВИРОВАТЬ ТОВАР ===
# ===================================================

@router.callback_query(F.data.startswith("archive:"))
async def archive_item_callback(callback: CallbackQuery) -> None:
    try:
        user_id = callback.from_user.id
        _, item_id_str = callback.data.split(":", 1)
        item_id = int(item_id_str)

        success, msg = await archive_item(user_id, item_id)
        if not success:
            await callback.answer(msg, show_alert=True)
            return

        items = await get_warehouse_items(user_id)
        text, keyboard = await _render_warehouse_message(items)
        await callback.message.edit_text(text, reply_markup=keyboard, parse_mode="HTML")
        await callback.answer(f"✅ {msg}")
    except Exception as exc:
        logger.exception("Ошибка архивации: %s", exc)
        await callback.answer("⚠️ Не удалось переместить товар в архив", show_alert=True)


# ===================================================
# === ОБРАБОТЧИК ОТМЕНЫ ===
# ===================================================

@router.callback_query(F.data == "cancel:dialog")
async def cancel_dialog(callback: CallbackQuery, state: FSMContext) -> None:
    await state.clear()
    await callback.answer("Действие отменено")
    await callback.message.delete()
    await callback.message.answer(
        "❌ Отменено.",
        reply_markup=main_menu_keyboard()
    )