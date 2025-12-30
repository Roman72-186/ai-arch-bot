from datetime import datetime, timedelta
from sqlalchemy import select, func, update
from sqlalchemy.ext.asyncio import AsyncSession
from db.models import User, PhotoUpload

# 1. Регистрация или получение пользователя
async def get_or_create_user(session: AsyncSession, tg_id: int):
    user = await session.get(User, tg_id)
    if not user:
        user = User(tg_id=tg_id)
        session.add(user)
        await session.commit()
        await session.refresh(user)
    return user

# 2. Проверка лимитов (сколько фото загружено за последние 24 часа)
async def check_user_limit(session: AsyncSession, tg_id: int) -> bool:
    # Определяем временную метку 24 часа назад
    time_threshold = datetime.now() - timedelta(days=1)
    
    # Считаем количество записей в photo_uploads для этого юзера за сутки
    stmt = (
        select(func.count(PhotoUpload.id))
        .where(PhotoUpload.user_id == tg_id)
        .where(PhotoUpload.created_at >= time_threshold)
    )
    result = await session.execute(stmt)
    count = result.scalar()
    
    # Возвращаем True, если лимит (3) еще не исчерпан
    return count < 30

# 3. Регистрация новой загрузки фото
async def add_photo_upload(session: AsyncSession, tg_id: int):
    new_upload = PhotoUpload(user_id=tg_id)
    session.add(new_upload)
    await session.commit()

# 4. Обновление thread_id (сброс или установка нового контекста)
async def update_user_thread(session: AsyncSession, tg_id: int, thread_id: str | None):
    stmt = (
        update(User)
        .where(User.tg_id == tg_id)
        .values(thread_id=thread_id)
    )
    await session.execute(stmt)
    await session.commit()

# 5. Получение текущего thread_id
async def get_user_thread(session: AsyncSession, tg_id: int) -> str | None:
    stmt = select(User.thread_id).where(User.tg_id == tg_id)
    result = await session.execute(stmt)
    return result.scalar()