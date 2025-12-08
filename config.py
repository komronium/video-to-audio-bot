from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    BOT_TOKEN: str
    DATABASE_URL: str = 'sqlite+aiosqlite:///./database.db'

    ADMIN_ID: int
    CHANNEL_ID: int

    GROUP_ID: int = -1003315417593
    USER_TOPIC_ID: int = 15
    DIAMONDS_TOPIC_ID: int = 17


    DIAMONDS_PRICE: int = 2
    LIFETIME_PREMIUM_PRICE: int = 200

    model_config = SettingsConfigDict(
        env_file='.env',
        env_file_encoding='utf-8',
        extra='ignore'
    )


settings = Settings()
