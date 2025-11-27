from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    BOT_TOKEN: str
    DATABASE_URL: str = 'sqlite+aiosqlite:///./database.db'
    CHANNEL_ID: int
    GROUP_ID: int
    ADMIN_ID: int

    DIAMONDS_PRICE: int = 2
    LIFETIME_PREMIUM_PRICE: int = 200

    model_config = SettingsConfigDict(
        env_file='.env',
        env_file_encoding='utf-8',
        extra='ignore'
    )


settings = Settings()
