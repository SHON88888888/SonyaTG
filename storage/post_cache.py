# post_cache.py — Работа с кешем следующего поста для отложенной публикации

import json
from config import NEXT_POST_FILE  # Путь к кеш-файлу поста из конфига

# Загружает отложенный пост из кеш-файла (если есть)
# Возвращает словарь или None

def load():
    try:
        with open(NEXT_POST_FILE, "r", encoding="utf-8") as f:
            return json.load(f)
    except FileNotFoundError:
        return None

# Сохраняет пост в кеш (будет опубликован позже)
# Если передать None — очищает кеш-файл

def save(data):
    with open(NEXT_POST_FILE, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)
