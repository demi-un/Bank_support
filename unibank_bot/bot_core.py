import json
from datetime import datetime

import telebot
from telebot import types

from database import dbsearch
from .config import TOKEN, OPERATOR_ID
from .keyboards import register_kb, answer_kb
from .llm import classify_question, generate_answer, analyze_expenses, get_recommendation_tags
from .state import (
    users_state,
    users_role,
    llm_enabled,
    last_user_question,
    last_bot_answer,
    tickets,
    analysis_waiting_file,
    operator_busy,
    save_rating,
)


bot = telebot.TeleBot(TOKEN)


def create_ticket(user_id, question):
    ticket_id = str(datetime.now().timestamp()).replace(".", "")[-8:]
    tickets[user_id] = {
        "ticket_id": ticket_id,
        "user_id": user_id,
        "question": question,
        "created_at": datetime.now().isoformat()
    }
    return ticket_id


def end_dialog(user_id):
    global operator_busy

    if operator_busy == user_id:
        operator_busy = None

    users_state[user_id] = "bot"
    llm_enabled[user_id] = True
    last_user_question.pop(user_id, None)

    bot.send_message(user_id, "✅ Диалог с оператором завершён. Вы можете задать новый вопрос.")


@bot.message_handler(commands=["start"])
def start(msg):
    bot.send_message(
        msg.chat.id,
        "*Здравствуйте! Я - Виртуальный ассистент Сбербанка*\n\n"
        "Я помогу:\n"
        "• ответить на вопросы по продуктам и сервисам\n"
        "• передать запрос оператору\n"
        "• сделать краткий анализ ваших расходов (/analise)\n\n"
        "__Выберите роль:__",
        reply_markup=register_kb(),
        parse_mode="Markdown"
    )


@bot.callback_query_handler(func=lambda c: c.data in ["reg_user", "reg_employee"])
def register(call):
    user_id = call.message.chat.id

    if call.data == "reg_user":
        users_role[user_id] = "user"
        users_state[user_id] = "bot"
        llm_enabled[user_id] = True

        bot.send_message(
            user_id,
            "✅ Вы зарегистрированы как **клиент Сбербанка**.\n\n"
            "Опишите ваш вопрос по продуктам и сервисам — я постараюсь помочь.",
            parse_mode="Markdown"
        )

    if call.data == "reg_employee":
        users_role[user_id] = "employee"
        users_state[user_id] = "operator"
        llm_enabled[user_id] = False

        bot.send_message(
            user_id,
            "✅ Вы зарегистрированы как **сотрудник**.\n\n"
            "Команды:\n"
            "/reply <user_id> <текст> — ответ клиенту\n"
            "/end <user_id> — завершить диалог с клиентом.",
            parse_mode="HTML"
        )


@bot.message_handler(commands=["reply"])
def operator_reply(msg):
    if msg.chat.id != OPERATOR_ID:
        return

    try:
        _, user_id, text = msg.text.split(maxsplit=2)
    except ValueError:
        bot.send_message(
            OPERATOR_ID,
            "❌ Некорректный формат.\n"
            "Шаблон:\n"
            "/reply <user_id> <текст ответа клиенту>",
            parse_mode="HTML"
        )
        return

    bot.send_message(
        int(user_id),
        f"👨‍💼 Оператор:\n\n{text}"
    )


@bot.message_handler(commands=["analise"])
def start_analysis(msg):
    user_id = msg.chat.id

    if users_role.get(user_id) == "employee":
        return

    analysis_waiting_file[user_id] = True

    bot.send_message(
        user_id,
        "📂 Для анализа расходов отправьте JSON-файл с историей трат **как документ**.\n\n"
        "Формат операции:\n"
        """
        `{\"date\": \"01.10\", 
        \"time\": \"09:00\", 
        \"description\": \"...\", 
        \"amount\": -85000, 
        \"category\": \"аренда\"}`""",
        parse_mode="Markdown"
    )


@bot.message_handler(commands=["end"])
def handle_end(msg):
    user_id = msg.chat.id
    args = msg.text.split()

    if msg.chat.id == OPERATOR_ID and len(args) == 2:
        # оператор завершает диалог пользователя
        target_user = int(args[1])
        if users_state.get(target_user) == "operator":
            end_dialog(target_user)
            bot.send_message(
                OPERATOR_ID,
                f"✅ Диалог с клиентом {target_user} завершён."
            )
        else:
            bot.send_message(
                OPERATOR_ID,
                f"⚠️ Клиент {target_user} сейчас не в диалоге с оператором."
            )
        return

    # обычный пользователь завершает диалог
    end_dialog(user_id)


@bot.callback_query_handler(func=lambda c: c.data == "end_dialog")
def handle_end_button(call):
    # кнопка только для оператора
    if call.message.chat.id == OPERATOR_ID:
        target_user_id = operator_busy
        if target_user_id:
            end_dialog(target_user_id)
            bot.send_message(
                OPERATOR_ID,
                f"✅ Диалог с клиентом {target_user_id} завершён."
            )
        else:
            bot.send_message(
                OPERATOR_ID,
                "⚠️ Сейчас нет активного диалога для завершения."
            )


@bot.callback_query_handler(func=lambda c: c.data == "call_operator")
def call_operator(call):
    global operator_busy

    user_id = call.message.chat.id

    if operator_busy is not None:
        bot.send_message(
            user_id,
            "⏳ Оператор сейчас помогает другому клиенту.\n"
            "Пожалуйста, подождите — ваш запрос в очереди."
        )
        return

    operator_busy = user_id
    users_state[user_id] = "operator"
    llm_enabled[user_id] = False

    question = last_user_question.get(user_id, "Вопрос не найден")
    ticket_id = create_ticket(user_id, question)

    bot.send_message(
        OPERATOR_ID,
        f"📩 Новое обращение клиента\n"
        f"Тикет #{ticket_id}\n"
        f"Клиент: {user_id}\n"
        f"Вопрос: {question}"
    )

    bot.send_message(
        user_id,
        "👨‍💼 Вас подключили к оператору службы поддержки банка.\n"
        "Дождитесь, пожалуйста, ответа специалиста в этом чате."
    )


@bot.callback_query_handler(func=lambda c: c.data.startswith("rate_"))
def rate_answer(call):
    user_id = call.message.chat.id

    try:
        rating = int(call.data.split("_", 1)[1])
    except (ValueError, IndexError):
        return

    if rating < 1 or rating > 5:
        return

    question = last_user_question.get(user_id, "")
    # текст сообщения, к которому прикреплены кнопки — это ответ бота
    answer = call.message.text or last_bot_answer.get(user_id, "")

    save_rating(user_id, question, answer, rating)

    # убираем ТОЛЬКО ряд с оценками, оставляя кнопки-ссылки
    try:
        original = call.message.reply_markup
        if original and original.keyboard:
            from telebot.types import InlineKeyboardMarkup, InlineKeyboardButton

            new_kb = InlineKeyboardMarkup()
            for row in original.keyboard:
                # оставляем в ряду только кнопки, не относящиеся к оценке
                new_row = []
                for btn in row:
                    # у URL-кнопок callback_data == None, у наших оценок — "rate_X"
                    if getattr(btn, "callback_data", None) and str(btn.callback_data).startswith("rate_"):
                        continue
                    new_row.append(
                        InlineKeyboardButton(
                            text=btn.text,
                            url=getattr(btn, "url", None),
                            callback_data=getattr(btn, "callback_data", None)
                        )
                    )
                if new_row:
                    new_kb.row(*new_row)

            bot.edit_message_reply_markup(
                chat_id=call.message.chat.id,
                message_id=call.message.message_id,
                reply_markup=new_kb
            )
    except Exception:
        pass

    bot.answer_callback_query(
        callback_query_id=call.id,
        text=f"Благодарим за вашу оценку сервиса: {rating}/5"
    )


@bot.message_handler(content_types=["text"])
def handle_user(msg):
    user_id = msg.chat.id
    text = msg.text

    if users_role.get(user_id) == "employee":
        return

    last_user_question[user_id] = text

    if users_state.get(user_id) == "operator":
        bot.send_message(OPERATOR_ID, f"👤 {user_id}: {text}")
        return

    if not llm_enabled.get(user_id, True):
        return

    category = classify_question(text)

    if category == "NON_BANK":
        bot.send_message(
            user_id,
            "Я помогаю только с вопросами по продуктам и сервисам Сбербанка."
        )
        return

    db_result = dbsearch(text)

    if db_result == "в базе нет подходящего ответа":
        bot.send_message(
            user_id,
            "К сожалению, в базе знаний нет точного ответа на ваш вопрос.\n"
            "Я могу подключить оператора поддержки, который продолжит диалог.",
            reply_markup=types.InlineKeyboardMarkup().add(
                types.InlineKeyboardButton("👨‍💼 Связаться с оператором", callback_data="call_operator")
            )
        )
        return

    answer = generate_answer(db_result, text)
    last_bot_answer[user_id] = answer

    # определяем, какие разделы сайта Сбера порекомендовать
    tags = get_recommendation_tags(text, answer)
    links_map = {
        "cards": ("💳 Карты", "https://www.sberbank.ru/ru/person/bank_cards"),
        "deposits": ("💰 Вклады", "https://www.sberbank.ru/ru/person/contributions"),
        "mortgage": ("🏠 Ипотека", "https://www.sberbank.ru/ru/person/mortgagelending"),
        "credits": ("📄 Кредиты", "https://www.sberbank.ru/ru/person/credits"),
        "payments": ("🧾 Платежи", "https://www.sberbank.ru/ru/person/payments"),
        "transfers": ("📨 Переводы", "https://www.sberbank.ru/ru/person/transfers"),
        "insurance": ("🛡 Страхование", "https://www.sberbank.ru/ru/person/insurance"),
        "investments": ("📈 Инвестиции", "https://www.sberbank.ru/ru/person/investments"),
        "support": ("📞 Поддержка", "https://www.sberbank.ru/ru/person/paymentsandtransfers/help"),
    }
    links = [links_map[t] for t in tags if t in links_map]

    bot.send_message(
        user_id,
        answer,
        reply_markup=answer_kb(links),
        parse_mode="Markdown"
    )


MEDIA_TYPES = ["photo", "video", "audio", "document", "sticker", "voice",
               "video_note", "animation", "contact", "location", "venue"]


@bot.message_handler(content_types=MEDIA_TYPES)
def handle_non_text(msg):
    user_id = msg.chat.id
    # сотрудникам ничего не отвечаем на медиа
    if users_role.get(user_id) == "employee":
        return

    # если пользователь прислал документ с тратами для анализа
    if msg.content_type == "document" and analysis_waiting_file.get(user_id):
        doc = msg.document
        file_name = (doc.file_name or "").lower()
        if not file_name.endswith(".json"):
            bot.send_message(
                user_id,
                "⚠️ Файл должен быть в формате JSON (расширение **.json**).\n"
                "Отправьте, пожалуйста, корректный файл с историей трат."
            )
            return

        try:
            file_info = bot.get_file(doc.file_id)
            downloaded = bot.download_file(file_info.file_path)
            data = json.loads(downloaded.decode("utf-8"))
        except Exception:
            bot.send_message(
                user_id,
                "❌ Не удалось обработать файл как JSON.\n"
                "Проверьте, что файл содержит корректный JSON, и попробуйте снова."
            )
            return

        if not isinstance(data, list):
            bot.send_message(
                user_id,
                "❌ Ожидался список операций (JSON-массив).\n"
                "Проверьте структуру файла и отправьте его ещё раз."
            )
            return

        analysis_waiting_file[user_id] = False

        report = analyze_expenses(data)
        bot.send_message(user_id, report, parse_mode="Markdown")
        return

    # по умолчанию медиа не обрабатываем
    bot.send_message(
        user_id,
        "⚠️ Я работаю только с текстом.\n"
    )
