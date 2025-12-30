import asyncio
from typing import Any, Awaitable, Callable, Dict, List, Union

from aiogram import BaseMiddleware
from aiogram.types import Message, TelegramObject

class AlbumMiddleware(BaseMiddleware):
    """
    Middleware для сбора медиагрупп (альбомов).
    Задержка 0.6 сек позволяет собрать все части сообщения.
    """
    def __init__(self, latency: float = 0.6):
        self.latency = latency
        self.album_data: Dict[str, List[Message]] = {}

    async def __call__(
        self,
        handler: Callable[[TelegramObject, Dict[str, Any]], Awaitable[Any]],
        event: TelegramObject,
        data: Dict[str, Any]
    ) -> Any:
        if not isinstance(event, Message) or not event.media_group_id:
            return await handler(event, data)

        mid = event.media_group_id
        
        # Если это первое сообщение группы — создаем список
        if mid not in self.album_data:
            self.album_data[mid] = [event]
            
            # Ждем немного, пока прилетят остальные части альбома
            await asyncio.sleep(self.latency)
            
            # Добавляем весь список сообщений в данные хендлера
            data["album"] = self.album_data[mid]
            
            # Удаляем данные из временного хранилища
            del self.album_data[mid]
            
            # Запускаем хендлер только один раз для всей группы
            return await handler(event, data)
        
        # Если сообщение — часть группы, которая уже "ждет", просто добавляем его в список
        self.album_data[mid].append(event)
        return None