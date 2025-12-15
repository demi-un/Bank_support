import telebot
from telebot import types
from langchain.schema import HumanMessage, SystemMessage
from langchain_community.chat_models.gigachat import GigaChat

from datetime import datetime
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
Ты классификатор.
Ответь ТОЛЬКО одним словом:
BANK — если вопрос относится к банковским продуктам или сервисам
NON_BANK — если не относится
""")

ANSWER_PROMPT = SystemMessage(content="""
Ты помощник банка.
Отвечай ТОЛЬКО используя предоставленный контекст.
НЕ ДОБАВЛЯЙ информацию от себя.
""")

# ================== STORAGE ==================

users_state = {}          # bot | operator
users_role = {}           # user | employee
llm_enabled = {}          # True / False
last_user_question = {}  # user_id: text
tickets = {}
operator_busy = None      # user_id или None

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
        return "⚠️ Временная ошибка сервиса. Попробуйте позже."

def operator_kb():
    kb = types.InlineKeyboardMarkup()
    kb.add(types.InlineKeyboardButton(
        "Завершить диалог",
        callback_data="end_dialog"
    ))
    return kb

def register_kb():
    kb = types.InlineKeyboardMarkup()
    kb.add(
        types.InlineKeyboardButton("🙋 Пользователь", callback_data="reg_user"),
        types.InlineKeyboardButton("🏦 Сотрудник банка", callback_data="reg_employee")
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

    bot.send_message(user_id, "✅ Диалог завершен. Вы можете задать новый вопрос.")

# ================== /start ==================

@bot.message_handler(commands=["start"])
def start(msg):
    bot.send_message(
        msg.chat.id,
        "Кто вы?",
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
            "✅ Вы зарегистрированы как пользователь.\nЗадайте вопрос по банковским продуктам."
        )

    if call.data == "reg_employee":
        users_role[user_id] = "employee"
        users_state[user_id] = "operator"
        llm_enabled[user_id] = False

        bot.send_message(
            user_id,
            "✅ Вы зарегистрированы как сотрудник банка.\nИспользуйте /reply для ответа клиентам и /end <user_id> для завершения диалога."
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
            "❌ Формат:\n/reply <user_id> <текст>"
        )
        return

    bot.send_message(
        int(user_id),
        f"👨‍💼 Оператор:\n{text}"
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
            bot.send_message(OPERATOR_ID, f"✅ Диалог с пользователем {target_user} завершен.")
        else:
            bot.send_message(OPERATOR_ID, f"⚠️ Пользователь {target_user} не находится в диалоге с оператором.")
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
            bot.send_message(OPERATOR_ID, f"✅ Диалог с пользователем {target_user_id} завершен.")
        else:
            bot.send_message(OPERATOR_ID, "⚠️ Нет активного диалога для завершения.")

# ================== CALL OPERATOR ==================

@bot.callback_query_handler(func=lambda c: c.data == "call_operator")
def call_operator(call):
    global operator_busy

    user_id = call.message.chat.id

    if operator_busy is not None:
        bot.send_message(
            user_id,
            "⏳ Оператор сейчас занят другим клиентом. Пожалуйста, подождите."
        )
        return

    operator_busy = user_id
    users_state[user_id] = "operator"
    llm_enabled[user_id] = False

    question = last_user_question.get(user_id, "Вопрос не найден")
    ticket_id = create_ticket(user_id, question)

    bot.send_message(
        OPERATOR_ID,
        f"📩 Тикет #{ticket_id}\n"
        f"Пользователь: {user_id}\n"
        f"Вопрос: {question}"
    )

    bot.send_message(
        user_id,
        "👨‍💼 Вы подключены к живому оператору."
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
            "Я могу помочь только с вопросами по банковским продуктам и сервисам."
        )
        return

    db_result = dbsearch(text)

    if db_result == "в базе нет подходящего ответа":
        bot.send_message(
            user_id,
            "К сожалению, по вашему вопросу нет информации. Я могу подключить оператора.",
            reply_markup=types.InlineKeyboardMarkup().add(
                types.InlineKeyboardButton("Связаться с оператором", callback_data="call_operator")
            )
        )
        return

    answer = generate_answer(db_result, text)
    bot.send_message(user_id, answer)

# ================== НЕ ТЕКСТОВЫЕ СООБЩЕНИЯ ==================

MEDIA_TYPES = ["photo", "video", "audio", "document", "sticker", "voice",
               "video_note", "animation", "contact", "location", "venue"]

@bot.message_handler(content_types=MEDIA_TYPES)
def handle_non_text(msg):
    user_id = msg.chat.id
    if users_role.get(user_id) != "employee":
        bot.send_message(user_id, "⚠️ Я работаю только с текстовыми сообщениями")

# ================== RUN ==================

if __name__ == "__main__":
    print("Бот запущен")
    bot.polling(none_stop=True)
