"""
VK Publisher — публикация сообщений в VK сообществе.
Поддержка текста и фотографий.
"""

import time
import logging
from pathlib import Path

import vk_api
import requests

import config

log = logging.getLogger(__name__)


class VKPublisher:
    """Публикация постов в VK сообществе."""

    def __init__(self):
        self.session = vk_api.VkApiClient()
        self.group_id = int(config.Config.VK_GROUP_ID)
        self.last_request_time = 0

    def _rate_limit(self):
        """Соблюдение rate limiting VK API (3 запроса/сек)."""
        now = time.time()
        elapsed = now - self.last_request_time
        if elapsed < config.Config.VK_RATE_LIMIT:
            time.sleep(config.Config.VK_RATE_LIMIT - elapsed)
        self.last_request_time = time.time()

    def _upload_photos_to_server(self, photo_paths: list[Path]) -> list[dict]:
        """
        Загрузка фотографий на временный сервер VK.
        Возвращает список dict с photo, server, hash для wall.savePhotosServer.
        """
        if not photo_paths:
            return []

        try:
            # Получаем URL для загрузки
            self._rate_limit()
            upload_data = self.session.wall().savePhotosServer(
                group_id=self.group_id
            )
            upload_url = upload_data["upload_url"]

            uploaded_photos = []
            for i, photo_path in enumerate(photo_paths):
                self._rate_limit()
                with open(photo_path, "rb") as f:
                    files = {"photo": (photo_path.name, f, "image/jpeg")}
                    resp = requests.post(upload_url, files=files)
                    resp.raise_for_status()
                    data = resp.json()
                    data["_path"] = photo_path  # сохраняем путь для отладки
                    uploaded_photos.append(data)
                log.info(f"Фото {i+1}/{len(photo_paths)} загружено: {photo_path.name}")
                time.sleep(config.Config.VK_RATE_LIMIT)

            return uploaded_photos

        except Exception as e:
            log.error(f"Ошибка загрузки фото на сервер VK: {e}")
            raise

    def publish_post(
        self,
        text: str = "",
        photo_paths: list[Path] | None = None,
    ) -> int | None:
        """
        Публикация поста в VK.

        Args:
            text: Текст поста
            photo_paths: Список путей к фотографиям

        Returns:
            ID опубликованного поста или None при ошибке
        """
        if not text and not photo_paths:
            log.warning("Нет контента для публикации")
            return None

        log.info(
            f"Публикация в VK: text_len={len(text)}, photos={len(photo_paths or [])}"
        )

        # Подготовка параметров
        params = {
            "owner_id": f"-{self.group_id}",
            "message": text if text else None,
            "from_group": True,  # Публикация от имени группы
            "group_id": self.group_id,
        }

        # Загрузка фото
        if photo_paths:
            try:
                uploaded = self._upload_photos_to_server(photo_paths)
                if uploaded:
                    # VK требует передачи всех фото
                    photos_str = ",".join(
                        f"{item['photo']}:{item['server']}:{item['hash']}"
                        for item in uploaded
                    )
                    params["photos"] = photos_str
                    log.info(f"Подготовлено {len(uploaded)} фото для публикации")
            except Exception as e:
                log.error(f"Не удалось загрузить фото, публикуем без них: {e}")

        # Публикация с retry logic
        for attempt in range(1, config.Config.MAX_RETRIES + 1):
            try:
                self._rate_limit()
                post_params = {k: v for k, v in params.items() if v is not None}
                result = self.session.wall().post(
                    owner_id=post_params["owner_id"],
                    message=post_params.get("message"),
                    from_group=post_params.get("from_group"),
                    group_id=post_params.get("group_id"),
                    photos=post_params.get("photos"),
                )
                post_id = result[0].get("post_id") if isinstance(result, list) else result
                log.info(f"Пост опубликован в VK: post_id={post_id}")
                return post_id

            except vk_api.exceptions.VkApiError as e:
                log.error(f"Ошибка VK API (попытка {attempt}/{config.Config.MAX_RETRIES}): {e}")
                if attempt < config.Config.MAX_RETRIES:
                    wait_time = 2 ** attempt
                    log.info(f"Повтор через {wait_time} сек...")
                    time.sleep(wait_time)
                else:
                    log.error("Все попытки публикации исчерпаны")
                    return None

            except Exception as e:
                log.error(f"Неожиданная ошибка при публикации: {e}")
                return None

    def publish_with_photos(self, text: str, photo_paths: list[Path]) -> int | None:
        """Публикация поста с фотографиями."""
        return self.publish_post(text=text, photo_paths=photo_paths)

    def publish_text_only(self, text: str) -> int | None:
        """Публикация текстового поста."""
        return self.publish_post(text=text)
