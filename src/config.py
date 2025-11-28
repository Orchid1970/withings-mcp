from pydantic_settings import BaseSettings
from functools import lru_cache

class Settings(BaseSettings):
    WITHINGS_CLIENT_ID: str = ""
    WITHINGS_CLIENT_SECRET: str = ""
    WITHINGS_ACCESS_TOKEN: str = "" # NEW: Add access token
    WITHINGS_REFRESH_TOKEN: str = "" # NEW: Add refresh token
    DATABASE_URL: str = "sqlite+aiosqlite:///./withings.db"
    ENCRYPTION_KEY: str = ""
    BASE_URL: str = "http://localhost:8000"
    
    class Config:
        env_file = ".env"
        extra = "ignore"

@lru_cache()
def get_settings() -> Settings:
    return Settings()
