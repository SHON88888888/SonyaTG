# image_generator
# -*- coding: utf-8 -*-
"""
Модуль генерации изображений через Leonardo.Ai
Теперь поддерживается запрос нескольких изображений (num_images).
"""
import logging
import httpx
import os
import asyncio
from typing import List, Optional
from config import LEONARDO_API_KEY


async def generate_image_urls(
    topic: str,
    context: str,
    num_images: int = 1,
    width: int = 1024,
    height: int = 1024,
    guidance_scale: float = 7.0,
    num_steps: int = 30,
) -> List[str]:
    """
    Генерирует одну или несколько изображений через Leonardo.Ai.

    :param topic: Тема поста (будет включена в prompt).
    :param context: Контекст поста (будет обрезан до 400 символов).
    :param num_images: Количество изображений для генерации. Если 0, возвращает пустой список.
    :param width: Ширина изображения.
    :param height: Высота изображения.
    :param guidance_scale: Параметр guidance_scale.
    :param num_steps: Количество шагов инференса.
    :return: Список путей к сохраненным файлам изображений.
    """
    if num_images <= 0:
        logging.info(f"[ImageGen] num_images={num_images}, пропускаем генерацию")
        return []

    prompt = f"{topic}. {context[:400]}"
    logging.info(f"[ImageGen] Используем LEONARDO. Промпт: {prompt}")

    headers = {
        "Authorization": f"Bearer {LEONARDO_API_KEY}",
        "Content-Type": "application/json"
    }

    payload = {
        "prompt": prompt,
        "negative_prompt": "blurry, distorted, bad anatomy",
        "width": width,
        "height": height,
        "num_images": num_images,
        "guidance_scale": guidance_scale,
        "num_inference_steps": num_steps,
        "public": False
    }

    try:
        async with httpx.AsyncClient(timeout=60) as client:
            response = await client.post(
                "https://cloud.leonardo.ai/api/rest/v1/generations",
                headers=headers,
                json=payload
            )

            if response.status_code >= 400:
                logging.error(f"[Leonardo] Ошибка {response.status_code}: {await response.aread()}")

            response.raise_for_status()
            result = response.json()

            generation_id = result.get("sdGenerationJob", {}).get("generationId")
            if not generation_id:
                logging.error("[Leonardo] Не удалось получить ID генерации")
                return []

            # Ожидаем выполнения генерации
            for attempt in range(60):  # до 5 минут (60*5 сек.)
                await asyncio.sleep(5)
                poll_resp = await client.get(
                    f"https://cloud.leonardo.ai/api/rest/v1/generations/{generation_id}",
                    headers=headers
                )
                poll_resp.raise_for_status()
                poll_data = poll_resp.json()
                images_meta = poll_data.get("generations_by_pk", {}).get("generated_images", [])

                if len(images_meta) >= num_images:
                    # Получили нужное количество изображений
                    saved_paths: List[str] = []
                    for idx, img in enumerate(images_meta[:num_images]):
                        image_url = img.get("url")
                        if not image_url:
                            continue
                        img_data = await client.get(image_url)
                        img_data.raise_for_status()
                        # Создаем уникальное имя файла
                        safe_hash = abs(hash(prompt))
                        filename = f"generated_image_{safe_hash}_{idx+1}.jpg"
                        with open(filename, "wb") as f:
                            f.write(img_data.content)
                        saved_paths.append(filename)
                    return saved_paths

            logging.error("[Leonardo] Таймаут ожидания изображения")
            return []

    except Exception as e:
        logging.error(f"Image generation failed: {e}")
        return []
