# main.py — Точка входа в Telegram-бота. Инициализирует бота, подключает роутеры и запускает автопостинг

import asyncio
import logging
import os
import logging

os.makedirs("logs", exist_ok=True)

logging.basicConfig(
    filename="logs/app.log",
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
    encoding="utf-8"
)

from aiogram import Bot, Dispatcher
from aiogram.enums import ParseMode
from aiogram.fsm.storage.memory import MemoryStorage

from config import BOT_TOKEN                      # Импорт токена из конфигурации
from handlers import basic                        # Подключение хендлеров (роутеров)
from services import autoposter                   # Модуль автоматической публикации

# Настройка логгера для отладки
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Инициализация Telegram-бота
bot = Bot(token=BOT_TOKEN, parse_mode=ParseMode.HTML)

# Создание диспетчера и FSM-хранилища (в оперативной памяти)
dp = Dispatcher(storage=MemoryStorage())

# Подключение маршрутов (обработчиков команд и сообщений)
dp.include_router(basic.router)

# Главная асинхронная функция запуска
# Стартует диспетчер и автопостер после запуска

def main():
    async def runner():
        await dp.start_polling(bot, on_startup=[lambda _: autoposter.run(bot)]) # Запуск polling-режима и фоновой задачи autoposter

    asyncio.run(runner())

# Точка запуска скрипта
if __name__ == "__main__":
    main()
