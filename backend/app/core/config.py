from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    app_name: str = Field(default="industrail AI Platform")
    app_version: str = Field(default="0.1.0")
    environment: str = Field(default="development")

    database_url: str = Field(
        default="postgresql+psycopg://postgres:postgres@localhost:5432/industrial_ai"
    )
    secret_key: str

    algorithm: str = "HS256"

    access_token_expire_minutes: int = 60

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encodeing="utf-8",
    )


settings = Settings()
