import requests
import base64

from langchain.schema import HumanMessage, SystemMessage
from langchain_gigachat import GigaChat

import urllib3
urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)


# -----------------------------------------------------------------------------
# получение всех констант
API_KEY = None
CLIENT_SECRET = None
CLIENT_ID = None


with open(".env") as f:
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


def get_access_token(API_KEY):
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
ACCESS_TOKEN = get_access_token(API_KEY=API_KEY)


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


messages = [SystemMessage(content=SYSTEM_PROMPT)]
def llm(user_message, history):
    history.append(HumanMessage(content=user_message))
    answer = giga.invoke(history)
    history.append(answer)
    return (answer.content, history)


if __name__ == "__main__":
    answer, history = llm("как заблокировать карту")
    print(answer)
    # answer, history = llm("Расскажи подробнее про 1 пункт", history)
    # print(answer)

