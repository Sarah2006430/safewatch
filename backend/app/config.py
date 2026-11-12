from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    database_url: str = "postgresql+asyncpg://postgres:postgres@localhost:5432/emergency"

    jwt_secret: str = "change-this-secret-in-production"
    jwt_expire_minutes: int = 720

    # Shared secret used by the detection service (sent as X-API-Key header)
    detector_api_key: str = "detector-secret-key"

    media_dir: str = "media"
    cors_origins: str = "http://localhost:5173,http://127.0.0.1:5173"

    admin_username: str = "admin"
    admin_password: str = "admin123"

    seed_demo_data: bool = True
    # Default map centre used for demo seed data (Bengaluru). Change to your city.
    default_lat: float = 12.9716
    default_lon: float = 77.5946

    # Window in which a repeated detection (same camera + type) is merged into
    # the existing open incident instead of creating a new one.
    dedup_window_seconds: int = 120


settings = Settings()
