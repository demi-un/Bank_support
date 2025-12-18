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
        types.InlineKeyboardButton("👤 Клиент Сбербанка", callback_data="reg_user"),
        types.InlineKeyboardButton("🏦 Сотрудник Сбербанка", callback_data="reg_employee")
    )
    return kb


def rating_kb() -> types.InlineKeyboardMarkup:
    kb = types.InlineKeyboardMarkup(row_width=5)
    buttons = [
        types.InlineKeyboardButton("1", callback_data="rate_1"),
        types.InlineKeyboardButton("2", callback_data="rate_2"),
        types.InlineKeyboardButton("3", callback_data="rate_3"),
        types.InlineKeyboardButton("4", callback_data="rate_4"),
        types.InlineKeyboardButton("5", callback_data="rate_5"),
    ]
    kb.add(*buttons)
    return kb


