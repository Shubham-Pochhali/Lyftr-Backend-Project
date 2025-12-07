import os


class Settings:
    def __init__(self) -> None:
        # SQLite default as per spec
        self.DATABASE_URL: str = os.getenv("DATABASE_URL", "sqlite:////data/app.db")
        self.WEBHOOK_SECRET: str | None = os.getenv("WEBHOOK_SECRET")
        self.LOG_LEVEL: str = os.getenv("LOG_LEVEL", "INFO").upper()


settings = Settings()
