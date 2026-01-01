import logging
from aiogram import Router, F, types
from aiogram.filters import Command
from html.parser import HTMLParser

from db.engine import async_session
from db.requests import (
    get_or_create_user,
    check_user_limit,
    add_photo_upload,
    update_user_thread,
    get_user_thread,
)
from services.openai_service import ai_service

router = Router()
logger = logging.getLogger(__name__)

MAX_TG_LEN = 3500  # лимит Telegram ~4096

class _HTMLStripper(HTMLParser):
    def __init__(self):
        super().__init__()
        self.parts = []

    def handle_data(self, data: str):
        if data:
            self.parts.append(data)

    def get_text(self) -> str:
        return "".join(self.parts)


def strip_html(text: str) -> str:
    s = _HTMLStripper()
    s.feed(text or "")
    s.close()
    # чуть нормализуем пробелы/переносы
    return " ".join(s.get_text().split())

async def safe_delete(msg: types.Message | None):
    if not msg:
        return
    try:
        await msg.delete()
    except Exception:
        pass


async def send_long(message: types.Message, text: str):
    if not text:
        await message.answer("⚠️ Пустой ответ от ИИ. Попробуйте ещё раз.")
        return

    text = strip_html(str(text))

    for i in range(0, len(text), MAX_TG_LEN):
        await message.answer(text[i:i + MAX_TG_LEN])


@router.message(Command("start"))
async def cmd_start(message: types.Message):
    async with async_session() as session:
        await get_or_create_user(session, message.from_user.id)

    await message.answer("Пришли фото своей работы.")


@router.message(F.photo)
async def handle_photo(message: types.Message):
    tg_id = message.from_user.id
    status_msg = await message.answer("Изучаю...")

    try:
        # 1) Проверка лимита + создание пользователя
        async with async_session() as session:
            await get_or_create_user(session, tg_id)

            if not await check_user_limit(session, tg_id):
                await safe_delete(status_msg)
                await message.answer("Лимит исчерпан.")
                return

        # 2) Фото -> URL
        photo = message.photo[-1]
        file = await message.bot.get_file(photo.file_id)
        photo_url = f"https://api.telegram.org/file/bot{message.bot.token}/{file.file_path}"

        # 3) Анализ фото (ВАЖНО: без thread_id)
        new_thread_id, response_text = await ai_service.analyze_photo(photo_url)

        # 4) Сохранение thread + счетчик
        async with async_session() as session:
            await update_user_thread(session, tg_id, new_thread_id)
            await add_photo_upload(session, tg_id)

        # 5) Удаляем статус и отправляем ответ
        await safe_delete(status_msg)
        await send_long(message, response_text)

    except Exception:
        logger.exception("Ошибка в handle_photo")
        await safe_delete(status_msg)
        await message.answer("❌ Произошла ошибка при анализе фото. Попробуйте позже.")


@router.message(F.text & ~F.command)
async def handle_text(message: types.Message):
    tg_id = message.from_user.id
    status_msg = await message.answer("Думаю...")

    try:
        # 1) Берём thread_id
        async with async_session() as session:
            thread_id = await get_user_thread(session, tg_id)

        if not thread_id:
            await safe_delete(status_msg)
            await message.answer("Сначала пришли фото, чтобы я создал контекст.")
            return

        # 2) Follow-up
        response_text = await ai_service.ask_follow_up(thread_id, message.text)

        # 3) Удаляем статус и отправляем ответ
        await safe_delete(status_msg)
        await send_long(message, response_text)

    except Exception:
        logger.exception("Ошибка в handle_text")
        await safe_delete(status_msg)
        await message.answer("❌ Ошибка при обработке запроса. Попробуйте позже.")
