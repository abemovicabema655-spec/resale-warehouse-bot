import logging

from aiogram import F, Router
from aiogram.fsm.context import FSMContext
from aiogram.types import CallbackQuery, Message

from database.db import add_purchase
from keyboards.menus import cancel_inline_keyboard, main_menu_keyboard
from states.purchase import PurchaseStates
from utils.formatters import format_item_card

logger = logging.getLogger(__name__)
router = Router()


@router.message(F.text == "➕ Новая закупка")
async def start_purchase(message: Message, state: FSMContext) -> None:
    try:
        await state.set_state(PurchaseStates.name)
        await message.answer(
            "➕ <b>Новая закупка</b>\n\n"
            "Шаг 1 из 5.\n"
            "Введите название товара:",
            reply_markup=cancel_inline_keyboard(),
            parse_mode="HTML",
        )
    except Exception as exc:
        logger.exception("Ошибка начала закупки: %s", exc)
        await message.answer("⚠️ Не удалось начать добавление товара.")


@router.message(PurchaseStates.name)
async def process_name(message: Message, state: FSMContext) -> None:
    try:
        name = (message.text or "").strip()
        if not name:
            await message.answer(
                "⚠️ Название не может быть пустым. Введите название товара:",
                reply_markup=cancel_inline_keyboard(),
            )
            return

        await state.update_data(name=name)
        await state.set_state(PurchaseStates.size)
        await message.answer(
            "Шаг 2 из 5.\n"
            "Введите размер (например: 42, M, XL):",
            reply_markup=cancel_inline_keyboard(),
        )
    except Exception as exc:
        logger.exception("Ошибка ввода названия: %s", exc)
        await message.answer("⚠️ Ошибка обработки. Попробуйте снова.")


@router.message(PurchaseStates.size)
async def process_size(message: Message, state: FSMContext) -> None:
    try:
        size = (message.text or "").strip()
        if not size:
            await message.answer(
                "⚠️ Размер не может быть пустым. Введите размер:",
                reply_markup=cancel_inline_keyboard(),
            )
            return

        await state.update_data(size=size)
        await state.set_state(PurchaseStates.quantity)
        await message.answer(
            "Шаг 3 из 5.\n"
            "Введите количество (целое положительное число):",
            reply_markup=cancel_inline_keyboard(),
        )
    except Exception as exc:
        logger.exception("Ошибка ввода размера: %s", exc)
        await message.answer("⚠️ Ошибка обработки. Попробуйте снова.")


@router.message(PurchaseStates.quantity)
async def process_quantity(message: Message, state: FSMContext) -> None:
    try:
        text = (message.text or "").strip()
        if not text.isdigit() or int(text) <= 0:
            await message.answer(
                "⚠️ Введите целое положительное число:",
                reply_markup=cancel_inline_keyboard(),
            )
            return

        await state.update_data(quantity=int(text))
        await state.set_state(PurchaseStates.purchase_price)
        await message.answer(
            "Шаг 4 из 5.\n"
            "Введите цену закупки (число):",
            reply_markup=cancel_inline_keyboard(),
        )
    except Exception as exc:
        logger.exception("Ошибка ввода количества: %s", exc)
        await message.answer("⚠️ Ошибка обработки. Попробуйте снова.")


@router.message(PurchaseStates.purchase_price)
async def process_purchase_price(message: Message, state: FSMContext) -> None:
    try:
        text = (message.text or "").strip().replace(",", ".")
        try:
            price = float(text)
            if price < 0:
                raise ValueError
        except ValueError:
            await message.answer(
                "⚠️ Введите корректное число (цена закупки):",
                reply_markup=cancel_inline_keyboard(),
            )
            return

        await state.update_data(purchase_price=price)
        await state.set_state(PurchaseStates.sale_price)
        await message.answer(
            "Шаг 5 из 5.\n"
            "Введите цену продажи (число):",
            reply_markup=cancel_inline_keyboard(),
        )
    except Exception as exc:
        logger.exception("Ошибка ввода цены закупки: %s", exc)
        await message.answer("⚠️ Ошибка обработки. Попробуйте снова.")


@router.message(PurchaseStates.sale_price)
async def process_sale_price(message: Message, state: FSMContext) -> None:
    try:
        user_id = message.from_user.id
        text = (message.text or "").strip().replace(",", ".")
        try:
            price = float(text)
            if price < 0:
                raise ValueError
        except ValueError:
            await message.answer(
                "⚠️ Введите корректное число (цена продажи):",
                reply_markup=cancel_inline_keyboard(),
            )
            return

        data = await state.get_data()
        item = await add_purchase(
            user_id=user_id,                     # <-- добавили user_id
            name=data["name"],
            size=data["size"],
            quantity=data["quantity"],
            purchase_price=data["purchase_price"],
            sale_price=price,
        )
        await state.clear()

        await message.answer(
            format_item_card(item),
            reply_markup=main_menu_keyboard(),
            parse_mode="HTML",
        )
    except Exception as exc:
        logger.exception("Ошибка сохранения закупки: %s", exc)
        await state.clear()
        await message.answer(
            "⚠️ Не удалось сохранить товар. Попробуйте снова.",
            reply_markup=main_menu_keyboard(),
        )


@router.callback_query(F.data == "cancel:dialog")
async def cancel_dialog(callback: CallbackQuery, state: FSMContext) -> None:
    try:
        await state.clear()
        await callback.answer("Диалог отменён")
        await callback.message.edit_text(
            "❌ Добавление товара отменено.\n\n"
            "Выберите раздел в меню ниже.",
        )
        await callback.message.answer(
            "🏠 Главное меню",
            reply_markup=main_menu_keyboard(),
        )
    except Exception as exc:
        logger.exception("Ошибка отмены диалога: %s", exc)
        await state.clear()
        await callback.answer("Диалог отменён", show_alert=True)