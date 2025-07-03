from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    BOT_TOKEN: str
    DATABASE_URL: str = 'sqlite+aiosqlite:///./database.db'
    CHANNEL_ID: int
    CHANNEL_JOIN_LINK: str
    GROUP_ID: int
    ADMIN_ID: int

    DIAMONDS_PRICE: int = 2
    LIFETIME_PREMIUM_PRICE: int = 250

    API_HOST: str = 'youtube-mp36.p.rapidapi.com'
    API_KEY: str

    model_config = SettingsConfigDict(
        env_file='.env',
        env_file_encoding='utf-8',
        extra='ignore'
    )


settings = Settings()
