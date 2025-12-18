from __future__ import annotations

OPERATOR_ID: int = 0
API_KEY: str = ""
TOKEN: str = ""


def load_env(path: str = ".env") -> None:
    """
    Простая загрузка API_KEY, TOKEN и OPERATOR_ID из .env-файла.
    """
    global OPERATOR_ID, API_KEY, TOKEN

    try:
        with open(path) as f:
            for line in f:
                line = line.strip()
                if not line or line.startswith("#"):
                    continue

                if API_KEY and TOKEN and OPERATOR_ID:
                    break

                if line.startswith("API_KEY="):
                    API_KEY = line.split("=", 1)[1]
                elif line.startswith("TOKEN="):
                    TOKEN = line.split("=", 1)[1]
                elif line.startswith("OPERATOR_ID="):
                    try:
                        OPERATOR_ID = int(line.split("=", 1)[1])
                    except ValueError:
                        OPERATOR_ID = 0
    except FileNotFoundError:
        # оставляем значения по умолчанию — бот просто не поднимется без токенов
        pass


# загружаем значения при импорте
load_env()


