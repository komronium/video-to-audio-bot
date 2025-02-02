from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    BOT_TOKEN: str
    DATABASE_URL: str = 'sqlite:///./database.db'
    CHANNEL_ID: int
    CHANNEL_JOIN_LINK: str
    GROUP_ID: int
    ADMIN_ID: int

    model_config = SettingsConfigDict(
        env_file='.env',
        env_file_encoding='utf-8',
        extra='ignore'
    )


settings = Settings()
