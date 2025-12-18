import telebot
from telebot import types
from langchain.schema import HumanMessage, SystemMessage
from langchain_community.chat_models.gigachat import GigaChat

from datetime import datetime
import json
import uuid

# ================== CONFIG ==================

OPERATOR_ID = 0
API_KEY = ""
TOKEN = ""

# ================== ENV ==================

with open(".env") as f:
    for line in f:
        if API_KEY and TOKEN and OPERATOR_ID:
            break
        if line.startswith("API_KEY="):
            API_KEY = line.strip().split("=", 1)[1]
        if line.startswith("TOKEN="):
            TOKEN = line.strip().split("=", 1)[1]
        if line.startswith("OPERATOR_ID="):
            OPERATOR_ID = int(line.strip().split("=", 1)[1])

# ================== DB ==================

from database import dbsearch

# ================== BOT ==================

bot = telebot.TeleBot(TOKEN)

# ================== LLM ==================

giga = GigaChat(
    credentials=API_KEY,
    model="GigaChat",
    verify_ssl_certs=False,
    timeout=10
)

# ================== PROMPTS ==================

CLASSIFIER_PROMPT = SystemMessage(content="""
Ты выступаешь в роли классификатора обращений клиентов банка.
Ответь ТОЛЬКО одним словом:
BANK — если вопрос относится к банковским продуктам, сервисам или операциям.
NON_BANK — если вопрос не связан с банковскими услугами.
""")

ANSWER_PROMPT = SystemMessage(content="""
Ты виртуальный консультант Сбербанка.

ТВОЯ ЗАДАЧА:
- Отвечать вежливо, профессионально, *кратко и по делу*.
- Использовать ТОЛЬКО предоставленный контекст, НЕ добавлять информацию от себя.
- Если в контексте нет прямого ответа, кратко об этом сообщить.

ФОРМАТ ОТВЕТА (Markdown для Telegram):
- Короткое вступление (1–2 предложения) — только если нужно.
- Основная часть — в виде маркированных списков или коротких абзацев.
- Выделяй ключевые слова с помощью `*жирного*`.
- Не используй слишком длинные тексты (до 5–7 предложений).
""")

EXPENSE_PROMPT = SystemMessage(content="""
Ты финансовый консультант Сбербанка.
Тебе передают агрегированные данные по расходам клиента (категории, суммы, доли в процентах).

ТВОЯ ЗАДАЧА:
- Коротко и понятно объяснить картину расходов.
- Отметить 2–4 самых важных наблюдения (где трат особенно много / мало).
- Дать практичные советы по финансовой грамотности применительно к этим данным.

ФОРМАТ ОТВЕТА (Markdown для Telegram):
- Заголовок: одна строка с `*...*`.
- 1 блок: краткий обзор (2–3 пункта).
- 1 блок: рекомендации (3–5 конкретных советов).
- Используй маркированные списки `- ...`.
- Выделяй важные слова с помощью `*жирного*`.
- Не пиши больше ~10–12 строк.
""")

# ================== STORAGE ==================

users_state = {}          # bot | operator
users_role = {}           # user | employee
llm_enabled = {}           # True / False
last_user_question = {}    # user_id: text
last_bot_answer = {}       # user_id: text
tickets = {}
operator_busy = None      # user_id или None
analysis_waiting_file = {}  # user_id: bool

RATINGS_FILE = "ratings.jsonl"

# ================== HELPERS ==================

def classify_question(text: str) -> str:
    try:
        resp = giga.invoke([
            CLASSIFIER_PROMPT,
            HumanMessage(content=text)
        ])
        return resp.content.strip()
    except Exception:
        return "BANK"

def generate_answer(context: str, question: str) -> str:
    try:
        resp = giga.invoke([
            ANSWER_PROMPT,
            HumanMessage(content=f"Контекст:\n{context}\n\nВопрос:\n{question}")
        ])
        return resp.content
    except Exception:
        return "⚠️ Сервис временно недоступен. Попробуйте повторить запрос чуть позже."

def operator_kb():
    kb = types.InlineKeyboardMarkup()
    kb.add(types.InlineKeyboardButton(
        "✅ Завершить диалог",
        callback_data="end_dialog"
    ))
    return kb


def rating_kb():
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


def save_rating(user_id: int, question: str, answer: str, rating: int):
    record = {
        "timestamp": datetime.now().isoformat(),
        "user_id": user_id,
        "question": question,
        "answer": answer,
        "rating": rating,
    }

    try:
        with open(RATINGS_FILE, "a", encoding="utf-8") as f:
            f.write(json.dumps(record, ensure_ascii=False) + "\n")
    except Exception:
        # если что-то пошло не так при сохранении — не ломаем основной поток
        pass


def analyze_expenses(expenses: list[dict]) -> str:
    """
    Анализ трат на основе агрегированных данных и GigaChat.
    Ожидается список операций с полями: date, time, description, amount, category.
    """
    if not expenses:
        return "В файле нет операций — нечего анализировать."

    total_spent = 0
    by_category = {}

    for op in expenses:
        amount = op.get("amount", 0)
        category = op.get("category", "прочее")
        # считаем только расходы (отрицательные суммы)
        if amount < 0:
            value = abs(amount)
            total_spent += value
            by_category[category] = by_category.get(category, 0) + value

    if total_spent == 0:
        return "В файле не найдено расходов (отрицательных сумм) — возможно, это не тот файл."

    # сортируем категории по убыванию трат
    top_cats = sorted(by_category.items(), key=lambda x: x[1], reverse=True)

    # готовим агрегированные данные в виде текста-контекста для GigaChat
    lines = []
    lines.append(f"Общая сумма расходов в выборке: {total_spent:,.0f} ₽".replace(",", " "))
    lines.append("Категории (сумма, доля %):")

    for cat, amt in top_cats:
        share = amt / total_spent * 100
        lines.append(f"- {cat}: {amt:,.0f} ₽ ({share:.1f}%)".replace(",", " "))

    context = "\n".join(lines)

    try:
        resp = giga.invoke([
            EXPENSE_PROMPT,
            HumanMessage(content=context)
        ])
        return resp.content
    except Exception:
        # запасной простой текст, если анализ через GigaChat недоступен
        fallback_lines = []
        fallback_lines.append("📊 *Краткий обзор расходов*")
        fallback_lines.append("")
        fallback_lines.append(f"Общая сумма расходов: *{total_spent:,.0f} ₽*".replace(",", " "))
        fallback_lines.append("")
        fallback_lines.append("По основным категориям:")
        for cat, amt in top_cats[:5]:
            share = amt / total_spent * 100
            fallback_lines.append(f"- *{cat}*: {amt:,.0f} ₽ ({share:.1f}%)".replace(",", " "))
        fallback_lines.append("")
        fallback_lines.append("💡 Попробуйте перераспределить траты и оставить запас 10–20% дохода на сбережения.")
        return "\n".join(fallback_lines)

def register_kb():
    kb = types.InlineKeyboardMarkup()
    kb.add(
        types.InlineKeyboardButton("👤 Клиент Сбербанка", callback_data="reg_user"),
        types.InlineKeyboardButton("🏦 Сотрудник Сбербанка", callback_data="reg_employee")
    )
    return kb

def create_ticket(user_id, question):
    ticket_id = str(uuid.uuid4())[:8]
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

# ================== /start ==================

@bot.message_handler(commands=["start"])
def start(msg):
    bot.send_message(
        msg.chat.id,
        "*Виртуальный ассистент Сбербанка*\n\n"
        "Я помогу:\n"
        "• ответить на вопросы по продуктам и сервисам\n"
        "• передать запрос оператору\n"
        "• сделать краткий анализ ваших расходов по JSON-файлу (/analise)\n\n"
        "_Выберите роль ниже:_",
        reply_markup=register_kb()
    )

# ================== REGISTRATION ==================

@bot.callback_query_handler(func=lambda c: c.data in ["reg_user", "reg_employee"])
def register(call):
    user_id = call.message.chat.id

    if call.data == "reg_user":
        users_role[user_id] = "user"
        users_state[user_id] = "bot"
        llm_enabled[user_id] = True

        bot.send_message(
            user_id,
            "✅ Вы зарегистрированы как *клиент Сбербанка*.\n\n"
            "Опишите ваш вопрос по продуктам и сервисам — я постараюсь помочь."
        )

    if call.data == "reg_employee":
        users_role[user_id] = "employee"
        users_state[user_id] = "operator"
        llm_enabled[user_id] = False

        bot.send_message(
            user_id,
            "✅ Вы зарегистрированы как *сотрудник Сбербанка*.\n\n"
            "Команды:\n"
            "/reply &lt;user_id&gt; &lt;текст&gt; — ответ клиенту\n"
            "/end &lt;user_id&gt; — завершить диалог с клиентом."
        )

# ================== OPERATOR REPLY ==================

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
            "/reply &lt;user_id&gt; &lt;текст ответа клиенту&gt;"
        )
        return

    bot.send_message(
        int(user_id),
        f"👨‍💼 Сообщение от оператора поддержки Сбербанка:\n\n{text}"
    )


@bot.message_handler(commands=["analise"])
def start_analysis(msg):
    user_id = msg.chat.id

    if users_role.get(user_id) == "employee":
        return

    analysis_waiting_file[user_id] = True

    bot.send_message(
        user_id,
        "📂 Для анализа расходов отправьте JSON-файл с историей трат *как документ*.\n\n"
        "Формат операции:\n"
        "`{\"date\": \"01.10\", \"time\": \"09:00\", \"description\": \"...\", \"amount\": -85000, \"category\": \"аренда\"}`"
    )

# ================== OPERATOR END DIALOG ==================

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

# ================== CALL OPERATOR ==================

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
        "👨‍💼 Вас подключили к оператору службы поддержки Сбербанка.\n"
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

    # убираем клавиатуру с оценками
    try:
        bot.edit_message_reply_markup(
            chat_id=call.message.chat.id,
            message_id=call.message.message_id,
            reply_markup=None
        )
    except Exception:
        pass

    bot.answer_callback_query(
        callback_query_id=call.id,
        text=f"Благодарим за вашу оценку сервиса: {rating}/5"
    )

# ================== USER MESSAGE ==================

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
            "Сейчас я помогаю только с вопросами по продуктам и сервисам Сбербанка.\n"
            "Пожалуйста, переформулируйте запрос так, чтобы он относился к банковскому обслуживанию."
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
    bot.send_message(
        user_id,
        answer,
        reply_markup=rating_kb()
    )

# ================== НЕ ТЕКСТОВЫЕ СООБЩЕНИЯ ==================

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
                "⚠️ Файл должен быть в формате JSON (расширение *.json*).\n"
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
        "Для анализа расходов используйте команду /analise и отправьте JSON-файл документом."
    )

# ================== RUN ==================

if __name__ == "__main__":
    print("Бот запущен")
    bot.polling(none_stop=True)
