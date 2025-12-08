import asyncio
from aiogram import Bot, Dispatcher

from app.handlers import router


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


async def main():
    bot = Bot(token=TOKEN)
    dp = Dispatcher()
    dp.include_router(router)
    await dp.start_polling(bot)


if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        print("Бот выключен")
