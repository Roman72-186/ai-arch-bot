from sqlalchemy.ext.asyncio import create_async_engine, async_sessionmaker, AsyncSession
from core.config import config

# Создаем движок. echo=False в продакшене, чтобы не забивать логи SQL-запросами
engine = create_async_engine(
    config.database_url,
    echo=False,
)

# Фабрика сессий. expire_on_commit=False критично для асинхронности
async_session = async_sessionmaker(
    engine, 
    class_=AsyncSession, 
    expire_on_commit=False
)

# Функция-помощник для получения сессии (понадобится в middleware и хендлерах)
async def get_session() -> AsyncSession:
    async with async_session() as session:
        yield session