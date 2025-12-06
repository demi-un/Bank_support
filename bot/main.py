# main.py - для aiogram 3.22.0
import asyncio
import logging
import os
from datetime import datetime

from aiogram import Bot, Dispatcher, types, F
from aiogram.fsm.storage.memory import MemoryStorage
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
from aiogram.filters import Command

from rag_system import SberSupportRAG
from dotenv import load_dotenv

# Загружаем переменные окружения
load_dotenv()

# Настройка логирования
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

# ID администратора
ADMIN_ID = os.getenv("ADMIN_ID", "123456789")
try:
    ADMIN_ID = int(ADMIN_ID)
except:
    ADMIN_ID = 123456789
    logger.warning(f"Использую ID по умолчанию: {ADMIN_ID}")

ADMIN_IDS = [ADMIN_ID]

# Инициализация бота
API_TOKEN = os.getenv("TELEGRAM_BOT_TOKEN")
if not API_TOKEN:
    logger.error("❌ Не найден TELEGRAM_BOT_TOKEN в .env файле!")
    API_TOKEN = input("Введите токен бота Telegram: ").strip()
    if not API_TOKEN:
        logger.error("Токен не предоставлен. Завершение работы.")
        exit(1)

bot = Bot(token=API_TOKEN)
storage = MemoryStorage()
dp = Dispatcher(storage=storage)

# Инициализация RAG системы
rag_system = None

# Состояния для FSM
class UserStates(StatesGroup):
    waiting_for_feedback = State()
    waiting_for_escalation = State()

# Статистика
bot_stats = {
    "total_questions": 0,
    "successful_answers": 0,
    "failed_answers": 0,
    "user_sessions": set()
}

# ========== КОМАНДЫ ==========

@dp.message(Command("start"))
async def cmd_start(message: types.Message):
    """Обработка команды /start"""
    user_id = message.from_user.id
    bot_stats["user_sessions"].add(user_id)
    
    welcome_text = """
🤖 *Добро пожаловать в помощник поддержки Сбера!*

Я - AI-помощник для сотрудников внутренней IT-поддержки банка.

*Что я умею:*
✅ Помогать со сбросом паролей
✅ Решать проблемы с VPN и доступом
✅ Консультировать по корпоративным системам
✅ Отвечать на типовые IT-вопросы

*Доступные команды:*
/help - справка по командам
/stats - статистика бота
/feedback - оставить обратную связь

Просто напишите ваш вопрос, и я постараюсь помочь!
"""
    
    await message.answer(welcome_text, parse_mode="Markdown")
    logger.info(f"Пользователь {user_id} запустил бота")

@dp.message(Command("help"))
async def cmd_help(message: types.Message):
    """Обработка команды /help"""
    help_text = """
*📋 Доступные команды:*

/start - начать работу с ботом
/help - показать это сообщение
/stats - статистика использования
/feedback - оставить обратную связь
/escalate - эскалировать проблему (создать тикет)

*💡 Как пользоваться:*
1. Просто напишите ваш вопрос (например: "Как сбросить пароль?")
2. Я поищу информацию в базе знаний
3. Предоставлю наиболее подходящий ответ

*📞 Контакты поддержки:*
• Телефон: 8-800-555-00-00
• ServiceNow: https://servicenow.sberbank.ru
"""
    await message.answer(help_text, parse_mode="Markdown")

@dp.message(Command("stats"))
async def cmd_stats(message: types.Message):
    """Показать статистику бота"""
    if message.from_user.id not in ADMIN_IDS:
        await message.answer("Эта команда доступна только администраторам.")
        return
    
    if bot_stats["total_questions"] > 0:
        success_rate = (bot_stats['successful_answers'] / bot_stats['total_questions'] * 100)
        success_text = f"{success_rate:.1f}%"
    else:
        success_text = "нет данных"
    
    stats_text = f"""
*📊 Статистика бота:*

👥 Уникальных пользователей: {len(bot_stats["user_sessions"])}
❓ Всего вопросов: {bot_stats["total_questions"]}
✅ Успешных ответов: {bot_stats["successful_answers"]}
❌ Неудачных ответов: {bot_stats["failed_answers"]}
📈 Успешность: {success_text}

*💾 RAG система:* {'✅ Активна' if rag_system else '❌ Неактивна'}
"""
    await message.answer(stats_text, parse_mode="Markdown")

@dp.message(Command("feedback"))
async def cmd_feedback(message: types.Message, state: FSMContext):
    """Начать процесс обратной связи"""
    await state.set_state(UserStates.waiting_for_feedback)
    await message.answer(
        "Пожалуйста, напишите вашу обратную связь или предложения по улучшению бота:"
    )

@dp.message(UserStates.waiting_for_feedback)
async def process_feedback(message: types.Message, state: FSMContext):
    """Обработка обратной связи"""
    feedback = message.text
    user_id = message.from_user.id
    
    logger.info(f"Обратная связь от {user_id}: {feedback}")
    
    with open("feedback.txt", "a", encoding="utf-8") as f:
        f.write(f"{datetime.now()} - User {user_id}: {feedback}\n")
    
    await message.answer("Спасибо за вашу обратную связь! Она поможет улучшить бота.")
    await state.clear()

@dp.message(Command("escalate"))
async def cmd_escalate(message: types.Message, state: FSMContext):
    """Эскалация проблемы"""
    await state.set_state(UserStates.waiting_for_escalation)
    
    keyboard = types.ReplyKeyboardMarkup(
        keyboard=[
            [
                types.KeyboardButton(text="Высокая"),
                types.KeyboardButton(text="Средняя"),
                types.KeyboardButton(text="Низкая")
            ],
            [types.KeyboardButton(text="Отмена")]
        ],
        resize_keyboard=True
    )
    
    await message.answer(
        "Пожалуйста, опишите проблему для эскалации и выберите приоритет:",
        reply_markup=keyboard
    )

@dp.message(UserStates.waiting_for_escalation)
async def process_escalation(message: types.Message, state: FSMContext):
    """Обработка эскалации"""
    if message.text.lower() == "отмена":
        await message.answer("Эскалация отменена.", reply_markup=types.ReplyKeyboardRemove())
        await state.clear()
        return
    
    user_id = message.from_user.id
    ticket_id = f"TICKET-{datetime.now().strftime('%Y%m%d-%H%M%S')}"
    
    logger.info(f"Создан тикет {ticket_id} от пользователя {user_id}: {message.text}")
    
    with open("tickets.txt", "a", encoding="utf-8") as f:
        f.write(f"{ticket_id} | {datetime.now()} | User {user_id} | {message.text}\n")
    
    await message.answer(
        f"✅ Проблема эскалирована!\n\n"
        f"📋 Номер тикета: *{ticket_id}*\n"
        f"👨‍💼 Ответственный: Вторая линия поддержки\n"
        f"⏱️ Ожидаемое время решения: 24 часа\n\n"
        f"Для отслеживания статуса обращайтесь в ServiceNow.",
        parse_mode="Markdown",
        reply_markup=types.ReplyKeyboardRemove()
    )
    
    await state.clear()

# ========== ОБРАБОТКА ВОПРОСОВ ==========

@dp.message(F.text)
async def handle_question(message: types.Message):
    """Обработка всех текстовых сообщений (вопросов)"""
    global rag_system
    
    user_id = message.from_user.id
    user_question = message.text.strip()
    bot_stats["total_questions"] += 1
    
    logger.info(f"❓ Вопрос от {user_id}: {user_question}")
    
    if rag_system is None:
        try:
            rag_system = SberSupportRAG()
            logger.info("✅ RAG система инициализирована")
        except Exception as e:
            logger.error(f"❌ Ошибка инициализации RAG: {e}")
            await message.answer("Извините, система временно недоступна. Попробуйте позже.")
            bot_stats["failed_answers"] += 1
            return
    
    await bot.send_chat_action(chat_id=message.chat.id, action="typing")
    
    try:
        result = rag_system.get_answer(user_question)
        answer = result["answer"]
        
        formatted_answer = f"*❓ Ваш вопрос:* {user_question}\n\n"
        formatted_answer += f"*🤖 Ответ:* {answer}\n\n"
        formatted_answer += "*💡 Если ответ не помог:*\n"
        formatted_answer += "• Используйте /escalate для эскалации проблемы\n"
        formatted_answer += "• Позвоните в поддержку: 8-800-555-00-00\n"
        formatted_answer += "• Обратитесь в ServiceNow\n"
        
        keyboard = types.InlineKeyboardMarkup(inline_keyboard=[
            [
                types.InlineKeyboardButton(text="👍 Помогло", callback_data="helpful"),
                types.InlineKeyboardButton(text="👎 Не помогло", callback_data="not_helpful")
            ],
            [
                types.InlineKeyboardButton(text="🔄 Эскалировать", callback_data="escalate_now")
            ]
        ])
        
        await message.answer(formatted_answer, parse_mode="Markdown", reply_markup=keyboard)
        
        logger.info(f"✅ Ответ отправлен пользователю {user_id}")
        bot_stats["successful_answers"] += 1
        
    except Exception as e:
        logger.error(f"❌ Ошибка при обработке вопроса: {e}")
        
        fallback_answer = (
            "Извините, произошла ошибка при обработке вашего запроса.\n\n"
            "Попробуйте:\n"
            "1. Переформулировать вопрос\n"
            "2. Обратиться напрямую в поддержку: 8-800-555-00-00\n"
            "3. Использовать /escalate для создания тикета"
        )
        
        await message.answer(fallback_answer)
        bot_stats["failed_answers"] += 1

# ========== CALLBACK ОБРАБОТЧИКИ ==========

@dp.callback_query(F.data.in_(["helpful", "not_helpful", "escalate_now"]))
async def process_callback(callback_query: types.CallbackQuery, state: FSMContext):
    """Обработка callback'ов от кнопок"""
    user_id = callback_query.from_user.id
    action = callback_query.data
    
    if action == "helpful":
        await callback_query.answer("Спасибо за оценку!")
        logger.info(f"Пользователь {user_id} оценил ответ как полезный")
        
    elif action == "not_helpful":
        await callback_query.answer("Извините, что не смогли помочь")
        
        keyboard = types.InlineKeyboardMarkup(inline_keyboard=[
            [types.InlineKeyboardButton(text="🔄 Эскалировать", callback_data="escalate_confirm")]
        ])
        
        await callback_query.message.answer(
            "Извините, что не смогли помочь. Хотите эскалировать проблему?",
            reply_markup=keyboard
        )
        
    elif action == "escalate_now":
        await cmd_escalate(callback_query.message, state)
        
    elif action == "escalate_confirm":
        await cmd_escalate(callback_query.message, state)

# ========== ЗАПУСК БОТА ==========

async def on_startup():
    """Действия при запуске бота"""
    logger.info("🚀 Бот запускается...")
    
    global rag_system
    try:
        rag_system = SberSupportRAG()
        logger.info("✅ RAG система успешно инициализирована")
    except Exception as e:
        logger.error(f"❌ Ошибка инициализации RAG системы: {e}")
        rag_system = None
    
    logger.info("🤖 Бот готов к работе!")

async def on_shutdown():
    """Действия при остановке бота"""
    logger.info("🛑 Бот останавливается...")
    logger.info("✅ Бот остановлен")

async def main():
    """Основная функция запуска бота"""
    print("=" * 50)
    print("🤖 Sber Support Bot - MVP версия")
    print("=" * 50)
    print("\nДля остановки нажмите Ctrl+C\n")
    
    # Выполняем startup
    await on_startup()
    
    # Запускаем polling
    await dp.start_polling(bot, skip_updates=True)

if __name__ == '__main__':
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        print("\n\n🛑 Бот остановлен пользователем")
        asyncio.run(on_shutdown())