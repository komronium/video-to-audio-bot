from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    BOT_TOKEN: str
    DATABASE_URL: str = "sqlite+aiosqlite:///./database.db"
    CHANNEL_ID: int
    CHANNEL_JOIN_LINK: str = ""
    GROUP_ID: int
    ADMIN_ID: int
    SERVER_IP: str = "89.169.47.171"
    API_HOST: str = "youtube-mp36.p.rapidapi.com"
    API_KEY: str = ""

    # Demo MP3 sent once to brand-new users so they immediately see the output.
    # Admin runs /demo_capture (uploads any MP3 → bot replies with file_id) and
    # saves it in .env. Empty value disables the demo step.
    ONBOARDING_DEMO_FILE_ID: str = ""

    LIFETIME_PREMIUM_PRICE: int = 200
    # Monthly subscription — softer entry tier vs lifetime. Picked to be
    # ~1/4 of lifetime so break-even is 4 months → light commitment, but
    # economically clear that lifetime is the better deal long-term.
    MONTHLY_PREMIUM_PRICE: int = 49
    MONTHLY_PREMIUM_DAYS: int = 30
    DIAMONDS_PRICES: dict[int, int] = {
        1: 2,
        3: 5,
        5: 8,
        10: 15,
        20: 28,
        50: 70,
    }

    model_config = SettingsConfigDict(
        env_file=".env", env_file_encoding="utf-8", extra="ignore"
    )


settings = Settings()
