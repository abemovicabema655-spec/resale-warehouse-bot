def format_money(value: float) -> str:
    return f"{value:,.2f}".replace(",", " ").replace(".", ",")


def format_percent(value: float) -> str:
    return f"{value:,.1f}".replace(",", " ").replace(".", ",")


def calc_item_margin_percent(purchase_price: float, sale_price: float) -> float:
    if purchase_price and purchase_price > 0:
        return (sale_price - purchase_price) / purchase_price * 100
    return 0.0


def format_dashboard(stats: dict) -> str:
    lines = [
        "📦 <b>Главный экран</b>\n",
        f"📊 Остаток на складе: <b>{stats['total_stock']}</b> шт.",
        f"💵 Прибыль за всё время: <b>{format_money(stats['profit'])}</b> ₽",
        f"📈 Маржинальность: <b>{format_percent(stats['margin_percent'])}</b> %",
        f"🛒 Продано товаров: <b>{stats['sold_count']}</b> шт.",
        f"💰 Общая выручка: <b>{format_money(stats['revenue'])}</b> ₽",
        f"📉 Общая себестоимость: <b>{format_money(stats['cost'])}</b> ₽",
    ]
    if stats["total_stock"] == 0 and stats["sold_count"] == 0:
        lines.append(
            "\n<i>Склад пуст. Добавьте первый товар через «➕ Новая закупка».</i>"
        )
    return "\n".join(lines)


def format_finance(stats: dict) -> str:
    lines = [
        "💰 <b>Финансы</b>\n",
        f"💵 Выручка: <b>{format_money(stats['revenue'])}</b> ₽",
        f"📉 Себестоимость проданных товаров: <b>{format_money(stats['cost'])}</b> ₽",
        f"📈 Прибыль: <b>{format_money(stats['profit'])}</b> ₽",
        f"📊 Маржинальность: <b>{format_percent(stats['margin_percent'])}</b> %",
        f"🛒 Количество продаж: <b>{stats['sold_count']}</b> шт.",
    ]
    if stats["sold_count"] == 0:
        lines.append("\n<i>Продаж пока нет — данные появятся после первой продажи.</i>")
    return "\n".join(lines)


def format_statistics(stats: dict) -> str:
    lines = [
        "📈 <b>Статистика</b>\n",
        f"🛒 Всего продано: <b>{stats['sold_count']}</b> шт.",
        f"💰 Общая выручка: <b>{format_money(stats['revenue'])}</b> ₽",
        f"📊 Средняя цена продажи: <b>{format_money(stats['avg_price'])}</b> ₽",
    ]
    if stats["sold_count"] == 0:
        lines.append("\n<i>Статистика пуста — продайте первый товар через «📦 Склад».</i>")
    return "\n".join(lines)


def format_warehouse(items: list[dict], search_query: str | None = None) -> str:
    if not items:
        if search_query:
            return (
                f"📦 <b>Склад</b>\n\n"
                f"По запросу «<b>{search_query}</b>» ничего не найдено."
            )
        return "📦 <b>Склад</b>\n\nСклад пуст. Добавьте товар через «➕ Новая закупка»."

    lines = ["📦 <b>Склад</b>"]
    if search_query:
        lines.append(f"\n🔍 Результаты поиска: «<b>{search_query}</b>»")

    for item in items:
        margin = calc_item_margin_percent(item["purchase_price"], item["sale_price"])
        lines.append(f"\n<b>{item['name']}</b>")
        lines.append(
            f"Закупка: {format_money(item['purchase_price'])} ₽ | "
            f"Продажа: {format_money(item['sale_price'])} ₽ | "
            f"Наценка: {format_percent(margin)} %"
        )
        if not item["sizes"]:
            lines.append("  — нет размеров на складе")
            continue
        for size_info in item["sizes"]:
            qty = size_info["quantity"]
            status = "✅" if qty > 0 else "❌"
            lines.append(f"  {status} Размер {size_info['size']}: {qty} шт.")

    return "\n".join(lines)


def format_sales_history(sales: list[dict]) -> str:
    if not sales:
        return (
            "📋 <b>Последние продажи</b>\n\n"
            "<i>Продаж пока нет — история появится после первой продажи.</i>"
        )

    lines = ["📋 <b>Последние продажи</b>\n"]
    for sale in sales:
        sold_at = sale["sold_at"] or ""
        if len(sold_at) >= 16:
            sold_at = sold_at[:16]
        lines.append(
            f"🕐 {sold_at} — <b>{sale['name']}</b> "
            f"({sale['size']}) — {format_money(sale['price'])} ₽"
        )
    return "\n".join(lines)


def format_item_card(item: dict) -> str:
    return (
        "✅ <b>Товар добавлен на склад</b>\n\n"
        f"📦 Название: <b>{item['name']}</b>\n"
        f"📏 Размер: <b>{item['size']}</b>\n"
        f"🔢 Количество: <b>{item['quantity']}</b> шт.\n"
        f"💵 Цена закупки: <b>{format_money(item['purchase_price'])}</b> ₽\n"
        f"💰 Цена продажи: <b>{format_money(item['sale_price'])}</b> ₽"
    )
