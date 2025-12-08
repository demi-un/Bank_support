import requests
import base64

import json

from ddgs import DDGS
from IPython.display import display, Markdown

from gigachat import GigaChat
from gigachat.models import Chat, Function, FunctionParameters, Messages, MessagesRole

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


def get_acessed_token(API_KEY):
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


ACCESS_TOKEN = get_acessed_token(API_KEY=API_KEY)


def get_const():
    print(f"API_KEY: {API_KEY}")
    print(f"CLIENT_SECRET: {CLIENT_SECRET}")
    print(f"CLIENT_ID: {CLIENT_ID}")
    print(f"ACCESS_TOKEN: {ACCESS_TOKEN}")
    print('---------------------------------------------------------------')

get_const()
# -----------------------------------------------------------------------------


# основной код
def get_chat_complection(auth_token, user_message, convertation_history=None):
    url = "https://gigachat.devices.sberbank.ru/api/v1/chat/completions"

    if convertation_history is None:
        convertation_history = []
    

    convertation_history.append({
                "role": "user",
                "content": user_message
            })

    payload = json.dumps({
        "model": "GigaChat",
        "messages": convertation_history,
        "temperature": 0.3,
        "max_tokens": 250
    })

    headers = {
        'Content-Type': 'application/json',
        'Accept': 'application/json',
        "Authorization": f"Bearer {auth_token}"
    }

    try:
        responce = requests.request("POST", url, headers=headers, data=payload, verify=False)
        responce_data = responce.json()
        print(responce_data)

        convertation_history.append({
            "role": "assistant",
            "content": responce_data['choices'][0]['message']['content']
        })

        return responce, convertation_history
    except requests.RequestException as e:
        print(f"Произошла ошибка: {str(e)}")
        return None, convertation_history
    

convertation_history = []

responce, convertation_history = get_chat_complection(ACCESS_TOKEN, "привет, меня зовут Рома", convertation_history)

responce, convertation_history = get_chat_complection(ACCESS_TOKEN, "как меня зовут?", convertation_history)

print(convertation_history)
