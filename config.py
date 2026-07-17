import os
from pathlib import Path

from dotenv import load_dotenv

load_dotenv()

BASE_DIR = Path(__file__).resolve().parent
DB_PATH = BASE_DIR / "warehouse.db"
BOT_TOKEN = os.getenv("BOT_TOKEN")


def get_bot_token() -> str:
    if not BOT_TOKEN:
        raise ValueError("BOT_TOKEN не найден. Создайте файл .env на основе .env.example")
    return BOT_TOKEN
