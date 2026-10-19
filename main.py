"""
TG2VK Bot — пересылка сообщений из Telegram-канала в VK-сообщество.

Запуск:
    python main.py
"""

import asyncio
import logging
import sys
import time
from pathlib import Path

from telegram import Update
from telegram.ext import (
    Application,
    MessageHandler,
    ContextTypes,
)

import config
from utils import (
    setup_working_dir,
    clean_text,
    extract_photos,
    extract_caption,
    download_photo,
)
from vk_publisher import VKPublisher

# Настройка логирования
def setup_logging():
    """Настройка логирования."""
    log_level = getattr(logging, config.Config.LOG_LEVEL, logging.INFO)

    formatter = logging.Formatter(
        "%(asctime)s [%(levelname)s] %(name)s: %(message)s",
        datefmt="%Y-%m-%d %H:%M:%S"
    )

    console_handler = logging.StreamHandler(sys.stdout)
    console_handler.setFormatter(formatter)

    log_dir = Path("./logs")
    log_dir.mkdir(exist_ok=True)
    file_handler = logging.FileHandler(
        log_dir / "bot.log",
        encoding="utf-8"
    )
    file_handler.setFormatter(formatter)

    root_logger = logging.getLogger()
    root_logger.setLevel(log_level)
    root_logger.addHandler(console_handler)
    root_logger.addHandler(file_handler)

    logging.getLogger("httpx").setLevel(logging.WARNING)
    logging.getLogger("telegram").setLevel(logging.INFO)


# Файл для хранения ID опубликованных сообщений
DUPLICATES_FILE = Path("./published_ids.txt")
_published_ids: set[str] = set()


def load_published_ids():
    """Загрузка списка уже опубликованных ID."""
    if DUPLICATES_FILE.exists():
        with open(DUPLICATES_FILE, "r", encoding="utf-8") as f:
            return set(line.strip() for line in f if line.strip())
    return set()


def save_published_ids():
    """Сохранение списка опубликованных ID."""
    with open(DUPLICATES_FILE, "w", encoding="utf-8") as f:
        for msg_id in sorted(_published_ids):
            f.write(f"{msg_id}\n")


def is_duplicate(message_id: int) -> bool:
    """Проверка на дубликат."""
    return str(message_id) in _published_ids


def mark_published(message_id: int):
    """Пометить сообщение как опубликованное."""
    _published_ids.add(str(message_id))
    if len(_published_ids) % 50 == 0:
        save_published_ids()
        log.info(f"Сохранено {len(_published_ids)} ID в файл дубликатов")


async def handle_channel_post(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Обработка нового сообщения в Telegram-канале."""
    global _published_ids

    log = logging.getLogger(__name__)

    # Проверяем, что это сообщение из канала
    message = update.channel_post
    if not message:
        return

    # Проверка на дубликат
    if is_duplicate(message.message_id):
        log.info(f"Дубликат, пропускаем: message_id={message.message_id}")
        return

    # Извлечение текста
    text = extract_caption(message)
    if not text:
        text = ""

    # Извлечение фотографий
    photos = extract_photos(message)

    # Пропускаем сообщения без контента
    if not text and not photos:
        log.info(f"Сообщение без контента, пропускаем: message_id={message.message_id}")
        return

    # Очистка текста
    clean_txt = clean_text(text)

    log.info(
        f"Новое сообщение: id={message.message_id}, "
        f"text_len={len(clean_txt)}, photos={len(photos)}"
    )

    # Публикация в VK
    try:
        # Скачивание фотографий
        downloaded_photos = []
        if photos:
            log.info(f"Скачивание {len(photos)} фотографий...")
            for photo in photos:
                photo_path = await download_photo(photo)
                if photo_path:
                    downloaded_photos.append(photo_path)

        # Публикация
        publisher = VKPublisher()
        if downloaded_photos:
            post_id = publisher.publish_with_photos(clean_txt, downloaded_photos)
        else:
            post_id = publisher.publish_text_only(clean_txt)

        if post_id:
            mark_published(message.message_id)
            log.info(f"Успешно: TG#{message.message_id} -> VK#{post_id}")
        else:
            log.error(f"Не удалось опубликовать TG#{message.message_id}")

    except Exception as e:
        log.error(f"Ошибка публикации TG#{message.message_id}: {e}", exc_info=True)


def main():
    """Точка входа."""
    setup_logging()
    log = logging.getLogger(__name__)

    log.info("=" * 60)
    log.info("TG2VK Bot запускается...")
    log.info("=" * 60)

    # Валидация конфигурации
    errors = config.Config.validate()
    if errors:
        log.error("Ошибка конфигурации:")
        for error in errors:
            log.error(f"  - {error}")
        sys.exit(1)

    log.info("Конфигурация валидна")
    log.info(f"Telegram channel: {config.Config.TG_CHANNEL_ID}")
    log.info(f"VK group: {config.Config.VK_GROUP_ID}")

    # Загрузка опубликованных ID
    _published_ids.update(load_published_ids())
    log.info(f"Загружено {len(_published_ids)} ID из файла дубликатов")

    # Создание рабочей директории
    setup_working_dir()

    # Создание приложения
    builder = Application.builder().token(config.Config.TG_BOT_TOKEN)
    if config.Config.TG_PROXY_URL:
        builder.proxy(config.Config.TG_PROXY_URL)
        log.info(f"Используется прокси: {config.Config.TG_PROXY_URL}")
    app = builder.build()

    # Добавление обработчика
    app.add_handler(MessageHandler(None, handle_channel_post))

    log.info("Telegram Listener запущен")
    log.info("Ожидание новых сообщений...")
    log.info("Для остановки нажмите Ctrl+C")

    # Запуск бота
    try:
        app.run_polling(drop_pending_updates=True)
    except KeyboardInterrupt:
        save_published_ids()
        log.info(f"Сохранено {len(_published_ids)} ID в файл дубликатов")
        log.info("Бот остановлен пользователем")
    except Exception as e:
        save_published_ids()
        log.error(f"Критическая ошибка: {e}", exc_info=True)
        sys.exit(1)


if __name__ == "__main__":
    main()
