"""
Конфигурация бота. Загрузка параметров из .env файла.
"""

import os
from pathlib import Path
from dotenv import load_dotenv

# Загрузка .env из корня проекта
_env_path = Path(__file__).parent / ".env"
load_dotenv(_env_path)


class Config:
    """Конфигурация бота из переменных окружения."""

    # Telegram
    TG_BOT_TOKEN: str = os.getenv("TG_BOT_TOKEN", "")
    TG_CHANNEL_ID: str = os.getenv("TG_CHANNEL_ID", "")
    TG_PROXY_URL: str = os.getenv("TG_PROXY_URL", "")  # опционально

    # VK
    VK_COMMUNITY_TOKEN: str = os.getenv("VK_COMMUNITY_TOKEN", "")
    VK_GROUP_ID: str = os.getenv("VK_GROUP_ID", "")

    # Настройки
    LOG_LEVEL: str = os.getenv("LOG_LEVEL", "INFO").upper()
    WORKING_DIR: str = os.getenv("WORKING_DIR", "./tmp")

    # Ограничения
    MAX_TEXT_LENGTH: int = 2048  # VK limit
    MAX_IMAGE_DIMENSION: int = 1920  # px
    VK_RATE_LIMIT: float = 0.33  # сек между запросами (3/сек)
    MAX_RETRIES: int = 3  # количество повторных попыток

    @classmethod
    def validate(cls) -> list[str]:
        """Валидация обязательных параметров."""
        errors = []
        if not cls.TG_BOT_TOKEN:
            errors.append("TG_BOT_TOKEN не указан в .env")
        if not cls.TG_CHANNEL_ID:
            errors.append("TG_CHANNEL_ID не указан в .env")
        if not cls.VK_COMMUNITY_TOKEN:
            errors.append("VK_COMMUNITY_TOKEN не указан в .env")
        if not cls.VK_GROUP_ID:
            errors.append("VK_GROUP_ID не указан в .env")
        return errors
