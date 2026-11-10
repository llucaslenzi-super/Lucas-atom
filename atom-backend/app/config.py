from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    database_url: str = "postgresql+psycopg://atom_app@localhost:5432/atom"
    admin_database_url: str = "postgresql+psycopg://atom_owner@localhost:5432/atom"

    jwt_secret: str = "dev-only-change-me-in-secret-manager-0123456789"
    jwt_alg: str = "HS256"
    access_ttl_min: int = 30
    refresh_ttl_days: int = 14


settings = Settings()
