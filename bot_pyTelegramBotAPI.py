import telebot
from time import sleep


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


@bot.message_handler(content_types=['text'])
def handle_text_message(message):
    user_id = message.chat.id

    if user_id not in users_memory:
        users_memory[user_id] = {

        }
