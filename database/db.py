import asyncio
import logging
from typing import Any

import asyncpg
from config import DB_URL

logger = logging.getLogger(__name__)


async def get_connection(retries: int = 5, delay: int = 3):
    """Подключается к PostgreSQL с повторными попытками, если БД «спит»."""
    last_error = None
    for attempt in range(1, retries + 1):
        try:
            conn = await asyncpg.connect(DB_URL)
            logger.info("✅ Подключение к базе данных установлено")
            return conn
        except Exception as e:
            last_error = e
            if attempt < retries:
                logger.warning(f"⚠️ Не удалось подключиться к БД (попытка {attempt}/{retries}), повтор через {delay} сек...")
                await asyncio.sleep(delay)
            else:
                logger.error(f"❌ Не удалось подключиться к БД после {retries} попыток: {e}")
    raise last_error or Exception("Неизвестная ошибка подключения")


async def init_db() -> None:
    """Создаёт таблицы, если их нет."""
    conn = await get_connection()
    try:
        await conn.execute("""
            CREATE TABLE IF NOT EXISTS users (
                id BIGINT PRIMARY KEY,
                username TEXT,
                first_name TEXT,
                last_name TEXT,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            );

            CREATE TABLE IF NOT EXISTS items (
                id SERIAL PRIMARY KEY,
                user_id BIGINT NOT NULL REFERENCES users(id),
                name TEXT NOT NULL,
                category TEXT DEFAULT 'Общее',
                purchase_price REAL,
                sale_price REAL
            );

            CREATE TABLE IF NOT EXISTS stock (
                id SERIAL PRIMARY KEY,
                item_id INTEGER NOT NULL REFERENCES items(id) ON DELETE CASCADE,
                size TEXT NOT NULL,
                quantity INTEGER DEFAULT 0,
                UNIQUE(item_id, size)
            );

            CREATE TABLE IF NOT EXISTS sales (
                id SERIAL PRIMARY KEY,
                item_id INTEGER NOT NULL REFERENCES items(id) ON DELETE CASCADE,
                size TEXT NOT NULL,
                price REAL,
                purchase_price REAL,
                sold_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            );

            CREATE INDEX IF NOT EXISTS idx_items_user_id ON items(user_id);
            CREATE INDEX IF NOT EXISTS idx_stock_item_id ON stock(item_id);
            CREATE INDEX IF NOT EXISTS idx_sales_item_id ON sales(item_id);
            CREATE INDEX IF NOT EXISTS idx_items_name ON items(name);
        """)
        await conn.execute("COMMIT")
        logger.info("✅ Таблицы созданы/проверены")
    finally:
        await conn.close()


async def register_user(user_id: int, username: str = None, first_name: str = None, last_name: str = None) -> None:
    conn = await get_connection()
    try:
        await conn.execute(
            "INSERT INTO users (id, username, first_name, last_name) VALUES ($1, $2, $3, $4) ON CONFLICT (id) DO NOTHING",
            user_id, username, first_name, last_name
        )
        await conn.execute("COMMIT")
    finally:
        await conn.close()


async def add_purchase(
    user_id: int,
    name: str,
    size: str,
    quantity: int,
    purchase_price: float,
    sale_price: float,
    category: str = "Общее",
) -> dict[str, Any]:
    conn = await get_connection()
    try:
        row = await conn.fetchrow(
            "SELECT id FROM items WHERE user_id = $1 AND name = $2",
            user_id, name.strip()
        )
        if row:
            item_id = row["id"]
            await conn.execute(
                """
                UPDATE items
                SET purchase_price = $1, sale_price = $2, category = $3
                WHERE id = $4
                """,
                purchase_price, sale_price, category, item_id
            )
        else:
            item_id = await conn.fetchval(
                """
                INSERT INTO items (user_id, name, category, purchase_price, sale_price)
                VALUES ($1, $2, $3, $4, $5)
                RETURNING id
                """,
                user_id, name.strip(), category, purchase_price, sale_price
            )

        stock_row = await conn.fetchrow(
            "SELECT id, quantity FROM stock WHERE item_id = $1 AND size = $2",
            item_id, size.strip()
        )
        if stock_row:
            new_qty = (stock_row["quantity"] or 0) + quantity
            await conn.execute(
                "UPDATE stock SET quantity = $1 WHERE id = $2",
                new_qty, stock_row["id"]
            )
        else:
            await conn.execute(
                "INSERT INTO stock (item_id, size, quantity) VALUES ($1, $2, $3)",
                item_id, size.strip(), quantity
            )

        await conn.execute("COMMIT")

        item = await conn.fetchrow("SELECT * FROM items WHERE id = $1", item_id)
        stock = await conn.fetchrow(
            "SELECT quantity FROM stock WHERE item_id = $1 AND size = $2",
            item_id, size.strip()
        )
        return {
            "id": item["id"],
            "name": item["name"],
            "category": item["category"],
            "purchase_price": item["purchase_price"],
            "sale_price": item["sale_price"],
            "size": size.strip(),
            "quantity": stock["quantity"] if stock else quantity,
        }
    finally:
        await conn.close()


def _calc_margin_percent(revenue: float, cost: float) -> float:
    if cost and cost > 0:
        return (revenue - cost) / cost * 100
    return 0.0


async def get_warehouse_items(user_id: int) -> list[dict[str, Any]]:
    conn = await get_connection()
    try:
        rows = await conn.fetch(
            """
            SELECT
                i.id AS item_id,
                i.name,
                i.purchase_price,
                i.sale_price,
                s.id AS stock_id,
                s.size,
                s.quantity
            FROM items i
            INNER JOIN stock s ON s.item_id = i.id
            WHERE i.user_id = $1
            ORDER BY i.name, s.size
            """,
            user_id
        )
        grouped = {}
        for row in rows:
            item_id = row["item_id"]
            if item_id not in grouped:
                grouped[item_id] = {
                    "item_id": item_id,
                    "name": row["name"],
                    "purchase_price": row["purchase_price"] or 0,
                    "sale_price": row["sale_price"] or 0,
                    "sizes": []
                }
            grouped[item_id]["sizes"].append({
                "stock_id": row["stock_id"],
                "size": row["size"],
                "quantity": row["quantity"] or 0
            })
        return list(grouped.values())
    finally:
        await conn.close()


async def get_item_by_id(user_id: int, item_id: int) -> dict[str, Any] | None:
    conn = await get_connection()
    try:
        row = await conn.fetchrow(
            "SELECT id, name, purchase_price, sale_price FROM items WHERE id = $1 AND user_id = $2",
            item_id, user_id
        )
        if not row:
            return None
        return {
            "item_id": row["id"],
            "name": row["name"],
            "purchase_price": row["purchase_price"] or 0,
            "sale_price": row["sale_price"] or 0,
        }
    finally:
        await conn.close()


async def update_item_prices(
    user_id: int,
    item_id: int,
    purchase_price: float,
    sale_price: float,
) -> tuple[bool, str]:
    conn = await get_connection()
    try:
        res = await conn.execute(
            "UPDATE items SET purchase_price = $1, sale_price = $2 WHERE id = $3 AND user_id = $4",
            purchase_price, sale_price, item_id, user_id
        )
        if res == "UPDATE 0":
            return False, "Товар не найден или доступ запрещён."
        await conn.execute("COMMIT")
        return True, "Цены обновлены."
    finally:
        await conn.close()


async def delete_stock_size(user_id: int, item_id: int, size: str) -> tuple[bool, str]:
    conn = await get_connection()
    try:
        row = await conn.fetchrow(
            "SELECT id FROM items WHERE id = $1 AND user_id = $2",
            item_id, user_id
        )
        if not row:
            return False, "Товар не найден или доступ запрещён."

        res = await conn.execute(
            "DELETE FROM stock WHERE item_id = $1 AND size = $2",
            item_id, size
        )
        if res == "DELETE 0":
            return False, "Размер не найден на складе."

        remaining = await conn.fetchval(
            "SELECT COUNT(*) FROM stock WHERE item_id = $1",
            item_id
        )
        if remaining == 0:
            sales_count = await conn.fetchval(
                "SELECT COUNT(*) FROM sales WHERE item_id = $1",
                item_id
            )
            if sales_count == 0:
                await conn.execute("DELETE FROM items WHERE id = $1", item_id)

        await conn.execute("COMMIT")
        return True, f"Размер {size} удалён со склада."
    finally:
        await conn.close()


async def sell_item(user_id: int, item_id: int, size: str) -> tuple[bool, str]:
    conn = await get_connection()
    try:
        row = await conn.fetchrow(
            "SELECT id FROM items WHERE id = $1 AND user_id = $2",
            item_id, user_id
        )
        if not row:
            return False, "Товар не найден или доступ запрещён."

        stock_row = await conn.fetchrow(
            "SELECT id, quantity FROM stock WHERE item_id = $1 AND size = $2",
            item_id, size
        )
        if not stock_row or (stock_row["quantity"] or 0) <= 0:
            return False, "Нет товара в наличии для продажи."

        item = await conn.fetchrow(
            "SELECT sale_price, purchase_price FROM items WHERE id = $1",
            item_id
        )
        if not item:
            return False, "Товар не найден."

        sale_price = item["sale_price"] or 0
        purchase_price = item["purchase_price"] or 0

        await conn.execute(
            "UPDATE stock SET quantity = quantity - 1 WHERE id = $1",
            stock_row["id"]
        )
        await conn.execute(
            """
            INSERT INTO sales (item_id, size, price, purchase_price)
            VALUES ($1, $2, $3, $4)
            """,
            item_id, size, sale_price, purchase_price
        )
        await conn.execute("COMMIT")
        return True, "Продажа зафиксирована."
    finally:
        await conn.close()


async def replenish_stock(user_id: int, item_id: int, size: str, amount: int) -> tuple[bool, str]:
    if amount <= 0:
        return False, "Количество должно быть положительным числом."

    conn = await get_connection()
    try:
        row = await conn.fetchrow(
            "SELECT id FROM items WHERE id = $1 AND user_id = $2",
            item_id, user_id
        )
        if not row:
            return False, "Товар не найден или доступ запрещён."

        res = await conn.execute(
            "UPDATE stock SET quantity = quantity + $1 WHERE item_id = $2 AND size = $3",
            amount, item_id, size
        )
        if res == "UPDATE 0":
            return False, "Размер не найден на складе."

        await conn.execute("COMMIT")
        return True, f"Добавлено {amount} шт."
    finally:
        await conn.close()


async def get_dashboard_stats(user_id: int) -> dict[str, Any]:
    conn = await get_connection()
    try:
        total_stock = await conn.fetchval(
            """
            SELECT COALESCE(SUM(s.quantity), 0)
            FROM stock s
            JOIN items i ON i.id = s.item_id
            WHERE i.user_id = $1
            """,
            user_id
        ) or 0

        row = await conn.fetchrow(
            """
            SELECT
                COUNT(*) AS sold_count,
                COALESCE(SUM(s.price), 0) AS revenue,
                COALESCE(SUM(s.purchase_price), 0) AS cost
            FROM sales s
            JOIN items i ON i.id = s.item_id
            WHERE i.user_id = $1
            """,
            user_id
        )
        sold_count = row["sold_count"] if row else 0
        revenue = row["revenue"] if row else 0
        cost = row["cost"] if row else 0
        profit = revenue - cost
        margin_percent = _calc_margin_percent(revenue, cost)

        return {
            "total_stock": total_stock,
            "profit": profit,
            "sold_count": sold_count,
            "revenue": revenue,
            "cost": cost,
            "margin_percent": margin_percent,
        }
    finally:
        await conn.close()


async def get_finance_stats(user_id: int) -> dict[str, Any]:
    stats = await get_dashboard_stats(user_id)
    return {
        "revenue": stats["revenue"],
        "cost": stats["cost"],
        "profit": stats["profit"],
        "sold_count": stats["sold_count"],
        "margin_percent": stats["margin_percent"],
    }


async def get_statistics(user_id: int) -> dict[str, Any]:
    stats = await get_finance_stats(user_id)
    sold_count = stats["sold_count"] or 0
    revenue = stats["revenue"] or 0
    avg_price = revenue / sold_count if sold_count > 0 else 0
    return {
        "sold_count": sold_count,
        "revenue": revenue,
        "avg_price": avg_price,
    }


# Обёртки
async def delete_size(user_id: int, item_id: int, size: str) -> tuple[bool, str]:
    return await delete_stock_size(user_id, item_id, size)


async def update_price(user_id: int, item_id: int, new_sale_price: float) -> tuple[bool, str]:
    conn = await get_connection()
    try:
        row = await conn.fetchrow(
            "SELECT purchase_price FROM items WHERE id = $1 AND user_id = $2",
            item_id, user_id
        )
        if not row:
            return False, "Товар не найден или доступ запрещён."
        purchase_price = row["purchase_price"] or 0
        return await update_item_prices(user_id, item_id, purchase_price, new_sale_price)
    finally:
        await conn.close()