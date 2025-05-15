# channel.py — Хранение и загрузка ID подключённого Telegram-канала

import json
from config import CHANNELS_FILE  # Путь к JSON-файлу с ID канала

# Сохраняет ID канала в JSON-файл
# Используется после пересланного сообщения из канала при /start

def save(channel_id):
    with open(CHANNELS_FILE, "w", encoding="utf-8") as f:
        json.dump({"id": channel_id}, f)

# Загружает ID подключённого канала
# Возвращает None, если файл не найден или структура некорректна

def load():
    try:
        with open(CHANNELS_FILE, "r", encoding="utf-8") as f:
            return json.load(f)["id"]
    except (FileNotFoundError, KeyError, json.JSONDecodeError):
        return None
