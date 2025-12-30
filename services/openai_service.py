import asyncio
from openai import AsyncOpenAI
from core.config import config

class OpenAIService:
    def __init__(self):
        # Инициализируем клиент с ключом из нашего конфига
        self.client = AsyncOpenAI(api_key=config.openai_api_key.get_secret_value())
        self.assistant_id = config.assistant_id

    async def analyze_photo(self, photo_url: str) -> tuple[str, str]:
        """
        Создает новый тред, отправляет фото и получает первичную оценку.
        Возвращает кортеж: (thread_id, response_text)
        """
        # 1. Создаем новый поток (сброс контекста для новой работы)
        thread = await self.client.beta.threads.create()

        # 2. Добавляем сообщение с картинкой
        # Инструкция вшита прямо в запрос для надежности HTML-форматирования
        await self.client.beta.threads.messages.create(
            thread_id=thread.id,
            role="user",
            content=[
                {
                    "type": "text", 
                    "text": "Проанализируй эту работу согласно своим инструкциям. "
                            "ОТВЕТЬ СТРОГО В HTML ФОРМАТЕ (используй <b>, <i>, <code>)."
                },
                {
                    "type": "image_url",
                    "image_url": {"url": photo_url}
                }
            ]
        )

        # 3. Запускаем ассистента и ждем результат (Polling)
        response_text = await self._get_assistant_response(thread.id)
        return thread.id, response_text

    async def ask_follow_up(self, thread_id: str, question: str) -> str:
        """
        Добавляет текстовый вопрос в существующий тред.
        """
        await self.client.beta.threads.messages.create(
            thread_id=thread_id,
            role="user",
            content=question
        )

        return await self._get_assistant_response(thread_id)

    async def _get_assistant_response(self, thread_id: str) -> str:
        """
        Вспомогательный метод для запуска ассистента и получения текста.
        """
        # Запуск (Run)
        run = await self.client.beta.threads.runs.create_and_poll(
            thread_id=thread_id,
            assistant_id=self.assistant_id,
            # Дополнительная инструкция для принудительного HTML
            instructions="Please format your response using HTML tags supported by Telegram. "
                         "Do not use markdown like **bold**."
        )

        if run.status == 'completed':
            messages = await self.client.beta.threads.messages.list(thread_id=thread_id)
            # Берем самое последнее сообщение от ассистента
            return messages.data[0].content[0].text.value
        else:
            return f"Ошибка при обработке: {run.status}"

# Создаем синглтон для использования в боте
ai_service = OpenAIService()