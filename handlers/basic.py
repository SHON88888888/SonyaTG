# basic.py — Основные хендлеры Telegram-бота (обработка /start, подключение канала, предпросмотр поста)

from aiogram import Router, F
from aiogram.types import Message
from aiogram.filters import CommandStart, Command
from aiogram.fsm.context import FSMContext
from datetime import datetime, timezone, timedelta
import asyncio

from config import MOSCOW_TZ_OFFSET
from storage import channel, user, prompt
from storage import content_plan_storage as content_plan
from storage import post_cache
from services.post_generator import prepare_and_preview_post  # Передаётся bot как аргумент
from services.autoposter import run as autoposter
from storage.states import ChannelState

MSK_TZ = timezone(timedelta(hours=MOSCOW_TZ_OFFSET))

# Создание роутера для регистрации хендлеров
router = Router()

# Обработчик команды /start
@router.message(CommandStart())
async def start(message: Message, state: FSMContext):
    print("[DEBUG] Запущен хендлер /start")
    try:
        channel_id = channel.load()
        print(f"[DEBUG] channel_id = {channel_id}")
        if not channel_id:
            raise ValueError("Канал не подключен")

        user.save(message.from_user.id)
        print(f"[DEBUG] перед get_chat({channel_id})")
        chat = await message.bot.get_chat(channel_id)
        print(f"[DEBUG] chat.title = {chat.title}")

        now = datetime.now(MSK_TZ).strftime("%d.%m.%Y %H:%M")
        await message.answer(f"✅ Активный канал — <b>{chat.title}</b>\n📅 Дата подключения: <b>{now}</b>.")

        plan = content_plan.load()
        times = [datetime.fromisoformat(p["publish"]).replace(tzinfo=MSK_TZ) for p in plan if p.get("status") != "published"]
        if not times:
            await message.answer("📋 Контент-план не содержит запланированных постов.")
            return

        start_date = times[0].strftime("%H:%M %d.%m.%Y")
        end_date = times[-1].strftime("%H:%M %d.%m.%Y")

        await message.answer(f"📋 Активный контен-план с <b>{start_date}</b> по <b>{end_date}</b>.")

        await prepare_and_preview_post(message.bot)
        asyncio.create_task(autoposter(message.bot))

    except Exception as e:
        print(f"[Ошибка /start]: {e}")
        await message.answer("👋 Добавьте бота в администраторы канала и перешлите сюда любое сообщение из канала для активации.")
        await state.set_state(ChannelState.waiting_for_forward)

# Обработчик пересланного сообщения из канала
@router.message(ChannelState.waiting_for_forward, F.forward_from_chat)
async def process_forwarded_message(message: Message, state: FSMContext):
    if not message.forward_from_chat or message.forward_from_chat.type != "channel":
        await message.answer("⛔ Пожалуйста, перешлите сообщение из канала.")
        return

    channel.save(message.forward_from_chat.id)
    user.save(message.from_user.id)

    chat = await message.bot.get_chat(message.forward_from_chat.id)
    now = datetime.now(MSK_TZ).strftime("%d.%m.%Y %H:%M")
    await message.answer(f"✅ Активный канал — <b>{chat.title}</b>\n📅 Дата подключения: <b>{now}</b>.")

    plan = content_plan.load()
    if plan:
        times = [datetime.fromisoformat(p["publish"]).replace(tzinfo=MSK_TZ) for p in plan if p.get("status") != "published"]
        if times:
            start_date = times[0].strftime("%H:%M %d.%m.%Y")
            end_date = times[-1].strftime("%H:%M %d.%m.%Y")
            await message.answer(f"📋 В соответствии с контент-планом публикации планируются с <b>{start_date}</b> по <b>{end_date}</b>.")

    await prepare_and_preview_post(message.bot)
    asyncio.create_task(autoposter(message.bot))

    await state.clear()
