import telebot
from telebot import types
from langchain.schema import HumanMessage, SystemMessage
from langchain_community.chat_models.gigachat import GigaChat

from datetime import datetime
import json
import uuid

# ================== CONFIG ==================

OPERATOR_ID = 0
API_KEY = ""
TOKEN = ""

# ================== ENV ==================

with open(".env") as f:
    for line in f:
        if API_KEY and TOKEN and OPERATOR_ID:
            break
        if line.startswith("API_KEY="):
            API_KEY = line.strip().split("=", 1)[1]
        if line.startswith("TOKEN="):
            TOKEN = line.strip().split("=", 1)[1]
        if line.startswith("OPERATOR_ID="):
            OPERATOR_ID = int(line.strip().split("=", 1)[1])

# ================== DB ==================

from database import dbsearch

# ================== BOT ==================

bot = telebot.TeleBot(TOKEN)

# ================== LLM ==================

giga = GigaChat(
    credentials=API_KEY,
    model="GigaChat",
    verify_ssl_certs=False,
    timeout=10
)

# ================== PROMPTS ==================

CLASSIFIER_PROMPT = SystemMessage(content="""
Ты классификатор.
Ответь ТОЛЬКО одним словом:
BANK — если вопрос относится к банковским продуктам или сервисам
NON_BANK — если не относится
""")

ANSWER_PROMPT = SystemMessage(content="""
Ты помощник банка.
Отвечай ТОЛЬКО используя предоставленный контекст.
НЕ ДОБАВЛЯЙ информацию от себя.
""")

# ================== STORAGE ==================

users_state = {}          # bot | operator
users_role = {}           # user | employee
llm_enabled = {}           # True / False
last_user_question = {}    # user_id: text
last_bot_answer = {}       # user_id: text
tickets = {}
operator_busy = None      # user_id или None
analysis_waiting_file = {}  # user_id: bool

RATINGS_FILE = "ratings.jsonl"

# ================== HELPERS ==================

def classify_question(text: str) -> str:
    try:
        resp = giga.invoke([
            CLASSIFIER_PROMPT,
            HumanMessage(content=text)
        ])
        return resp.content.strip()
    except Exception:
        return "BANK"

def generate_answer(context: str, question: str) -> str:
    try:
        resp = giga.invoke([
            ANSWER_PROMPT,
            HumanMessage(content=f"Контекст:\n{context}\n\nВопрос:\n{question}")
        ])
        return resp.content
    except Exception:
        return "⚠️ Временная ошибка сервиса. Попробуйте позже."

def operator_kb():
    kb = types.InlineKeyboardMarkup()
    kb.add(types.InlineKeyboardButton(
        "Завершить диалог",
        callback_data="end_dialog"
    ))
    return kb


def rating_kb():
    kb = types.InlineKeyboardMarkup(row_width=5)
    buttons = [
        types.InlineKeyboardButton("1", callback_data="rate_1"),
        types.InlineKeyboardButton("2", callback_data="rate_2"),
        types.InlineKeyboardButton("3", callback_data="rate_3"),
        types.InlineKeyboardButton("4", callback_data="rate_4"),
        types.InlineKeyboardButton("5", callback_data="rate_5"),
    ]
    kb.add(*buttons)
    return kb


def save_rating(user_id: int, question: str, answer: str, rating: int):
    record = {
        "timestamp": datetime.now().isoformat(),
        "user_id": user_id,
        "question": question,
        "answer": answer,
        "rating": rating,
    }

    try:
        with open(RATINGS_FILE, "a", encoding="utf-8") as f:
            f.write(json.dumps(record, ensure_ascii=False) + "\n")
    except Exception:
        # если что-то пошло не так при сохранении — не ломаем основной поток
        pass


def analyze_expenses(expenses: list[dict]) -> str:
    """
    Простой анализ трат и «мини-учебник» по финансам.
    Ожидается список операций с полями: date, time, description, amount, category.
    """
    if not expenses:
        return "В файле нет операций — нечего анализировать."

    total_spent = 0
    by_category = {}

    for op in expenses:
        amount = op.get("amount", 0)
        category = op.get("category", "прочее")
        # считаем только расходы (отрицательные суммы)
        if amount < 0:
            value = abs(amount)
            total_spent += value
            by_category[category] = by_category.get(category, 0) + value

    if total_spent == 0:
        return "В файле не найдено расходов (отрицательных сумм) — возможно, это не тот файл."

    # сортируем категории по убыванию трат
    top_cats = sorted(by_category.items(), key=lambda x: x[1], reverse=True)

    lines = []
    lines.append("📊 *Анализ ваших трат*")
    lines.append("")
    lines.append(f"Общая сумма расходов в выборке: *{total_spent:,.0f} ₽*".replace(",", " "))
    lines.append("")
    lines.append("По категориям:")

    for cat, amt in top_cats:
        share = amt / total_spent * 100
        lines.append(f"• *{cat}*: {amt:,.0f} ₽ ({share:.1f}%)".replace(",", " "))

    lines.append("")
    lines.append("💡 *Комментарий по категориям*")

    def comment_for(cat: str, share: float) -> str:
        if cat in ["аренда", "ипотека"]:
            return "Это базовый фиксированный расход. Важно, чтобы жильё не «съедало» больше ~30–35% дохода."
        if cat in ["коммуналка", "счета"]:
            return "Коммунальные платежи — обязательные расходы. Их оптимизация ограничена, но можно следить за тарифами и льготами."
        if cat in ["продукты"]:
            if share > 30:
                return "Расходы на продукты выше типичных 20–30%. Возможно, стоит пересмотреть корзину: меньше импульсивных и премиальных покупок."
            return "Умерный уровень расходов на продукты. Следите за акциями и планируйте закупки заранее."
        if cat in ["развлечения", "личное", "подарки"]:
            if share > 20:
                return "Много трат на развлечения и личные покупки. Это ок, если у вас уже есть подушка безопасности и нет долгов."
            return "Расходы на удовольствие в разумных пределах — это хорошо для баланса, главное не влезать в долги."
        if cat in ["авто"]:
            return "Автомобиль — заметная статья бюджета: топливо, обслуживание, страховки. Заложите эти траты как обязательные и сравните с альтернативами (такси/каршеринг)."
        if cat in ["спорт"]:
            return "Инвестиции в здоровье и спорт — хорошие расходы, если вы реально пользуетесь абонементом 🙂."
        if cat in ["здоровье"]:
            return "Расходы на здоровье часто неожиданные. Подумайте о резерве на медицину и страховании."
        if cat in ["питомец"]:
            return "Питомец — это всегда постоянные расходы. Важно учитывать их при планировании бюджета."
        return "Подумайте, все ли траты в этой категории осознанны и нужны, или часть можно сократить."

    for cat, amt in top_cats:
        share = amt / total_spent * 100
        lines.append(f"- *{cat}*: {comment_for(cat, share)}")

    lines.append("")
    lines.append("📘 *Базовые принципы финансовой грамотности*")
    lines.append("1. Старайтесь откладывать не менее 10–20% дохода на сбережения и подушку безопасности.")
    lines.append("2. Фиксируйте обязательные расходы (аренда, коммуналка, кредиты, проезд) — они не должны «съедать» весь доход.")
    lines.append("3. Импульсивные траты (одежда, гаджеты, развлечения) лучше заранее лимитировать в бюджете.")
    lines.append("4. Крупные покупки (телефон, техника, отпуск) планируйте заранее и копите на них, а не берите в кредит.")
    lines.append("5. Регулярно пересматривайте траты: ищите подписки/услуги, которыми перестали пользоваться.")

    return "\n".join(lines)

def register_kb():
    kb = types.InlineKeyboardMarkup()
    kb.add(
        types.InlineKeyboardButton("🙋 Пользователь", callback_data="reg_user"),
        types.InlineKeyboardButton("🏦 Сотрудник банка", callback_data="reg_employee")
    )
    return kb

def create_ticket(user_id, question):
    ticket_id = str(uuid.uuid4())[:8]
    tickets[user_id] = {
        "ticket_id": ticket_id,
        "user_id": user_id,
        "question": question,
        "created_at": datetime.now().isoformat()
    }
    return ticket_id

def end_dialog(user_id):
    global operator_busy

    if operator_busy == user_id:
        operator_busy = None

    users_state[user_id] = "bot"
    llm_enabled[user_id] = True
    last_user_question.pop(user_id, None)

    bot.send_message(user_id, "✅ Диалог завершен. Вы можете задать новый вопрос.")

# ================== /start ==================

@bot.message_handler(commands=["start"])
def start(msg):
    bot.send_message(
        msg.chat.id,
        "Кто вы?",
        reply_markup=register_kb()
    )

# ================== REGISTRATION ==================

@bot.callback_query_handler(func=lambda c: c.data in ["reg_user", "reg_employee"])
def register(call):
    user_id = call.message.chat.id

    if call.data == "reg_user":
        users_role[user_id] = "user"
        users_state[user_id] = "bot"
        llm_enabled[user_id] = True

        bot.send_message(
            user_id,
            "✅ Вы зарегистрированы как пользователь.\nЗадайте вопрос по банковским продуктам."
        )

    if call.data == "reg_employee":
        users_role[user_id] = "employee"
        users_state[user_id] = "operator"
        llm_enabled[user_id] = False

        bot.send_message(
            user_id,
            "✅ Вы зарегистрированы как сотрудник банка.\nИспользуйте /reply для ответа клиентам и /end <user_id> для завершения диалога."
        )

# ================== OPERATOR REPLY ==================

@bot.message_handler(commands=["reply"])
def operator_reply(msg):
    if msg.chat.id != OPERATOR_ID:
        return

    try:
        _, user_id, text = msg.text.split(maxsplit=2)
    except ValueError:
        bot.send_message(
            OPERATOR_ID,
            "❌ Формат:\n/reply <user_id> <текст>"
        )
        return

    bot.send_message(
        int(user_id),
        f"👨‍💼 Оператор:\n{text}"
    )


@bot.message_handler(commands=["analise"])
def start_analysis(msg):
    user_id = msg.chat.id

    if users_role.get(user_id) == "employee":
        return

    analysis_waiting_file[user_id] = True

    bot.send_message(
        user_id,
        "📂 Отправьте JSON-файл с историей трат *документом*.\n\n"
        "Формат каждой операции:\n"
        "`{\"date\": \"01.10\", \"time\": \"09:00\", \"description\": \"...\", \"amount\": -85000, \"category\": \"аренда\"}`"
    )

# ================== OPERATOR END DIALOG ==================

@bot.message_handler(commands=["end"])
def handle_end(msg):
    user_id = msg.chat.id
    args = msg.text.split()

    if msg.chat.id == OPERATOR_ID and len(args) == 2:
        # оператор завершает диалог пользователя
        target_user = int(args[1])
        if users_state.get(target_user) == "operator":
            end_dialog(target_user)
            bot.send_message(OPERATOR_ID, f"✅ Диалог с пользователем {target_user} завершен.")
        else:
            bot.send_message(OPERATOR_ID, f"⚠️ Пользователь {target_user} не находится в диалоге с оператором.")
        return

    # обычный пользователь завершает диалог
    end_dialog(user_id)

@bot.callback_query_handler(func=lambda c: c.data == "end_dialog")
def handle_end_button(call):
    # кнопка только для оператора
    if call.message.chat.id == OPERATOR_ID:
        target_user_id = operator_busy
        if target_user_id:
            end_dialog(target_user_id)
            bot.send_message(OPERATOR_ID, f"✅ Диалог с пользователем {target_user_id} завершен.")
        else:
            bot.send_message(OPERATOR_ID, "⚠️ Нет активного диалога для завершения.")

# ================== CALL OPERATOR ==================

@bot.callback_query_handler(func=lambda c: c.data == "call_operator")
def call_operator(call):
    global operator_busy

    user_id = call.message.chat.id

    if operator_busy is not None:
        bot.send_message(
            user_id,
            "⏳ Оператор сейчас занят другим клиентом. Пожалуйста, подождите."
        )
        return

    operator_busy = user_id
    users_state[user_id] = "operator"
    llm_enabled[user_id] = False

    question = last_user_question.get(user_id, "Вопрос не найден")
    ticket_id = create_ticket(user_id, question)

    bot.send_message(
        OPERATOR_ID,
        f"📩 Тикет #{ticket_id}\n"
        f"Пользователь: {user_id}\n"
        f"Вопрос: {question}"
    )

    bot.send_message(
        user_id,
        "👨‍💼 Вы подключены к живому оператору."
    )


@bot.callback_query_handler(func=lambda c: c.data.startswith("rate_"))
def rate_answer(call):
    user_id = call.message.chat.id

    try:
        rating = int(call.data.split("_", 1)[1])
    except (ValueError, IndexError):
        return

    if rating < 1 or rating > 5:
        return

    question = last_user_question.get(user_id, "")
    # текст сообщения, к которому прикреплены кнопки — это ответ бота
    answer = call.message.text or last_bot_answer.get(user_id, "")

    save_rating(user_id, question, answer, rating)

    # убираем клавиатуру с оценками
    try:
        bot.edit_message_reply_markup(
            chat_id=call.message.chat.id,
            message_id=call.message.message_id,
            reply_markup=None
        )
    except Exception:
        pass

    bot.answer_callback_query(
        callback_query_id=call.id,
        text=f"Спасибо за вашу оценку: {rating}/5"
    )

# ================== USER MESSAGE ==================

@bot.message_handler(content_types=["text"])
def handle_user(msg):
    user_id = msg.chat.id
    text = msg.text

    if users_role.get(user_id) == "employee":
        return

    last_user_question[user_id] = text

    if users_state.get(user_id) == "operator":
        bot.send_message(OPERATOR_ID, f"👤 {user_id}: {text}")
        return

    if not llm_enabled.get(user_id, True):
        return

    category = classify_question(text)

    if category == "NON_BANK":
        bot.send_message(
            user_id,
            "Я могу помочь только с вопросами по банковским продуктам и сервисам."
        )
        return

    db_result = dbsearch(text)

    if db_result == "в базе нет подходящего ответа":
        bot.send_message(
            user_id,
            "К сожалению, по вашему вопросу нет информации. Я могу подключить оператора.",
            reply_markup=types.InlineKeyboardMarkup().add(
                types.InlineKeyboardButton("Связаться с оператором", callback_data="call_operator")
            )
        )
        return

    answer = generate_answer(db_result, text)
    last_bot_answer[user_id] = answer
    bot.send_message(
        user_id,
        answer,
        reply_markup=rating_kb()
    )

# ================== НЕ ТЕКСТОВЫЕ СООБЩЕНИЯ ==================

MEDIA_TYPES = ["photo", "video", "audio", "document", "sticker", "voice",
               "video_note", "animation", "contact", "location", "venue"]

@bot.message_handler(content_types=MEDIA_TYPES)
def handle_non_text(msg):
    user_id = msg.chat.id
    # сотрудникам ничего не отвечаем на медиа
    if users_role.get(user_id) == "employee":
        return

    # если пользователь прислал документ с тратами для анализа
    if msg.content_type == "document" and analysis_waiting_file.get(user_id):
        doc = msg.document
        file_name = (doc.file_name or "").lower()
        if not file_name.endswith(".json"):
            bot.send_message(
                user_id,
                "⚠️ Пожалуйста, пришлите файл в формате JSON (расширение .json)."
            )
            return

        try:
            file_info = bot.get_file(doc.file_id)
            downloaded = bot.download_file(file_info.file_path)
            data = json.loads(downloaded.decode("utf-8"))
        except Exception:
            bot.send_message(
                user_id,
                "❌ Не удалось прочитать файл как JSON. Убедитесь, что формат корректный."
            )
            return

        if not isinstance(data, list):
            bot.send_message(
                user_id,
                "❌ Ожидался список операций (JSON-массив). Проверьте формат файла."
            )
            return

        analysis_waiting_file[user_id] = False

        report = analyze_expenses(data)
        bot.send_message(user_id, report, parse_mode="Markdown")
        return

    # по умолчанию медиа не обрабатываем
    bot.send_message(user_id, "⚠️ Я работаю только с текстовыми сообщениями")

# ================== RUN ==================

if __name__ == "__main__":
    print("Бот запущен")
    bot.polling(none_stop=True)
