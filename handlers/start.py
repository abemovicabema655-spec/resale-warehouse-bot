import logging

from aiogram import F, Router
from aiogram.filters import CommandStart
from aiogram.fsm.context import FSMContext
from aiogram.types import CallbackQuery, Message

from database.db import get_dashboard_stats
from keyboards.menus import back_inline_keyboard, main_menu_keyboard
from utils.formatters import format_dashboard

logger = logging.getLogger(__name__)
router = Router()


@router.message(CommandStart())
async def cmd_start(message: Message) -> None:
    try:
        stats = await get_dashboard_stats()
        await message.answer(
            "👋 Добро пожаловать в бот складского учёта!\n\n"
            + format_dashboard(stats),
            reply_markup=main_menu_keyboard(),
            parse_mode="HTML",
        )
    except Exception as exc:
        logger.exception("Ошибка в /start: %s", exc)
        await message.answer(
            "⚠️ Произошла ошибка при запуске. Попробуйте позже.",
            reply_markup=main_menu_keyboard(),
        )


@router.message(F.text == "📦 Главный экран")
async def show_dashboard(message: Message) -> None:
    try:
        stats = await get_dashboard_stats()
        await message.answer(
            format_dashboard(stats),
            reply_markup=back_inline_keyboard(),
            parse_mode="HTML",
        )
    except Exception as exc:
        logger.exception("Ошибка главного экрана: %s", exc)
        await message.answer("⚠️ Не удалось загрузить данные главного экрана.")


@router.callback_query(F.data == "back:menu")
async def back_to_menu(callback: CallbackQuery, state: FSMContext) -> None:
    try:
        await state.clear()
        await callback.answer()
        stats = await get_dashboard_stats()
        text = "🏠 <b>Главное меню</b>\n\n" + format_dashboard(stats)

        try:
            await callback.message.edit_text(
                text,
                reply_markup=None,
                parse_mode="HTML",
            )
        except Exception:
            pass

        await callback.message.answer(
            text,
            reply_markup=main_menu_keyboard(),
            parse_mode="HTML",
        )
    except Exception as exc:
        logger.exception("Ошибка возврата в меню: %s", exc)
        await callback.answer("⚠️ Ошибка", show_alert=True)
