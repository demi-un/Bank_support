from unibank_bot.bot_core import bot  # noqa: F401


if __name__ == "__main__":
    print("Бот запущен")
    bot.polling(none_stop=True)
