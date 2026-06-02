from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    app_name: str = Field(default="industrail AI Platform")
    app_version: str = Field(default="0.1.0")
    environment: str = Field(default="development")

    database_url: str = Field(
        default="postgresql+psycopg://postgres:postgres@localhost:5432/industrial_ai"
    )

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encodeing="utf-8",
    )


settings = Settings()
