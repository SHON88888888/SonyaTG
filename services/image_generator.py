# image_generator.py — генерация изображений через Leonardo.Ai с расширенными настройками
import logging
import httpx
import os
import asyncio
import uuid
from typing import List, Optional
from config import LEONARDO_API_KEY

# Значения по умолчанию
DEFAULT_NEGATIVE_PROMPT = (
    "blurry, grainy, lowres, bad anatomy, distorted, text, watermark, extra limbs, cloned face, artifacts"
)
DEFAULT_MODEL_ID = "leonardo-creative-v2"
DEFAULT_STYLE_PRESET = "LEONARDO"
DEFAULT_NUM_STEPS = 35

async def generate_image_urls(
    topic: str,
    visual_prompt: str,
    num_images: int = 1,
    width: int = 1080,
    height: int = 1080,
    guidance_scale: float = 7.0,
    num_steps: int = DEFAULT_NUM_STEPS,
    model_id: str = DEFAULT_MODEL_ID,
    negative_prompt: str = DEFAULT_NEGATIVE_PROMPT,
    style_preset: str = DEFAULT_STYLE_PRESET
) -> List[str]:
    """
    Генерирует изображения через Leonardo.Ai по заданному промпту и настройкам.

    :param topic: Тема поста (для логирования).
    :param visual_prompt: Основной текст запроса (image prompt).
    :param num_images: Сколько изображений сгенерировать.
    :param width: Ширина картинки.
    :param height: Высота картинки.
    :param guidance_scale: Степень следования промпту (0–20).
    :param num_steps: Кол-во шагов инференса (качество/скорость).
    :param model_id: Идентификатор модели Leonardo.
    :param negative_prompt: Что исключать из генерации.
    :param style_preset: Визуальный стиль.
    :return: Список путей к сохранённым изображениям.
    """
    if not visual_prompt.strip():
        logging.warning("[ImageGen] Промпт пуст, изображения не будут сгенерированы")
        return []

    logging.info(f"[ImageGen] Тема: {topic}, промпт: {visual_prompt.strip()} × {num_images}")

    headers = {
        "Authorization": f"Bearer {LEONARDO_API_KEY}",
        "Content-Type": "application/json"
    }

    saved_paths: List[str] = []

    async with httpx.AsyncClient(timeout=60) as client:
        for i in range(num_images):
            payload = {
                "prompt": visual_prompt.strip(),
                "negative_prompt": negative_prompt,
                "width": width,
                "height": height,
                "num_images": 1,
                "guidance_scale": guidance_scale,
                "num_inference_steps": num_steps,
                "model_id": model_id,
                "preset_style": style_preset,
                "public": False
            }

            try:
                # Запускаем генерацию
                response = await client.post(
                    "https://cloud.leonardo.ai/api/rest/v1/generations",
                    headers=headers,
                    json=payload
                )
                response.raise_for_status()

                result = response.json()
                generation_id = result.get("sdGenerationJob", {}).get("generationId")
                if not generation_id:
                    logging.error("[Leonardo] Не удалось получить ID генерации")
                    continue

                # Ждём завершения генерации
                for _ in range(60):
                    await asyncio.sleep(5)
                    poll = await client.get(
                        f"https://cloud.leonardo.ai/api/rest/v1/generations/{generation_id}",
                        headers=headers
                    )
                    poll.raise_for_status()
                    poll_data = poll.json()
                    images = poll_data.get("generations_by_pk", {}).get("generated_images", [])
                    if images:
                        img_url = images[0].get("url")
                        if not img_url:
                            break
                        img_data = await client.get(img_url)
                        img_data.raise_for_status()
                        filename = f"img_{uuid.uuid4().hex[:8]}.jpg"
                        with open(filename, "wb") as f:
                            f.write(img_data.content)
                        saved_paths.append(filename)
                        break
                else:
                    logging.error("[Leonardo] Таймаут генерации изображения")

            except Exception as e:
                logging.error(f"[ImageGen] Ошибка при генерации изображения: {e}", exc_info=True)

    return saved_paths
