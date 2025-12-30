from typing import List, Optional
from aiogram import Router, F, Bot
from aiogram.types import Message
from aiogram.filters import CommandStart

from db.engine import async_session
from db.requests import (
    get_or_create_user, 
    check_user_limit, 
    add_photo_upload, 
    update_user_thread, 
    get_user_thread
)
from services.openai_service import ai_service
from services.tasks import send_renewal_notification
from core.config import config

router = Router()

@router.message(CommandStart())
async def cmd_start(message: Message):
    """Приветствие и регистрация пользователя в БД"""
    async with async_session() as session:
        await get_or_create_user(session, message.from_user.id)
    
    welcome_text = (
        "<b>Привет! Я твой Нейро-помощник.</b> 🎨\n\n"
        "Отправь мне фото своей работы, и я проведу её подробный анализ.\n\n"
        "📍 <b>Лимиты:</b>\n"
        "— До 3-х работ в сутки.\n"
        "— К каждой работе можно задать уточняющие вопросы.\n"
        "— Новое фото сбрасывает контекст предыдущего обсуждения.\n\n"
        "<i>Просто прикрепи фото к сообщению!</i>"
    )
    await message.answer(welcome_text, parse_mode="HTML")


@router.message(F.photo)
async def handle_photo(message: Message, bot: Bot, album: Optional[List[Message]] = None):
    """
    Обработка фото или альбома. 
    Благодаря AlbumMiddleware, 'album' содержит список сообщений медиагруппы.
    """
    tg_id = message.from_user.id
    
    async with async_session() as session:
        # 1. Проверка лимитов (3 фото в 24 часа)
        if not await check_user_limit(session, tg_id):
            await message.answer(
                "⚠️ <b>Лимит исчерпан.</b>\n"
                "Вы уже оценили 3 работы за последние 24 часа. "
                "Я уведомлю вас, когда возможность снова появится!",
                parse_mode="HTML"
            )
            return

        status_msg = await message.answer("⏳ <i>Нейросеть изучает вашу работу... это займет несколько секунд.</i>", parse_mode="HTML")

        try:
            # 2. Получаем ссылку на фото. 
            # Если это альбом, берем фото из первого сообщения группы.
            target_msg = album[0] if album else message
            file_id = target_msg.photo[-1].file_id
            file = await bot.get_file(file_id)
            
            # OpenAI скачает фото по этой ссылке
            photo_url = f"https://api.telegram.org/file/bot{config.bot_token.get_secret_value()}/{file.file_path}"

            # 3. Запрос к OpenAI Assistant API (Vision)
            # Метод analyze_photo всегда создает НОВЫЙ тред (сброс контекста)
            thread_id, response_text = await ai_service.analyze_photo(photo_url)

            # 4. Обновление данных в БД
            await update_user_thread(session, tg_id, thread_id)
            await add_photo_upload(session, tg_id)

            # 5. Планируем уведомление через Celery на +24 часа
            send_renewal_notification.apply_async(args=[tg_id], countdown=86400)

            # 6. Ответ пользователю
            await status_msg.delete()
            await message.answer(response_text, parse_mode="HTML")

        except Exception as e:
            await status_msg.edit_text("❌ Произошла ошибка при анализе фото. Попробуйте позже.")
            # Здесь можно добавить логирование ошибки: logger.error(e)


@router.message(F.text)
async def handle_text(message: Message):
    """Обработка уточняющих вопросов (текстовые сообщения)"""
    tg_id = message.from_user.id
    
    # Игнорируем команды
    if message.text.startswith("/"):
        return

    async with async_session() as session:
        thread_id = await get_user_thread(session, tg_id)
        
        # Если thread_id нет, значит фото еще не присылали или лимит сброшен
        if not thread_id:
            await message.answer("📸 <b>Сначала отправьте фото работы!</b>\nЯ смогу ответить на вопросы только после анализа изображения.", parse_mode="HTML")
            return

        status_msg = await message.answer("🤔 <i>Пишу ответ...</i>", parse_mode="HTML")

        try:
            # Отправляем текст в существующий поток (сохранение контекста текущей работы)
            response_text = await ai_service.ask_follow_up(thread_id, message.text)
            
            await status_msg.delete()
            await message.answer(response_text, parse_mode="HTML")
            
        except Exception as e:
            await status_msg.edit_text("❌ Не удалось получить ответ от ассистента.")