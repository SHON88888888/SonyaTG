import asyncio
import os
import subprocess
from datetime import datetime
from zoneinfo import ZoneInfo
from pathlib import Path
from aiogram import Bot
from aiogram.types import FSInputFile, InputMediaPhoto
import logging

from storage import content_plan_storage as content_plan, user, channel
from services.post_generator import prepare_and_preview_post
from utils.file import load_json, save_json, delete_file
from services.video_tools import create_video, VideoSettings

logger = logging.getLogger(__name__)

# Московская временная зона
LOCAL_TZ = ZoneInfo("Europe/Moscow")
CONTENT_PLAN_PATH = "data/content_plan.json"
NEXT_POST_PATH = "data/next_post.json"
PROGRESS_TEMPLATE = "⏳ {}\n\n{} {}%"
CAPTION_LIMIT = 900

async def send_progress_message(bot: Bot, text: str) -> int:
    user_id = user.load()
    try:
        msg = await bot.send_message(
            user_id,
            PROGRESS_TEMPLATE.format(text, "▱" * 10, 0),
            parse_mode='HTML'
        )
        return msg.message_id
    except Exception as e:
        logger.error(f"send_progress_message error: {e}")
        return None

async def delete_progress_message(bot: Bot, message_id: int):
    if message_id:
        try:
            await bot.delete_message(chat_id=user.load(), message_id=message_id)
        except Exception as e:
            logger.warning(f"delete_progress_message error: {e}")

async def publish_post(bot: Bot, next_post: dict) -> bool:
    try:
        chat_id = channel.load()
        text = next_post.get("text", "") or ""
        # Определяем, использовать ли подпись
        if len(text) <= CAPTION_LIMIT:
            caption = text
            send_text_after = False
        else:
            caption = None
            send_text_after = True

        image_paths = next_post.get("image_urls", [])
        create_video_flag = next_post.get("create_video", False)
        video_settings = VideoSettings.from_dict(next_post.get("video_settings", {}))
        video_path = os.path.join("data", "generated_video.mp4")

        # Видео
        if create_video_flag and len(image_paths) >= 2:
            if subprocess.run(["which", "ffmpeg"], capture_output=True).stdout:
                success = create_video(
                    [Path(p) for p in image_paths], video_path, video_settings
                )
                if success:
                    await bot.send_video(chat_id=chat_id, video=FSInputFile(video_path), caption=caption)
                    delete_file(video_path)
                    if send_text_after:
                        await bot.send_message(chat_id=chat_id, text=text)
                    return True
        # Фото или альбом
        if len(image_paths) == 1:
            await bot.send_photo(chat_id=chat_id, photo=FSInputFile(image_paths[0]), caption=caption)
        elif len(image_paths) > 1:
            media = [InputMediaPhoto(media=FSInputFile(p), caption=caption if i == 0 else None)
                     for i, p in enumerate(image_paths)]
            await bot.send_media_group(chat_id=chat_id, media=media)
        else:
            # Текст без медиа
            await bot.send_message(chat_id=chat_id, text=text)
            return True

        if send_text_after:
            await bot.send_message(chat_id=chat_id, text=text)
        return True
    except Exception as e:
        logger.error(f"publish_post error: {e}")
        return False

async def delete_preview(bot: Bot):
    for fname in ["data/preview_message_id.txt", "data/preview_header_id.txt"]:
        if os.path.exists(fname):
            try:
                with open(fname) as f:
                    msg_id = int(f.read().strip())
                await bot.delete_message(chat_id=user.load(), message_id=msg_id)
                os.remove(fname)
            except Exception as e:
                logger.warning(f"delete_preview error for {fname}: {e}")

async def generate_and_preview(bot: Bot):
    """Отправляет сообщение с заголовком, прогресс-баром и запускает генерацию предпросмотра"""
    chat = await bot.get_chat(channel.load())
    # Определяем ближайший пост из контент-плана
    plan = load_json(CONTENT_PLAN_PATH)
    candidates = [p for p in plan if not p.get("status")]
    next_item = min(candidates, key=lambda p: p.get("publish"))
    publish_dt = datetime.fromisoformat(next_item["publish"]).replace(tzinfo=LOCAL_TZ)
    publish_str = publish_dt.strftime("%H:%M %d.%m.%Y")

    # Формируем сообщение
    header = (
        f"📬 Очередной пост для канала <b>{chat.title}</b>\n"
        f"🕒 Планируемая публикация: {publish_str}\n"
        f"Предпросмотр поста:"
    )
    initial_bar = PROGRESS_TEMPLATE.format("", "▱" * 10, 0)

    progress_msg_id = await bot.send_message(
        user.load(),
        f"{header}\n{initial_bar}",
        parse_mode='HTML'
    )

    await prepare_and_preview_post(bot, progress_msg_id)
    await delete_progress_message(bot, progress_msg_id)

async def run(bot: Bot):
    logger.info("🚀 Autoposter started")

    while True:
        now = datetime.now(LOCAL_TZ)
        logger.debug(f"Autoposter tick: now={now.isoformat()}")

        if not os.path.exists(CONTENT_PLAN_PATH):
            await bot.send_message(user.load(), "❌ Нет постов для публикации. Обновите Контент-план.")
            await asyncio.sleep(60)
            continue

        plan = load_json(CONTENT_PLAN_PATH)
        candidates = [p for p in plan if not p.get("status")]
        if not candidates:
            await bot.send_message(user.load(), "❌ Нет постов для публикации. Обновите Контент-план.")
            await asyncio.sleep(300)
            continue

        if os.path.exists(NEXT_POST_PATH):
            next_post = load_json(NEXT_POST_PATH)
            publish_time = datetime.fromisoformat(next_post["publish"]).replace(tzinfo=LOCAL_TZ)
            if publish_time <= now:
                if await publish_post(bot, next_post):
                    await delete_preview(bot)
                    delete_file(NEXT_POST_PATH)
                    await generate_and_preview(bot)
                else:
                    await asyncio.sleep(10)
            else:
                delay = (publish_time - now).total_seconds()
                await asyncio.sleep(min(delay, 300))
        else:
            await generate_and_preview(bot)
            await asyncio.sleep(10)
