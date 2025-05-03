# post_generator.py — Обновлённый для нескольких изображений
from datetime import datetime, timezone, timedelta
import logging
from openai import OpenAI
from aiogram import Bot
from aiogram.types import FSInputFile, InputMediaPhoto

from config import MOSCOW_TZ_OFFSET
from storage import content_plan_storage as content_plan
from storage import prompt, post_cache, channel, user
from services.image_generator import generate_image_urls

client = OpenAI()
MSK_TZ = timezone(timedelta(hours=MOSCOW_TZ_OFFSET))
logger = logging.getLogger(__name__)

async def generate_post_text(rubric, topic):
    logger.info(f"Генерация текста поста для рубрики '{rubric}', тема '{topic}'")
    prompt_text = prompt.read().replace("{rubric}", rubric).replace("{topic}", topic)
    response = client.chat.completions.create(
        model="gpt-4o",
        messages=[{"role": "user", "content": prompt_text}],
        temperature=1.0
    )
    post_text = response.choices[0].message.content.strip()
    logger.info("Текст поста успешно сгенерирован")
    return post_text

async def generate_image_prompt(text):
    logger.info("Генерация промпта для изображения")
    prompt_instruction = (
        "Создай короткий промпт на английском языке для нейросети генерации изображений "
        "по следующему описанию поста. Не упоминай текст напрямую. Промпт должен описывать атмосферу, "
        "настроение и визуальные элементы, подходящие под пост. Максимум 40 слов."
    )
    response = client.chat.completions.create(
        model="gpt-4o",
        messages=[
            {"role": "system", "content": prompt_instruction},
            {"role": "user", "content": text[:1000]}
        ],
        temperature=0.8
    )
    image_prompt = response.choices[0].message.content.strip()
    logger.info(f"Промпт для изображения: {image_prompt}")
    return image_prompt

async def prepare_and_preview_post(bot: Bot):
    logger.info("Подготовка следующего поста")
    from storage.content_plan_storage import get_all
    all_posts = get_all()
    now = datetime.now(MSK_TZ)

    future_posts = [post for post in all_posts
                    if datetime.fromisoformat(post["publish"]).replace(tzinfo=MSK_TZ) > now]

    if not future_posts:
        logger.info("Нет постов в будущем для предпросмотра")
        return

    item = min(future_posts, key=lambda p: datetime.fromisoformat(p["publish"]).replace(tzinfo=MSK_TZ))
    logger.info(f"Следующий пост: рубрика '{item['rubric']}', тема '{item['topic']}'")

    user_id = user.load()
    if user_id:
        try:
            channel_id = channel.load()
            publish_time = datetime.fromisoformat(item["publish"]).replace(tzinfo=MSK_TZ).strftime("%H:%M %d.%m.%Y")
            chat = await bot.get_chat(channel_id)
            channel_name = chat.title

            header_text = (
                f"📬 Очередной пост для канала <b>{channel_name}</b>\n"
                f"🕒 Планируемая публикация: <b>{publish_time}</b>\n"
                f"<b>Предпросмотр поста:</b>"
            )

            header_msg = await bot.send_message(user_id, header_text)
            with open("data/preview_header_id.txt", "w") as f:
                f.write(str(header_msg.message_id))

        except Exception as e:
            logger.warning(f"Не удалось отправить заголовок предпросмотра: {e}")

    # Генерация текста и изображений
    text = await generate_post_text(item["rubric"], item["topic"])
    # Получаем из плана число изображений: булево или число
    raw = item.get("generate_image", 0)
    try:
        num_images = int(raw)
    except (ValueError, TypeError):
        num_images = 1 if raw else 0
    image_prompt = await generate_image_prompt(text) if num_images > 0 else None
    image_paths = await generate_image_urls(item["topic"], image_prompt or "", num_images=num_images)
    logger.info(f"Сгенерированы изображения: {image_paths}")

    post_cache.save({
        "rubric": item["rubric"],
        "topic": item["topic"],
        "text": text,
        "image_urls": image_paths,
        "publish": item["publish"]
    })
    logger.info("Пост сохранен в кеш")

    if user_id:
        try:
            body_text = f"<b>{item['rubric']} — {item['topic']}</b>\n\n{text}"
            if len(image_paths) == 1:
                photo = FSInputFile(image_paths[0])
                msg = await bot.send_photo(user_id, photo, caption=body_text[:1000])
            elif len(image_paths) > 1:
                media = []
                for idx, path in enumerate(image_paths):
                    file = FSInputFile(path)
                    if idx == 0:
                        media.append(InputMediaPhoto(media=file, caption=body_text[:1000]))
                    else:
                        media.append(InputMediaPhoto(media=file))
                await bot.send_media_group(user_id, media)
                msg = None
            else:
                msg = await bot.send_message(user_id, body_text)

            if msg:
                with open("data/preview_message_id.txt", "w") as f:
                    f.write(str(msg.message_id))
            logger.info("ID предпросмотра и заголовка сохранены")
        except Exception as e:
            logger.warning(f"Не удалось отправить предпросмотр поста: {e}")