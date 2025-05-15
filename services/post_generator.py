# post_generator.py — Обновлённый с прогресс-баром и улучшенной обработкой видео
import logging
import subprocess
import asyncio
from datetime import datetime, timezone, timedelta
from pathlib import Path

from aiogram import Bot
from aiogram.types import FSInputFile, InputMediaPhoto
from openai import OpenAI

from config import MOSCOW_TZ_OFFSET
from services.image_generator import generate_image_urls
from services.video_tools import create_video, VideoSettings
from storage import prompt, user, channel
from utils.file import load_json, save_json

client = OpenAI()
MSK_TZ = timezone(timedelta(hours=MOSCOW_TZ_OFFSET))
logger = logging.getLogger(__name__)

CONTENT_PLAN_PATH = "data/content_plan.json"
NEXT_POST_PATH = "data/next_post.json"
PROGRESS_TEMPLATE = "⏳ {}\n\n{} {}%"

async def update_progress(bot: Bot, progress_msg_id: int, progress: int, text: str):
    """Обновляет сообщение с прогрессом"""
    try:
        filled = min(progress // 10, 10)
        progress_bar = "▰" * filled + "▱" * (10 - filled)
        await bot.edit_message_text(
            chat_id=user.load(),
            message_id=progress_msg_id,
            text=PROGRESS_TEMPLATE.format(text, progress_bar, min(progress, 100))
        )
    except Exception as e:
        logger.warning(f"Ошибка обновления прогресса: {e}")

async def generate_post_text(rubric: str, topic: str, bot: Bot = None, progress_msg_id: int = None) -> str:
    """Генерирует текст поста с помощью GPT-4"""
    if bot and progress_msg_id:
        await update_progress(bot, progress_msg_id, 20, "Генерация текста...")
    
    logger.info(f"Генерация текста для рубрики '{rubric}', тема '{topic}'")
    try:
        prompt_text = prompt.read().replace("{rubric}", rubric).replace("{topic}", topic)
        response = client.chat.completions.create(
            model="gpt-4o",
            messages=[{"role": "user", "content": prompt_text}],
            temperature=1.0
        )
        post_text = response.choices[0].message.content.strip()
        logger.info("Текст поста успешно сгенерирован")
        return post_text
    except Exception as e:
        logger.error(f"Ошибка генерации текста: {e}")
        raise


async def create_video_from_images(
    image_paths: list, 
    settings: dict,
    bot: Bot = None,
    progress_msg_id: int = None
) -> tuple:
    """Создает видео из изображений с прогрессом"""
    video_path = Path("data/preview_video.mp4")
    video_created = False
    
    if bot and progress_msg_id:
        await update_progress(bot, progress_msg_id, 60, "Создание видео...")
    
    try:
        if not subprocess.run(["which", "ffmpeg"], capture_output=True).stdout:
            logger.error("FFmpeg не установлен!")
            return video_path, False

        video_settings = VideoSettings(
            frame_duration=settings.get("display_time", 3.0),
            transition_duration=settings.get("transition_time", 1.0),
            transition_type=settings.get("transition_type", "fade"),
            aspect_ratio=settings.get("aspect_ratio", "square"),
            transition_params=settings.get("transition_params", {})
        )

        video_created = create_video(
            [Path(p) for p in image_paths],
            video_path,
            video_settings
        )

        if not video_created:
            logger.error("Не удалось создать видео. Проверьте логи FFmpeg.")
        
        return video_path, video_created

    except Exception as e:
        logger.error(f"Ошибка создания видео: {e}")
        return video_path, False

async def send_preview(
    bot: Bot,
    rubric: str,
    topic: str,
    text: str,
    image_paths: list,
    video_path: Path,
    video_created: bool,
    publish_dt: datetime,
    progress_msg_id: int = None
):
    """Отправляет предпросмотр поста пользователю"""
    if bot and progress_msg_id:
        await update_progress(bot, progress_msg_id, 80, "Отправка предпросмотра...")
    
    try:
        # Отправляем заголовок предпросмотра
        channel_id = channel.load()
        chat = await bot.get_chat(channel_id)
        publish_time_str = publish_dt.strftime("%H:%M %d.%m.%Y")
        header_text = (
            f"📬 Очередной пост для канала <b>{chat.title}</b>\n"
            f"🕒 Планируемая публикация: <b>{publish_time_str}</b>\n"
            f"<b>Предпросмотр поста:</b>"
        )
        header_msg = await bot.send_message(user.load(), header_text)
        with open("data/preview_header_id.txt", "w") as f:
            f.write(str(header_msg.message_id))

        # Формируем текст поста
        body_text = f"<b>{rubric} — {topic}</b>\n\n{text}"

        # Отправляем контент
        if video_created and video_path.exists():
            msg = await bot.send_video(
                chat_id=user.load(),
                video=FSInputFile(video_path),
                caption=body_text[:1024]
            )
            logger.info("Предпросмотр с видео отправлен")
        elif len(image_paths) == 1:
            msg = await bot.send_photo(
                chat_id=user.load(),
                photo=FSInputFile(image_paths[0]),
                caption=body_text[:1024]
            )
            logger.info("Предпросмотр с изображением отправлен")
        elif len(image_paths) > 1:
            media = [
                InputMediaPhoto(media=FSInputFile(p), caption=body_text[:1024] if i == 0 else None)
                for i, p in enumerate(image_paths)
            ]
            await bot.send_media_group(user.load(), media)
            logger.info("Предпросмотр альбома отправлен")
            return  # Для медиагруппы не сохраняем ID
        else:
            msg = await bot.send_message(user.load(), body_text)
            logger.info("Текстовый предпросмотр отправлен")

        # Сохраняем ID сообщения для удаления
        with open("data/preview_message_id.txt", "w") as f:
            f.write(str(msg.message_id))

    except Exception as e:
        logger.error(f"Ошибка отправки предпросмотра: {e}")
        raise
    finally:
        if video_path.exists():
            try:
                video_path.unlink()
            except Exception as e:
                logger.warning(f"Ошибка удаления временного видео: {e}")

async def prepare_and_preview_post(bot: Bot, progress_msg_id: int = None):
    """Основная функция подготовки поста"""
    try:
        if progress_msg_id:
            await update_progress(bot, progress_msg_id, 10, "Загрузка контент-плана...")

        plan = load_json(CONTENT_PLAN_PATH)
        now = datetime.now(MSK_TZ)

        # Выбираем ближайший пост без статуса
        candidates = [
            post for post in plan
            if post.get("status", "") == ""
            and datetime.fromisoformat(post["publish"]).replace(tzinfo=MSK_TZ) > now
        ]
        
        if not candidates:
            logger.info("Нет постов для генерации")
            if progress_msg_id:
                await update_progress(bot, progress_msg_id, 100, "Нет новых постов в плане")
            return

        post = min(candidates, key=lambda p: datetime.fromisoformat(p["publish"]).replace(tzinfo=MSK_TZ))
        publish_dt = datetime.fromisoformat(post["publish"]).replace(tzinfo=MSK_TZ)
        rubric = post["rubric"]
        topic = post["topic"]

        # Генерация текста
        text = await generate_post_text(rubric, topic, bot, progress_msg_id)

        # Генерация изображений
        image_count = post.get("generate_image", {}).get("count", 0) if post.get("generate_image", {}).get("enabled") else 0
        image_paths = []
        if image_count > 0:
            if progress_msg_id:
                await update_progress(bot, progress_msg_id, 40, "Генерация изображений...")
            visual_prompt = post.get("visual_prompt", "")
            image_paths = await generate_image_urls(topic, visual_prompt, num_images=image_count)

        # Создание видео
        video_path = Path("data/preview_video.mp4")
        video_created = False
        
        if post.get("slider", {}).get("enabled") and len(image_paths) >= 2:
            video_path, video_created = await create_video_from_images(
                image_paths,
                post["slider"],
                bot,
                progress_msg_id
            )

        # Сохранение поста
        next_post = {
            "rubric": rubric,
            "topic": topic,
            "text": text,
            "image_urls": image_paths,
            "publish": post["publish"],
            "create_video": video_created,
            "video_settings": {
                "frame_duration": post["slider"].get("display_time", 3.0),
                "transition_duration": post["slider"].get("transition_time", 1.0),
                "transition_type": post["slider"].get("transition_type", "fade"),
                "aspect_ratio": post["slider"].get("aspect_ratio", "square"),
                "transition_params": post["slider"].get("transition_params", {})
            } if video_created else {}
        }
        save_json(NEXT_POST_PATH, next_post)

        # Обновление статуса
        for p in plan:
            if (p["rubric"] == rubric and 
                p["topic"] == topic and 
                p["publish"] == post["publish"]):
                p["status"] = "prepared"
        save_json(CONTENT_PLAN_PATH, plan)

        # Отправка предпросмотра
        await send_preview(
            bot,
            rubric,
            topic,
            text,
            image_paths,
            video_path,
            video_created,
            publish_dt,
            progress_msg_id
        )

        if progress_msg_id:
            await update_progress(bot, progress_msg_id, 100, "Пост готов к публикации!")

    except Exception as e:
        logger.error(f"Критическая ошибка: {e}", exc_info=True)
        if progress_msg_id:
            await update_progress(
                bot,
                progress_msg_id,
                100,
                f"Ошибка: {str(e)[:100]}"
            )
        raise