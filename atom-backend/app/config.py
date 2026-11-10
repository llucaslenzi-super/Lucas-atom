from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    database_url: str = "postgresql+psycopg://atom_app@localhost:5432/atom"
    admin_database_url: str = "postgresql+psycopg://atom_owner@localhost:5432/atom"

    jwt_secret: str = "dev-only-change-me-in-secret-manager-0123456789"
    jwt_alg: str = "HS256"
    access_ttl_min: int = 30
    refresh_ttl_days: int = 14

    # Internal callback (n8n/worker -> API) shared secret (HMAC).
    callback_hmac_secret: str = "dev-only-callback-secret-change-me-0123456789"

    # External providers. When a key is absent, the mock provider is used, so
    # the whole journey runs locally; set a key to activate the real client.
    openai_api_key: str | None = None
    apify_token: str | None = None
    google_places_key: str | None = None

    # Local object storage dir (swapped for Cloud Storage in Bloco 8).
    storage_dir: str = ".storage"

    # Cost guardrail per consulta (USD). Pipeline stops + marks parcial if hit.
    cost_ceiling_usd: float = 9.0


settings = Settings()
