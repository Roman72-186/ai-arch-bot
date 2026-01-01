import asyncio
import logging
import sys

from aiogram import Bot, Dispatcher
from aiogram.fsm.storage.redis import RedisStorage, DefaultKeyBuilder
from aiogram.client.default import DefaultBotProperties
from aiogram.enums import ParseMode

from core.config import config
from bot.handlers.user import router as user_router
from bot.middlewares.album import AlbumMiddleware
from db.engine import engine
from db.models import Base

# Настройка логирования
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    stream=sys.stdout
)
logger = logging.getLogger(__name__)

async def on_startup():
    """Действия при запуске бота"""
    logger.info("Инициализация базы данных...")
    async with engine.begin() as conn:
        # Создаем таблицы, если их еще нет
        await conn.run_sync(Base.metadata.create_all)
    logger.info("База данных готова.")

async def main():
    # 1. Инициализация хранилища (Redis) для FSM
    # Даже если мы не используем сложные стейты, Redis полезен для стабильности
    storage = RedisStorage.from_url(
        config.redis_url,
        key_builder=DefaultKeyBuilder(with_destiny=True)
    )

    # 2. Инициализация бота
    bot = Bot(
        token=config.bot_token.get_secret_value(),
        default=DefaultBotProperties(parse_mode=None)
    )

    # 3. Инициализация диспетчера
    dp = Dispatcher(storage=storage)

    # 4. Регистрация Middleware для обработки альбомов (Media Group)
    # Важно: регистрируем её на уровень выше хендлеров
    dp.message.middleware(AlbumMiddleware(latency=0.6))

    # 5. Подключение роутеров
    dp.include_router(user_router)

    # 6. Регистрация функций запуска
    dp.startup.register(on_startup)

    # 7. Запуск Polling
    logger.info("Бот запущен и готов к работе!")
    try:
        await dp.start_polling(bot)
    finally:
        await bot.session.close()
        await engine.dispose()

if __name__ == "__main__":
    try:
        asyncio.run(main())
    except (KeyboardInterrupt, SystemExit):
        logger.info("Бот остановлен.")
