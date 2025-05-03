# user.py — Хранение и загрузка ID администратора/пользователя, работающего с ботом

import json
import os

# Защита: пусть файл всегда будет внутри storage, даже при запуске скрипта напрямую
BASE_DIR = os.path.dirname(__file__)
USER_FILE = os.path.join(BASE_DIR, "user.json")

# Сохраняет ID пользователя в JSON-файл
# Используется при /start или после пересылки сообщения из канала
def save(user_id):
    with open(USER_FILE, "w", encoding="utf-8") as f:
        json.dump({"id": user_id}, f)

# Загружает ID пользователя (кто управляет ботом)
# Возвращает None, если файл отсутствует или структура повреждена
def load():
    try:
        with open(USER_FILE, "r", encoding="utf-8") as f:
            return json.load(f)["id"]
    except (FileNotFoundError, KeyError, json.JSONDecodeError):
        return None

# Запрещаем запуск напрямую
if __name__ == "__main__":
    raise RuntimeError("Этот модуль нельзя запускать напрямую. Используйте только импорт.")
