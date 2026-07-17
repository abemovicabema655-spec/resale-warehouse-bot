import logging
from typing import Any

import aiosqlite

from config import DB_PATH

logger = logging.getLogger(__name__)


async def init_db() -> None:
    async with aiosqlite.connect(DB_PATH) as db:
        await db.executescript(
            """
            CREATE TABLE IF NOT EXISTS items (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                name TEXT NOT NULL,
                category TEXT DEFAULT 'Общее',
                purchase_price REAL,
                sale_price REAL
            );

            CREATE TABLE IF NOT EXISTS stock (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                item_id INTEGER NOT NULL,
                size TEXT NOT NULL,
                quantity INTEGER DEFAULT 0,
                FOREIGN KEY (item_id) REFERENCES items(id),
                UNIQUE(item_id, size)
            );

            CREATE TABLE IF NOT EXISTS sales (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                item_id INTEGER NOT NULL,
                size TEXT NOT NULL,
                price REAL,
                purchase_price REAL,
                sold_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                FOREIGN KEY (item_id) REFERENCES items(id)
            );
            """
        )
        # Индексы для ускорения запросов
        await db.execute("CREATE INDEX IF NOT EXISTS idx_stock_item_id ON stock (item_id);")
        await db.execute("CREATE INDEX IF NOT EXISTS idx_sales_item_id ON sales (item_id);")
        await db.execute("CREATE INDEX IF NOT EXISTS idx_items_name ON items (name);")
        await db.commit()


async def add_purchase(
    name: str,
    size: str,
    quantity: int,
    purchase_price: float,
    sale_price: float,
    category: str = "Общее",
) -> dict[str, Any]:
    async with aiosqlite.connect(DB_PATH) as db:
        db.row_factory = aiosqlite.Row
        cursor = await db.execute(
            "SELECT id FROM items WHERE name = ? COLLATE NOCASE",
            (name.strip(),),
        )
        row = await cursor.fetchone()

        if row:
            item_id = row["id"]
            await db.execute(
                """
                UPDATE items
                SET purchase_price = ?, sale_price = ?, category = ?
                WHERE id = ?
                """,
                (purchase_price, sale_price, category, item_id),
            )
        else:
            cursor = await db.execute(
                """
                INSERT INTO items (name, category, purchase_price, sale_price)
                VALUES (?, ?, ?, ?)
                """,
                (name.strip(), category, purchase_price, sale_price),
            )
            item_id = cursor.lastrowid

        cursor = await db.execute(
            "SELECT id, quantity FROM stock WHERE item_id = ? AND size = ?",
            (item_id, size.strip()),
        )
        stock_row = await cursor.fetchone()

        if stock_row:
            new_qty = (stock_row["quantity"] or 0) + quantity
            await db.execute(
                "UPDATE stock SET quantity = ? WHERE id = ?",
                (new_qty, stock_row["id"]),
            )
        else:
            await db.execute(
                "INSERT INTO stock (item_id, size, quantity) VALUES (?, ?, ?)",
                (item_id, size.strip(), quantity),
            )

        await db.commit()

        cursor = await db.execute(
            "SELECT * FROM items WHERE id = ?",
            (item_id,),
        )
        item = await cursor.fetchone()
        cursor = await db.execute(
            "SELECT quantity FROM stock WHERE item_id = ? AND size = ?",
            (item_id, size.strip()),
        )
        stock = await cursor.fetchone()

        return {
            "id": item["id"],
            "name": item["name"],
            "category": item["category"],
            "purchase_price": item["purchase_price"],
            "sale_price": item["sale_price"],
            "size": size.strip(),
            "quantity": stock["quantity"] if stock else quantity,
        }


def _calc_margin_percent(revenue: float, cost: float) -> float:
    if cost and cost > 0:
        return (revenue - cost) / cost * 100
    return 0.0


def _group_warehouse_rows(rows: list) -> list[dict[str, Any]]:
    grouped: dict[int, dict[str, Any]] = {}
    for row in rows:
        item_id = row["item_id"]
        if item_id not in grouped:
            grouped[item_id] = {
                "item_id": item_id,
                "name": row["name"],
                "purchase_price": row["purchase_price"] or 0,
                "sale_price": row["sale_price"] or 0,
                "sizes": [],
            }
        if row["size"] is not None:
            grouped[item_id]["sizes"].append(
                {
                    "stock_id": row["stock_id"],
                    "size": row["size"],
                    "quantity": row["quantity"] or 0,
                }
            )

    return list(grouped.values())


_WAREHOUSE_QUERY = """
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
    {where_clause}
    ORDER BY i.name COLLATE NOCASE, s.size COLLATE NOCASE
"""


async def get_warehouse_items() -> list[dict[str, Any]]:
    async with aiosqlite.connect(DB_PATH) as db:
        db.row_factory = aiosqlite.Row
        cursor = await db.execute(_WAREHOUSE_QUERY.format(where_clause=""))
        rows = await cursor.fetchall()
    return _group_warehouse_rows(rows)


async def search_warehouse_items(query: str) -> list[dict[str, Any]]:
    search = (query or "").strip()
    if not search:
        return await get_warehouse_items()

    async with aiosqlite.connect(DB_PATH) as db:
        db.row_factory = aiosqlite.Row
        cursor = await db.execute(
            _WAREHOUSE_QUERY.format(where_clause="WHERE i.name LIKE ? COLLATE NOCASE"),
            (f"%{search}%",),
        )
        rows = await cursor.fetchall()
    return _group_warehouse_rows(rows)


async def get_item_by_id(item_id: int) -> dict[str, Any] | None:
    async with aiosqlite.connect(DB_PATH) as db:
        db.row_factory = aiosqlite.Row
        cursor = await db.execute(
            "SELECT id, name, purchase_price, sale_price FROM items WHERE id = ?",
            (item_id,),
        )
        row = await cursor.fetchone()
    if not row:
        return None
    return {
        "item_id": row["id"],
        "name": row["name"],
        "purchase_price": row["purchase_price"] or 0,
        "sale_price": row["sale_price"] or 0,
    }


async def update_item_prices(
    item_id: int,
    purchase_price: float,
    sale_price: float,
) -> tuple[bool, str]:
    async with aiosqlite.connect(DB_PATH) as db:
        cursor = await db.execute("SELECT id FROM items WHERE id = ?", (item_id,))
        if not await cursor.fetchone():
            return False, "Товар не найден."

        await db.execute(
            "UPDATE items SET purchase_price = ?, sale_price = ? WHERE id = ?",
            (purchase_price, sale_price, item_id),
        )
        await db.commit()
    return True, "Цены обновлены."


async def delete_stock_size(item_id: int, size: str) -> tuple[bool, str]:
    print(f"🔍 delete_stock_size: item_id={item_id}, size={size}")
    async with aiosqlite.connect(DB_PATH) as db:
        db.row_factory = aiosqlite.Row
        cursor = await db.execute(
            "SELECT id FROM stock WHERE item_id = ? AND size = ?",
            (item_id, size),
        )
        stock_row = await cursor.fetchone()
        if not stock_row:
            print(f"❌ Размер {size} не найден в stock")
            return False, "Размер не найден на складе."

        await db.execute(
            "DELETE FROM stock WHERE item_id = ? AND size = ?",
            (item_id, size),
        )

        cursor = await db.execute(
            "SELECT COUNT(*) AS cnt FROM stock WHERE item_id = ?",
            (item_id,),
        )
        remaining = await cursor.fetchone()

        if remaining and remaining["cnt"] == 0:
            cursor = await db.execute(
                "SELECT COUNT(*) AS cnt FROM sales WHERE item_id = ?",
                (item_id,),
            )
            sales_count = await cursor.fetchone()
            if sales_count and sales_count["cnt"] == 0:
                await db.execute("DELETE FROM items WHERE id = ?", (item_id,))

        await db.commit()
    print(f"✅ Размер {size} удалён")
    return True, f"Размер {size} удалён со склада."


async def get_recent_sales(limit: int = 20) -> list[dict[str, Any]]:
    limit = max(1, min(limit, 50))
    async with aiosqlite.connect(DB_PATH) as db:
        db.row_factory = aiosqlite.Row
        cursor = await db.execute(
            """
            SELECT
                s.sold_at,
                COALESCE(i.name, 'Удалённый товар') AS name,
                s.size,
                s.price
            FROM sales s
            LEFT JOIN items i ON i.id = s.item_id
            ORDER BY s.sold_at DESC, s.id DESC
            LIMIT ?
            """,
            (limit,),
        )
        rows = await cursor.fetchall()

    return [
        {
            "sold_at": row["sold_at"],
            "name": row["name"],
            "size": row["size"],
            "price": row["price"] or 0,
        }
        for row in rows
    ]


async def sell_item(item_id: int, size: str) -> tuple[bool, str]:
    async with aiosqlite.connect(DB_PATH) as db:
        db.row_factory = aiosqlite.Row
        cursor = await db.execute(
            "SELECT id, quantity FROM stock WHERE item_id = ? AND size = ?",
            (item_id, size),
        )
        stock_row = await cursor.fetchone()

        if not stock_row or (stock_row["quantity"] or 0) <= 0:
            return False, "Нет товара в наличии для продажи."

        cursor = await db.execute(
            "SELECT sale_price, purchase_price FROM items WHERE id = ?",
            (item_id,),
        )
        item = await cursor.fetchone()
        if not item:
            return False, "Товар не найден."

        sale_price = item["sale_price"] or 0
        purchase_price = item["purchase_price"] or 0

        await db.execute(
            "UPDATE stock SET quantity = quantity - 1 WHERE id = ?",
            (stock_row["id"],),
        )
        await db.execute(
            """
            INSERT INTO sales (item_id, size, price, purchase_price)
            VALUES (?, ?, ?, ?)
            """,
            (item_id, size, sale_price, purchase_price),
        )
        await db.commit()
        return True, "Продажа зафиксирована."


async def replenish_stock(item_id: int, size: str, amount: int) -> tuple[bool, str]:
    if amount <= 0:
        return False, "Количество должно быть положительным числом."

    async with aiosqlite.connect(DB_PATH) as db:
        db.row_factory = aiosqlite.Row
        cursor = await db.execute(
            "SELECT id, quantity FROM stock WHERE item_id = ? AND size = ?",
            (item_id, size),
        )
        stock_row = await cursor.fetchone()

        if not stock_row:
            return False, "Размер не найден на складе."

        await db.execute(
            "UPDATE stock SET quantity = quantity + ? WHERE id = ?",
            (amount, stock_row["id"]),
        )
        await db.commit()
        return True, f"Добавлено {amount} шт."


async def get_dashboard_stats() -> dict[str, Any]:
    async with aiosqlite.connect(DB_PATH) as db:
        db.row_factory = aiosqlite.Row

        cursor = await db.execute(
            "SELECT COALESCE(SUM(quantity), 0) AS total FROM stock"
        )
        stock_row = await cursor.fetchone()
        total_stock = stock_row["total"] if stock_row else 0

        cursor = await db.execute(
            """
            SELECT
                COUNT(*) AS sold_count,
                COALESCE(SUM(price), 0) AS revenue,
                COALESCE(SUM(purchase_price), 0) AS cost
            FROM sales
            """
        )
        sales_row = await cursor.fetchone()

    sold_count = sales_row["sold_count"] if sales_row else 0
    revenue = sales_row["revenue"] if sales_row else 0
    cost = sales_row["cost"] if sales_row else 0
    profit = revenue - cost
    margin_percent = _calc_margin_percent(revenue, cost)

    return {
        "total_stock": total_stock or 0,
        "profit": profit,
        "sold_count": sold_count or 0,
        "revenue": revenue or 0,
        "cost": cost or 0,
        "margin_percent": margin_percent,
    }


async def get_finance_stats() -> dict[str, Any]:
    stats = await get_dashboard_stats()
    return {
        "revenue": stats["revenue"],
        "cost": stats["cost"],
        "profit": stats["profit"],
        "sold_count": stats["sold_count"],
        "margin_percent": stats["margin_percent"],
    }


async def get_statistics() -> dict[str, Any]:
    stats = await get_finance_stats()
    sold_count = stats["sold_count"] or 0
    revenue = stats["revenue"] or 0
    avg_price = revenue / sold_count if sold_count > 0 else 0

    return {
        "sold_count": sold_count,
        "revenue": revenue,
        "avg_price": avg_price,
    }


# === ОБЁРТКИ ДЛЯ УДОБСТВА (используются в handlers) ===
async def delete_size(item_id: int, size: str) -> tuple[bool, str]:
    return await delete_stock_size(item_id, size)


async def update_price(item_id: int, new_sale_price: float) -> tuple[bool, str]:
    async with aiosqlite.connect(DB_PATH) as db:
        db.row_factory = aiosqlite.Row
        cursor = await db.execute("SELECT purchase_price FROM items WHERE id = ?", (item_id,))
        row = await cursor.fetchone()
        if not row:
            return False, "Товар не найден."
        purchase_price = row["purchase_price"] or 0
        return await update_item_prices(item_id, purchase_price, new_sale_price)