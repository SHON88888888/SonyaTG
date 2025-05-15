# config.py — Конфигурация и пути к данным проекта

import os
from dotenv import load_dotenv

load_dotenv()

BOT_TOKEN = os.getenv("BOT_TOKEN")
OPENAI_API_KEY = os.getenv("OPENAI_API_KEY")

# Настройки временной зоны
MOSCOW_TZ_OFFSET = 3

# Пути к файлам (обновлены с учётом папок data/ и storage/)
CONTENT_PLAN_FILE = os.getenv("CONTENT_PLAN_FILE", "data/content_plan.json")
POST_PROMPT_FILE = os.getenv("POST_PROMPT_FILE", "data/post_prompt.txt")
NEXT_POST_FILE = os.getenv("NEXT_POST_FILE", "data/next_post.json")
CHANNELS_FILE = os.getenv("CHANNELS_FILE", "storage/channel.json")
USER_FILE = os.getenv("USER_FILE", "storage/user.json")
KANDINSKY_API_KEY = os.getenv("KANDINSKY_API_KEY")
KANDINSKY_SECRET_KEY = os.getenv("KANDINSKY_SECRET_KEY")
LEONARDO_API_KEY = os.getenv("LEONARDO_API_KEY")
