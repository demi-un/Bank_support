TOKEN = None

# импорт токена из .env
with open(".env") as f:
    for line in f:
        line = line.strip()
        if not line or line.startswith("#"):
            continue
        if line.startswith("TOKEN="):
            TOKEN = line.split("=", 1)[1]
            break


# импорт gigachat
from LLM import chat  # функция chat - это gigachat

# импорт семантического поиска в базе знаний
from database import dbsearch
