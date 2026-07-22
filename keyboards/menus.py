from aiogram.types import InlineKeyboardButton, InlineKeyboardMarkup, KeyboardButton, ReplyKeyboardMarkup

MAIN_MENU_BUTTONS = [
    ["📦 Склад", "💰 Финансы"],
    ["➕ Новая закупка", "📈 Статистика"],
    ["📋 История продаж", "📂 Архив"],
    ["⚙️ Настройки"],
]


def main_menu_keyboard() -> ReplyKeyboardMarkup:
    return ReplyKeyboardMarkup(
        keyboard=[[KeyboardButton(text=btn) for btn in row] for row in MAIN_MENU_BUTTONS],
        resize_keyboard=True,
        input_field_placeholder="Выберите раздел меню",
    )


def back_inline_keyboard() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [InlineKeyboardButton(text="🔙 Назад", callback_data="back:menu")]
        ]
    )


def finance_inline_keyboard() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [InlineKeyboardButton(text="📋 Последние продажи", callback_data="sales:history")],
            [InlineKeyboardButton(text="🔙 Назад", callback_data="back:menu")],
        ]
    )


def cancel_inline_keyboard() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [InlineKeyboardButton(text="❌ Отмена", callback_data="cancel:dialog")]
        ]
    )


def warehouse_keyboard(
    items: list[dict],
    search_query: str | None = None,
) -> InlineKeyboardMarkup:
    buttons: list[list[InlineKeyboardButton]] = []

    for item in items:
        item_id = item["item_id"]
        item_name = item["name"]
        short_name = item_name[:20] + "…" if len(item_name) > 20 else item_name

        for size_info in item["sizes"]:
            size = size_info["size"]
            buttons.append([
                InlineKeyboardButton(
                    text=f"✅ Продано {size}",
                    callback_data=f"sell:{item_id}:{size}",
                ),
                InlineKeyboardButton(
                    text=f"🗑️ Удалить {size}",
                    callback_data=f"delete:{item_id}:{size}",
                ),
            ])
            buttons.append([
                InlineKeyboardButton(
                    text=f"➕ Пополнить {size}",
                    callback_data=f"replenish:{item_id}:{size}",
                ),
            ])

        buttons.append([
            InlineKeyboardButton(
                text=f"✏️ Изменить цену — {short_name}",
                callback_data=f"edit_price:{item_id}",
            )
        ])

        buttons.append([
            InlineKeyboardButton(
                text=f"🗄️ В архив",
                callback_data=f"archive:{item_id}",
            )
        ])

        buttons.append([
            InlineKeyboardButton(
                text=f"🔔 Порог",
                callback_data=f"threshold:{item_id}",
            )
        ])

    buttons.append([InlineKeyboardButton(text="🔍 Поиск", callback_data="warehouse:search")])
    if search_query:
        buttons.append(
            [InlineKeyboardButton(text="📦 Показать весь склад", callback_data="warehouse:all")]
        )
    buttons.append([InlineKeyboardButton(text="🔙 Назад", callback_data="back:menu")])

    return InlineKeyboardMarkup(inline_keyboard=buttons)