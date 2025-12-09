import telebot
from langchain.schema import HumanMessage, SystemMessage
from langchain_community.chat_models.gigachat import GigaChat

# -----------------------------------------------------------------------------
# получение API_KEY и TOKEN из .env
API_KEY = ""
TOKEN = ""

with open(".env") as f:
    for line in f:
        line = line.strip()
        if not line or line.startswith("#"):
            continue
        if line.startswith("API_KEY="):
            API_KEY = line[len("API_KEY="):].strip()
        if line.startswith("TOKEN="):
            TOKEN = line[len("TOKEN="):].strip()

# -----------------------------------------------------------------------------
# импорт семантического поиска (если используешь)
from database import dbsearch

# -----------------------------------------------------------------------------
# LLM
giga = GigaChat(
    credentials=API_KEY,
    model="GigaChat",
    verify_ssl_certs=False
)

SYSTEM_PROMPT = [
    SystemMessage(content="""
Роль:
Ты – виртуальный помощник банка. Твоя задача – помогать клиентам с типовыми вопросами по продуктам и сервисам банка (счета, карты, переводы, кредиты, онлайн-сервисы), отвечать чётко, вежливо и безопасно.

Тон и стиль общения:
    • Вежливый и профессиональный, но дружелюбный.
    • Сохранять спокойный тон, избегать жаргона и сленга.
    • Давать короткие и понятные инструкции, при необходимости использовать пошаговые объяснения.

Поведение:
    • Отвечать только на вопросы, связанные с банковскими продуктами и сервисами.
    • Не давать советы по инвестициям или юридическим вопросам.
    • Не запрашивать личные данные (пароли, CVV, PIN).
    • При сложных или нестандартных вопросах предлагать обратиться к живому оператору.

Формат ответов:
    • Кратко и по делу (1–3 предложения для простых запросов).
    • При необходимости добавлять нумерованные инструкции.
    • Использовать чистый, понятный язык без сложных терминов, если можно.
""")
]

# -----------------------------------------------------------------------------
# история пользователей
users_history = {}

# функция вызова LLM
def llm(user_message, user_history):
    # поиск в базе по вопросу пользователя
    db_results = dbsearch(user_message)

    user_history.append(HumanMessage(content=user_message + f"; СИСТЕМНОЕ СООБЩЕНИЕ: Контекст из базы данных (используй его, если он помогает ответить на заданный вопрос):\n{db_results}"))

    gigachat_answer = giga.invoke(user_history)
    user_history.append(gigachat_answer)

    return gigachat_answer.content, user_history

# -----------------------------------------------------------------------------
# инициализация бота
bot = telebot.TeleBot(TOKEN)

# -----------------------------------------------------------------------------
# обработка всех не текстовых сообщений
@bot.message_handler(content_types=['audio', 'video', 'document', 'photo', 'sticker', 'voice', 'location', 'contact'])
def not_text(user_message):
    user_id = user_message.chat.id
    bot.send_message(user_id, "Я работаю только с текстовыми сообщениями")

# -----------------------------------------------------------------------------
# обработка текстовых сообщений
@bot.message_handler(content_types=['text'])
def handle_text_message(user_message):
    user_id = user_message.chat.id

    # инициализация истории пользователя
    if user_id not in users_history:
        users_history[user_id] = SYSTEM_PROMPT.copy()

    user_history = users_history[user_id]

    # вызов LLM
    gigachat_answer, user_history = llm(user_message.text, user_history)

    # обновляем историю
    users_history[user_id] = user_history

    # отправляем ответ пользователю
    bot.send_message(user_id, gigachat_answer)

# -----------------------------------------------------------------------------
# запуск бота
if __name__ == "__main__":
    print("Бот запущен...")
    bot.polling(none_stop=True)
