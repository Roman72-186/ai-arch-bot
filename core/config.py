from pydantic_settings import BaseSettings, SettingsConfigDict
from pydantic import SecretStr

class Settings(BaseSettings):
    # Используем SecretStr, чтобы токены не светились в логах при ошибках
    bot_token: SecretStr
    openai_api_key: SecretStr
    assistant_id: str
    
    database_url: str
    redis_url: str

    # Автоматическое чтение из .env
    model_config = SettingsConfigDict(
        env_file=".env", 
        env_file_encoding="utf-8",
        extra="ignore"
    )

config = Settings()