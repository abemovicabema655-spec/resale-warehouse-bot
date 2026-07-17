import asyncio
import uvloop
asyncio.set_event_loop_policy(uvloop.EventLoopPolicy())

import logging
import sys
import threading
import os

from flask import Flask
from aiogram import Bot, Dispatcher
from aiogram.client.default import DefaultBotProperties
from aiogram.enums import ParseMode
from aiogram.fsm.storage.memory import MemoryStorage
from aiogram.types import ErrorEvent

from config import get_bot_token
from database.db import init_db
from handlers import deliveries, finance, purchase, start, statistics, warehouse
from keyboards.menus import main_menu_keyboard

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
    stream=sys.stdout,
)
logger = logging.getLogger(__name__)

# Мини-веб-сервер для Render
app = Flask(__name__)

@app.route('/')
@app.route('/health')
def health():
    return "OK", 200

def run_web():
    port = int(os.environ.get("PORT", 5000))
    app.run(host="0.0.0.0", port=port)


async def on_error(event: ErrorEvent) -> None:
    logger.exception("Необработанная ошибка: %s", event.exception)
    update = event.update
    if update.message:
        await update.message.answer(
            "⚠️ Произошла ошибка. Попробуйте ещё раз или вернитесь в меню.",
            reply_markup=main_menu_keyboard(),
        )
    elif update.callback_query:
        await update.callback_query.answer(
            "⚠️ Произошла ошибка. Попробуйте ещё раз.",
            show_alert=True,
        )


async def main() -> None:
    # Запускаем веб-сервер в отдельном потоке, чтобы не блокировать бота
    threading.Thread(target=run_web, daemon=True).start()
    logger.info("Веб-сервер для Render запущен")

    await init_db()

    bot = Bot(
        token=get_bot_token(),
        default=DefaultBotProperties(parse_mode=ParseMode.HTML),
    )
    dp = Dispatcher(storage=MemoryStorage())

    dp.errors.register(on_error)
    dp.include_router(start.router)
    dp.include_router(purchase.router)
    dp.include_router(warehouse.router)
    dp.include_router(finance.router)
    dp.include_router(statistics.router)
    dp.include_router(deliveries.router)

    logger.info("Бот запущен")
    await dp.start_polling(bot)


if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        logger.info("Бот остановлен")
    except Exception as exc:
        logger.exception("Критическая ошибка: %s", exc)
        sys.exit(1)