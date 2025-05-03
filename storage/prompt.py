# prompt.py — Работа с промптом генерации текста постов

from config import POST_PROMPT_FILE  # Путь к файлу с шаблоном запроса для GPT

# Загружает текст промпта из файла
# Используется при генерации нового поста в post_generator.py

def read():
    # Чтение шаблона запроса из файла. Возвращает строку или пустую строку при ошибке
    try:
            with open(POST_PROMPT_FILE, "r", encoding="utf-8") as f:
                    return f.read().strip()
    except FileNotFoundError:
        return ""

# Сохраняет новый текст промпта в файл (при редактировании через бота)

def save(content):
    # Сохраняет шаблон, игнорируя пустой ввод
    if not content.strip():
        return
    with open(POST_PROMPT_FILE, "w", encoding="utf-8") as f:
        f.write(content.strip())
