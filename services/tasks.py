import asyncio
from celery import Celery
from aiogram import Bot
from core.config import config

# Инициализируем Celery. Используем Redis как брокер и бэкенд.
celery_app = Celery(
    "worker",
    broker=config.redis_url,
    backend=config.redis_url
)

# Настройки для стабильности
celery_app.conf.update(
    task_track_started=True,
    task_serializer="json",
    accept_content=["json"],
    result_serializer="json",
    timezone="UTC"
)

async def send_async_notification(user_id: int):
    """
    Вспомогательная асинхронная функция для отправки сообщения.
    """
    bot = Bot(token=config.bot_token.get_secret_value())
    try:
        await bot.send_message(
            chat_id=user_id,
            text="🔔 <b>Прошли сутки!</b>\n\nТеперь вам снова доступна возможность оценить свою работу у Нейро помощника. Жду ваши фото!",
            parse_mode="HTML"
        )
    finally:
        await bot.session.close()

@celery_app.task(name="send_renewal_notification")
def send_renewal_notification(user_id: int):
    """
    Синхронная обертка Celery для запуска асинхронного кода бота.
    """
    loop = asyncio.get_event_loop()
    loop.run_until_complete(send_async_notification(user_id))