from pydantic import BaseSettings

class Settings(BaseSettings):
    # Application settings
    app_name: str = "Ntheemba Auth Service"
    app_version: str = "1.0.0"
    debug: bool = False

    # Database settings
    database_url: str

    # Security settings
    secret_key: str
    algorithm: str = "HS256"
    access_token_expire_minutes: int = 30

    class Config:
        env_file = ".env"

settings = Settings()