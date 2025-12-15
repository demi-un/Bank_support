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
        if line.startswith("OPERATOR_ID"):
            OPERATOR_ID = int(line.strip().split("=", 1)[1])

# ================== DB ==================

from database import dbsearch

# ================== BOT ==================

bot = telebot.TeleBot(TOKEN)

# ================== LLM ==================

giga = GigaChat(
    credentials=API_KEY,
    model="GigaChat",
    verify_ssl_certs=False
)

# ===== SYSTEM PROMPTS =====

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

users_state = {}  # bot | operator
tickets = {}


# ================== HELPERS ==================

def classify_question(text: str) -> str:
    resp = giga.invoke([
        CLASSIFIER_PROMPT,
        HumanMessage(content=text)
    ]).content.strip()
    return resp


def generate_answer(context: str, question: str) -> str:
    resp = giga.invoke([
        ANSWER_PROMPT,
        HumanMessage(content=f"Контекст:\n{context}\n\nВопрос:\n{question}")
    ])
    return resp.content


def operator_kb():
    kb = types.InlineKeyboardMarkup()
    kb.add(types.InlineKeyboardButton(
        "Связаться с оператором",
        callback_data="call_operator"
    ))
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


# ================== /start ==================

@bot.message_handler(commands=["start"])
def start(msg):
    users_state[msg.chat.id] = "bot"
    bot.send_message(
        msg.chat.id,
        "Здравствуйте! Задайте вопрос по банковским продуктам."
    )


# ================== CALLBACK ==================

@bot.callback_query_handler(func=lambda c: c.data == "call_operator")
def call_operator(call):
    user_id = call.message.chat.id
    users_state[user_id] = "operator"

    ticket_id = create_ticket(user_id, call.message.text)

    bot.send_message(
        OPERATOR_ID,
        f"📩 Тикет #{ticket_id}\nПользователь: {user_id}\nВопрос: {call.message.text}"
    )

    bot.send_message(
        user_id,
        "Вы подключены к живому оператору."
    )


# ================== USER MESSAGE ==================

@bot.message_handler(content_types=["text"])
def handle_user(msg):
    user_id = msg.chat.id
    text = msg.text

    # оператор
    if users_state.get(user_id) == "operator":
        bot.send_message(OPERATOR_ID, f"👤 {user_id}: {text}")
        return

    # 1️⃣ классификация
    category = classify_question(text)

    # ❌ не банковский
    if category == "NON_BANK":
        bot.send_message(
            user_id,
            "Я могу помочь только с вопросами по банковским продуктам и сервисам."
        )
        return

    # 2️⃣ банковский → БД
    db_result = dbsearch(text)

    # ❌ БД пустая — НИКАКОГО LLM
    if db_result == "в базе нет подходящего ответа":
        bot.send_message(
            user_id,
            "К сожалению, по вашему вопросу нет информации. Я могу подключить оператора.",
            reply_markup=operator_kb()
        )
        return

    # 3️⃣ есть данные → формируем ответ
    answer = generate_answer(db_result, text)
    bot.send_message(user_id, answer)


# ================== OPERATOR ==================

@bot.message_handler(commands=["reply"])
def operator_reply(msg):
    if msg.chat.id != OPERATOR_ID:
        return

    _, user_id, text = msg.text.split(maxsplit=2)
    bot.send_message(int(user_id), f"👨‍💼 Оператор:\n{text}")


# ================== RUN ==================

if __name__ == "__main__":
    print("Бот запущен")
    bot.polling(none_stop=True)
