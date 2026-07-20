import os
from dotenv import load_dotenv

load_dotenv()

BOT_TOKEN = os.getenv("BOT_TOKEN")
DB_URL = DB_URL = "postgresql://neondb_owner:npg_wk1qSUQ2brms@ep-restless-mud-as38r0fx-pooler.c-4.eu-central-1.aws.neon.tech/neondb?sslmode=require"

def get_bot_token() -> str:
    if not BOT_TOKEN:
        raise ValueError("BOT_TOKEN не найден. Создайте файл .env на основе .env.example")
    return BOT_TOKEN

def get_db_url() -> str:
    if not DB_URL:
        raise ValueError("DATABASE_URL не найден. Проверьте переменные окружения")
    return DB_URL