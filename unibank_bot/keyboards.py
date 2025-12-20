from telebot import types


def operator_kb() -> types.InlineKeyboardMarkup:
    kb = types.InlineKeyboardMarkup()
    kb.add(types.InlineKeyboardButton(
        "✅ Завершить диалог",
        callback_data="end_dialog"
    ))
    return kb


def register_kb() -> types.InlineKeyboardMarkup:
    kb = types.InlineKeyboardMarkup()
    kb.add(
        types.InlineKeyboardButton("👤 Клиент банка", callback_data="reg_user"),
        types.InlineKeyboardButton("🏦 Сотрудник банка", callback_data="reg_employee")
    )
    return kb

 
def rating_row():
    return [
        types.InlineKeyboardButton("1⭐", callback_data="rate_1"),
        types.InlineKeyboardButton("2⭐", callback_data="rate_2"),
        types.InlineKeyboardButton("3⭐", callback_data="rate_3"),
        types.InlineKeyboardButton("4⭐", callback_data="rate_4"),
        types.InlineKeyboardButton("5⭐", callback_data="rate_5"),
    ]


def answer_kb(links: list[tuple[str, str]]) -> types.InlineKeyboardMarkup:
    """
    Клавиатура под ответом GigaChat:
    - первая строка: оценки 1–5
    - далее: ссылки на сайт Сбербанка, подобранные под запрос
    """
    kb = types.InlineKeyboardMarkup()

    # ряд с оценками
    kb.row(*rating_row())

    # ряды с рекомендациями / ссылками
    row: list[types.InlineKeyboardButton] = []
    for title, url in links:
        row.append(types.InlineKeyboardButton(title, url=url))
        if len(row) == 2:
            kb.row(*row)
            row = []
    if row:
        kb.row(*row)

    return kb


def rating_kb() -> types.InlineKeyboardMarkup:
    """
    Оставлено для обратной совместимости, если где-то ещё используется.
    """
    kb = types.InlineKeyboardMarkup()
    kb.row(*rating_row())
    return kb


def main_menu_kb() -> types.InlineKeyboardMarkup:
    """
    Главное меню бота с быстрыми действиями.
    """
    kb = types.InlineKeyboardMarkup(row_width=2)
    kb.add(
        types.InlineKeyboardButton("💳 Карты", callback_data="menu_cards"),
        types.InlineKeyboardButton("💰 Вклады", callback_data="menu_deposits"),
        types.InlineKeyboardButton("🏠 Ипотека", callback_data="menu_mortgage"),
        types.InlineKeyboardButton("📄 Кредиты", callback_data="menu_credits"),
        types.InlineKeyboardButton("🧾 Платежи", callback_data="menu_payments"),
        types.InlineKeyboardButton("📨 Переводы", callback_data="menu_transfers"),
        types.InlineKeyboardButton("📊 Анализ расходов", callback_data="menu_analysis"),
    )
    return kb


def back_to_menu_kb() -> types.InlineKeyboardMarkup:
    """
    Кнопка возврата в главное меню.
    """
    kb = types.InlineKeyboardMarkup()
    kb.add(types.InlineKeyboardButton("🏠 Главное меню", callback_data="main_menu"))
    return kb


