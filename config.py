import os
from dotenv import load_dotenv

load_dotenv()

BOT_TOKEN = os.getenv("BOT_TOKEN")
DB_URL = os.getenv("DATABASE_URL")  # Используем PostgreSQL

def get_bot_token() -> str:
    if not BOT_TOKEN:
        raise ValueError("BOT_TOKEN не найден. Создайте файл .env на основе .env.example")
    return BOT_TOKEN