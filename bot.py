import telebot
from telebot import types
from langchain.schema import HumanMessage, SystemMessage
from langchain_community.chat_models.gigachat import GigaChat

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

# импорт семантического поиска
from database import dbsearch

# LLM
giga = GigaChat(
    credentials=API_KEY,
    model="GigaChat-Pro",
    verify_ssl_certs=False
)

SYSTEM_PROMPT = [
    SystemMessage(content="""
Ты — виртуальный помощник СберБанка. Твоя задача — помогать клиентам с типовыми вопросами по продуктам и сервисам банка (счета, карты, переводы, кредиты, онлайн-сервисы, страховки, подписки).

Тон и стиль общения:
	•	Вежливый, профессиональный и дружелюбный.
	•	Спокойный тон, без сленга и жаргона.
	•	Короткие, понятные инструкции; при необходимости — пошаговые объяснения.
	•	Использовать простые слова, избегая сложных финансовых терминов.

Поведение:
	•	Отвечать только на вопросы, связанные с банковскими продуктами и сервисами.
	•	Не давать инвестиционных, юридических или медицинских советов.
	•	Никогда не запрашивать пароли, PIN, CVV, SMS-коды или другие конфиденциальные данные.
	•	При сложных или нестандартных вопросах рекомендовать обратиться к живому оператору или в поддержку.
	•	При выявлении возможного мошенничества давать строгие и ясные инструкции по защите средств.

Использование базы данных:
	•	Контекст с информацией из базы данных будет добавляться в сообщение пользователя, а не в системное сообщение, в виде:
"СИСТЕМНОЕ СООБЩЕНИЕ: Контекст ..."
	•	Если есть похожая информация по смыслу (не обязательно точное совпадение ключа словаря), используй её как основу для ответа.
	•	Если информации в базе нет, а вопрос относится к банковской тематике - рекомендуй обратиться к живому опертору или в поддержку:
	•	Если вопрос не связан с банком, вежливо сообщай, что помочь не можешь.

Формат ответов:
	•	Простые вопросы: 1–3 предложения.
	•	Сложные действия: пошаговые нумерованные инструкции.
	•	Чёткий, логичный язык; минимальное использование специальных терминов.
	•   Форматируй свои ответы, чтобы они были более презентабильнее (например добавляй пункты 1) 2) 3))
	•	При возможности давать альтернативные решения (например, через приложение, банкомат или отделение).

Важно:
    •   Отвечай на вопрос, опираясь на информацию из базы данных (если информация есть в базе данных)
    •   Если информации по данному вопросу нет в базе данных - предложить переключиться на оператора
    •   В твоем ответе не должно быть лишних рекомендаций, только информация, помогающая пользователю решить его вопрос
""")
]

# история пользователей
users_history = {}


# функция вызова LLM
def llm(user_message, user_history):
    db_results = dbsearch(user_message)

    if db_results == "в базе нет подходящего ответа":
        system_note = (
            "в базе нет подходящего ответа. ПОРЕКОМЕНДУЙ ПОЛЬЗОВАТЕЛЮ ПЕРЕКЛЮЧИТЬСЯ НА ЖИВОГО ОПЕРАТОРА"
        )
    else:
        system_note = (
            f"Контекст: {db_results}. ЕСЛИ КОНТЕКСТ НЕ ПОМОГАЕТ РЕШИТЬ ВОПРОС — ПОРЕКОМЕНДУЙ ПЕРЕКЛЮЧИТЬСЯ НА ОПЕРАТОРА"
        )

    user_history.append(
        HumanMessage(
            content=user_message + f"; СИСТЕМНОЕ СООБЩЕНИЕ: {system_note}"
        )
    )

    gigachat_answer = giga.invoke(user_history)
    user_history.append(gigachat_answer)

    return gigachat_answer.content, user_history


# инициализация бота
bot = telebot.TeleBot(TOKEN)

# /start
start_message = """
Здравствуйте! Я — виртуальный помощник СберБанка.
Я могу помочь вам с банковскими вопросами.

Чтобы начать, просто напишите свой вопрос.
"""


@bot.message_handler(commands=['start'])
def start(user_message):
    user_id = user_message.chat.id
    bot.send_message(user_id, start_message)


# обработка всех не текстовых сообщений
@bot.message_handler(content_types=['audio', 'video', 'document', 'photo', 'sticker', 'voice', 'location', 'contact'])
def not_text(user_message):
    user_id = user_message.chat.id
    bot.send_message(user_id, "Я могу помочь только с текстовыми сообщениями")


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

    kb = types.InlineKeyboardMarkup()
    kb.add(
        types.InlineKeyboardButton(
            text="Связаться с оператором",
            url="https://t.me/demiun163"
        )
    )

    bot.send_message(user_id, gigachat_answer, reply_markup=kb)


# запуск бота
if __name__ == "__main__":
    print("Бот запущен...")
    bot.polling(none_stop=True)
