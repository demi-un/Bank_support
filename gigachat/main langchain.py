import requests
import base64
import json

from langchain.schema import HumanMessage, SystemMessage
from langchain_gigachat import GigaChat

import urllib3
urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)


# -----------------------------------------------------------------------------
# получение всех констант
API_KEY = None
CLIENT_SECRET = None
CLIENT_ID = None


with open("../.env") as f:
    for line in f:
        if API_KEY and CLIENT_SECRET and CLIENT_ID:
            break
        line = line.strip()
        if not line or line.startswith("#"):
            continue
        if line.startswith("API_KEY="):
            API_KEY = line[len("API_KEY="):].strip()
        if line.startswith("CLIENT_SECRET="):
            CLIENT_SECRET = line[len("CLIENT_SECRET="):].strip()
        if line.startswith("CLIENT_ID="):
            CLIENT_ID = line[len("CLIENT_ID="):].strip()


def get_acess_token(API_KEY):
    url = "https://ngw.devices.sberbank.ru:9443/api/v2/oauth"

    payload = "scope=GIGACHAT_API_PERS"

    headers = {
        "Content-Type": "application/x-www-form-urlencoded",
        "Accept": "application/json",
        "RqUID": "f248ab20-27a2-413f-8b2e-7482c936864e",
        "Authorization": f"Basic {API_KEY}"
    }

    response = requests.post(url, headers=headers, data=payload, verify=False)

    data = response.json()

    ACCESS_TOKEN = data.get("access_token")

    return ACCESS_TOKEN


auth_str = f"{CLIENT_ID}:{CLIENT_SECRET}"
API_KEY = base64.b64encode(auth_str.encode()).decode()
ACCESS_TOKEN = get_acess_token(API_KEY=API_KEY)


def get_const():
    print(f"API_KEY: {API_KEY}")
    print(f"CLIENT_SECRET: {CLIENT_SECRET}")
    print(f"CLIENT_ID: {CLIENT_ID}")
    print(f"ACCESS_TOKEN: {ACCESS_TOKEN}")
    print('---------------------------------------------------------------')

# get_const()

# -----------------------------------------------------------------------------
# основной код

giga = GigaChat(credentials=API_KEY,
                model="GigaChat",
                verify_ssl_certs=False)


messages = [SystemMessage(content="""
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
""")]


while True:
    user_input = input("Пользователь: ")
    if user_input == "q":
        break
    messages.append(HumanMessage(content=user_input))
    answer = giga(messages)
    messages.append(answer)
    print("отклик:", answer.content)
