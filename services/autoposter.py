# file: services/autoposter.py | updated: 2025-05-03 12:30 (UTC+3)

import uuid
import logging
import asyncio
from pathlib import Path
from aiogram import Bot
from aiogram.types import FSInputFile, InputMediaPhoto

from storage.content_plan_storage import get_due_post
from services.video_creator import create_video_with_ffmpeg

logger = logging.getLogger(__name__)

def cleanup_post_files(post_id: str):
    upload_dir = Path("uploads") / post_id
    output_file = Path("output") / f"{post_id}_video.mp4"

    if upload_dir.exists():
        for f in upload_dir.glob("*"):
            f.unlink()
        upload_dir.rmdir()
        logger.info(f"🧹 Удалены временные изображения из {upload_dir}")

    if output_file.exists():
        output_file.unlink()
        logger.info(f"🧹 Удалён ролик {output_file}")


async def autopost(bot: Bot, post: dict):
    post_id = post.get("id") or str(uuid.uuid4())
    chat_id = post.get("channel_id")
    text = post.get("text", "")

    upload_dir = Path("uploads") / post_id
    output_dir = Path("output")
    output_dir.mkdir(parents=True, exist_ok=True)

    images = sorted(upload_dir.glob("*.jpg")) + sorted(upload_dir.glob("*.png"))
    if not images and not text:
        logger.warning(f"⚠️ Пост {post_id} пуст: нет изображений и текста.")
        return

    slider = post.get("slider", {})
    make_video = slider.get("enabled", False)
    display_time = float(slider.get("display_time", 2.0))
    transition_time = float(slider.get("transition_time", 1.0))
    audio_enabled = post.get("audio", False)

    if make_video and images:
        try:
            logger.info(f"🎬 Генерация видео для поста {post_id}")
            video_path = create_video_with_ffmpeg(
                post_id=post_id,
                image_paths=images,
                frame_duration=display_time,
                transition_duration=transition_time,
                audio_enabled=audio_enabled
            )
            await bot.send_video(
                chat_id=chat_id,
                video=FSInputFile(video_path),
                caption=text
            )
            logger.info(f"✅ Видео отправлено: {video_path}")
            cleanup_post_files(post_id)
            return
        except Exception as e:
            logger.exception(f"❌ Ошибка при генерации видео: {e}")

    if images:
        media = [InputMediaPhoto(media=FSInputFile(img)) for img in images]
        await bot.send_media_group(chat_id=chat_id, media=media)

        if text:
            await bot.send_message(chat_id=chat_id, text=text)

        cleanup_post_files(post_id)

    elif text:
        await bot.send_message(chat_id=chat_id, text=text)
        logger.info(f"📝 Отправлено текстовое сообщение для поста {post_id}")


# 🔄 Фоновая проверка контент-плана
async def run(bot: Bot):
    while True:
        post = get_due_post()
        if post:
            await autopost(bot, post)
        await asyncio.sleep(20)
