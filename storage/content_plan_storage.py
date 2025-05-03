# content_plan_storage.py — Работа с JSON-файлом контент-плана публикаций

import json
from config import CONTENT_PLAN_FILE  # Импорт пути к файлу контент-плана из конфигурации

# Загружает весь контент-план из JSON-файла
# Возвращает список словарей с постами

def load():
    with open(CONTENT_PLAN_FILE, "r", encoding="utf-8") as f:
        return json.load(f)

# Сохраняет переданный контент-план (список постов) в файл
# Используется после изменений в структуре

def save(plan):
    with open(CONTENT_PLAN_FILE, "w", encoding="utf-8") as f:
        json.dump(plan, f, ensure_ascii=False, indent=2)

# Возвращает первый пост, который ещё не был опубликован (status != 'published')
# Используется генератором постов для выбора следующей публикации

def get_next():
    plan = load()
    for item in plan:
        if item.get("status") != "published":
            return item
    return None

# Отмечает пост с заданной рубрикой и темой как "опубликованный"
# После публикации этот метод вызывается, чтобы не публиковать повторно

def mark_published(rubric, topic):
    plan = load()
    for post in plan:
        if post["rubric"] == rubric and post["topic"] == topic:
            post["status"] = "published"
            break
    save(plan)

# Возвращает весь список постов из контент-плана (всегда актуальный)

def get_all():
    return load()
