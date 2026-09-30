from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):

    APP_NAME: str = "ProbeRat"
    VERSION: str = "1.0.0"

    FUNASR_URL: str = "http://127.0.0.1:8000"
    TTS_URL: str = "http://127.0.0.1:9001"
    TIMEOUT: int = 30


    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore"
    )


settings = Settings()