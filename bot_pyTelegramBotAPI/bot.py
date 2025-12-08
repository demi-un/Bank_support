import sys


TOKEN = None

# импорт токена из .env
with open("../.env") as f:
    for line in f:
        line = line.strip()
        if not line or line.startswith("#"):
            continue
        if line.startswith("TOKEN="):
            TOKEN = line.split("=", 1)[1]
            break


# импорт gigachat
sys.path.append("../gigachat")
from main import chat  # функция chat - это gigachat


# импорт семантического поиска в базе знаний
sys.path.append("../chromadb")
from db import dbsearch


print(dbsearch("Как заблокировать карту"))
