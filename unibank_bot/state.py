from __future__ import annotations

from datetime import datetime
import json
from typing import Dict, Any

# ================== РАЗДЕЛ ПАМЯТИ БОТА ==================

users_state: Dict[int, str] = {}          # bot | operator
users_role: Dict[int, str] = {}           # user | employee
llm_enabled: Dict[int, bool] = {}         # True / False
last_user_question: Dict[int, str] = {}   # user_id: text
last_bot_answer: Dict[int, str] = {}      # user_id: text
tickets: Dict[int, Dict[str, Any]] = {}
operator_busy: int | None = None          # user_id или None
analysis_waiting_file: Dict[int, bool] = {}  # user_id: bool


RATINGS_FILE = "ratings.jsonl"


def save_rating(user_id: int, question: str, answer: str, rating: int) -> None:
    """
    Сохранение оценки ответа бота в JSONL-файл.
    """
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


