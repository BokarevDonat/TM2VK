"""
Вспомогательные функции:
- Скачивание фотографий из Telegram
- Обработка текста (очистка, конвертация форматирования)
- Оптимизация изображений для VK
"""

import os
import re
import logging
from pathlib import Path

from PIL import Image

import config

log = logging.getLogger(__name__)


def setup_working_dir() -> Path:
    """Создаёт рабочую директорию для временных файлов."""
    work_dir = Path(config.Config.WORKING_DIR)
    work_dir.mkdir(parents=True, exist_ok=True)
    return work_dir


def clean_text(text: str) -> str:
    """
    Очистка текста от лишних пробелов и переносов.
    Сохранение форматирования Telegram (жирный, курсив, монокод).
    """
    if not text:
        return ""

    # Удаление двойных переносов строк
    text = re.sub(r'\n{3,}', '\n\n', text)

    # Удаление пробелов в начале/конце каждой строки
    lines = [line.strip() for line in text.splitlines()]
    text = '\n'.join(lines)

    # Конвертация Telegram-форматирования в plain text
    # Telegram uses Markdown-like syntax
    # __bold__ -> **bold**
    text = re.sub(r'__([^_]+)__', r'**\1**', text)
    # __monospace__ -> `monospace`
    text = re.sub(r'__([^_]+)__', r'```\1```', text)
    # ~strikethrough~ -> ~~strikethrough~~
    text = re.sub(r'~([^~]+)~', r'~~\1~~', text)
    # ||spoiler|| -> ||spoiler||
    # (VK supports ||spoiler|| natively)

    # Ограничение длины текста
    if len(text) > config.Config.MAX_TEXT_LENGTH:
        text = text[:config.Config.MAX_TEXT_LENGTH - 3] + "..."
        log.warning(f"Текст усечён до {config.Config.MAX_TEXT_LENGTH} символов")

    return text.strip()


def optimize_image(image_path: Path) -> Path:
    """
    Оптимизация изображения для VK.
    Сжимает до MAX_IMAGE_DIMENSION по длинной стороне.
    """
    try:
        img = Image.open(image_path)
        width, height = img.size

        # Масштабирование если нужно
        if width > config.Config.MAX_IMAGE_DIMENSION or height > config.Config.MAX_IMAGE_DIMENSION:
            # Вычисляем новый размер с сохранением пропорций
            if width > height:
                new_width = config.Config.MAX_IMAGE_DIMENSION
                new_height = int(height * (new_width / width))
            else:
                new_height = config.Config.MAX_IMAGE_DIMENSION
                new_width = int(width * (new_height / height))

            img = img.resize((new_width, new_height), Image.Resampling.LANCZOS)
            log.info(f"Изображение масштабировано: {width}x{height} -> {new_width}x{new_height}")

        # Сохранение с оптимизацией
        optimized_path = image_path.with_name(image_path.stem + "_optimized.jpg")
        # Конвертация в RGB если нужно (JPEG не поддерживает прозрачность)
        if img.mode in ("RGBA", "P"):
            img = img.convert("RGB")

        img.save(optimized_path, "JPEG", quality=85, optimize=True)
        log.info(f"Изображение оптимизировано: {optimized_path}")
        return optimized_path

    except Exception as e:
        log.error(f"Ошибка оптимизации изображения {image_path}: {e}")
        return image_path


async def download_photo(photo) -> Path | None:
    """
    Скачивание фотографии из Telegram.
    Возвращает путь к сохранённому файлу или None при ошибке.
    photo — объект telegram.PhotoSize (выбирается самый большой размер)
    """
    try:
        work_dir = setup_working_dir()
        # photo — список PhotoSize, берём самый большой (последний)
        if isinstance(photo, list):
            photo_obj = max(photo, key=lambda p: p.width * p.height)
        else:
            photo_obj = photo

        file_id = photo_obj.file_id
        file = await photo_obj.download(destination_dir=str(work_dir))
        file_path = Path(file)

        # Переименование в .jpg
        jpg_path = file_path.with_suffix(".jpg")
        if file_path != jpg_path:
            file_path.rename(jpg_path)
            file_path = jpg_path

        # Оптимизация
        optimized_path = optimize_image(file_path)

        log.info(f"Фото скачано: {optimized_path}")
        return optimized_path

    except Exception as e:
        log.error(f"Ошибка скачивания фото: {e}")
        return None


def extract_photos(message) -> list:
    """
    Извлечение фотографий из Telegram-сообщения.
    Возвращает список PhotoSize объектов.
    """
    if hasattr(message, 'photo') and message.photo:
        return message.photo
    return []


def extract_caption(message) -> str:
    """Извлечение текстового описания из сообщения."""
    if hasattr(message, 'caption') and message.caption:
        return message.caption
    if hasattr(message, 'text'):
        return message.text
    return ""
