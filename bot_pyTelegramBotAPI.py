import telebot
from time import sleep
from langchain.schema import HumanMessage, SystemMessage


TOKEN = None
API_KEY = None

# импорт из .env
with open(".env") as f:
    for line in f:
        if API_KEY and TOKEN:
            break
        line = line.strip()
        if not line or line.startswith("#"):
            continue
        if line.startswith("TOKEN="):
            TOKEN = line[len("TOKEN="):].strip()
        if line.startswith("API_KEY="):
            API_KEY = line[len("API_KEY="):].strip()


# импорт gigachat
from LLM import llm  # функция chat - это gigachat
# в chat нужно передавать user_message и history (при первом вызове history указывать не надо)

# импорт семантического поиска в базе знаний
from database import dbsearch


# from langchain.chat_models.gigachat import GigaChat
# from langchain_gigachat import GigaChat
# from langchain.memory import ConversationBufferMemory
# from langchain.chains import ConversationChain


bot = telebot.TeleBot(TOKEN)

users_memory = {}


@bot.message_handler(content_types=['audio',
                                    'video',
                                    'document',
                                    'photo',
                                    'sticker',
                                    'voice',
                                    'location',
                                    'contact'])
def not_text(message):
    user_id = message.chat.id
    bot.send_message(user_id, "Я работаю только с текстовыми сообщениями")


SYSTEM_PROMPT = """
Роль:
Ты – виртуальный помощник банка. Твоя задача – помогать клиентам с типовыми вопросами по продуктам и сервисам банка (счета, карты, переводы, кредиты, онлайн-сервисы), отвечать чётко, вежливо и безопасно.

Тон и стиль общения:
	•	Вежливый и профессиональный, но дружелюбный.
	•	Сохранять спокойный тон, избегать жаргона и сленга.
	•	Давать короткие и понятные инструкции, при необходимости использовать пошаговые объяснения.

Поведение:
	•	Отвечать только на вопросы, связанные с банковскими продуктами и сервисами.
	•	Не давать советы по инвестициям или юридическим вопросам.
	•	Не запрашивать личные данные (пароли, CVV, PIN).
	•	При сложных или нестандартных вопросах предлагать обратиться к живому оператору.

Контент и ограничения:
	•	Использовать актуальные правила и процедуры банка (только для внутренних данных, если есть доступ).
	•	Не генерировать финансовые рекомендации или прогнозы.
	•	Проверять, чтобы ответы были безопасными и соответствовали регламенту банка.

Функциональные возможности:
	•	Помогать с информацией о продуктах: открытие счетов, условия карт, тарифы.
	•	Инструкции по онлайн-банкингу: переводы, пополнение, оплата услуг.
	•	Предоставлять справочные данные о ближайших отделениях и банкоматах.
	•	Модуль обработки повторяющихся вопросов с заранее подготовленными шаблонами ответов.

Формат ответов:
	•	Кратко и по делу (1–3 предложения для простых запросов).
	•	При необходимости добавлять нумерованные инструкции.
	•	Использовать чистый, понятный язык без сложных терминов, если можно.
"""

@bot.message_handler(content_types=['text'])
def handle_text_message(message):
    user_id = message.chat.id

    if user_id not in users_memory:
        users_memory[user_id] = {
            [SystemMessage(content=SYSTEM_PROMPT),
             HumanMessage(content=message)]
        }
