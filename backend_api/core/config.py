import os
from dotenv import load_dotenv

load_dotenv()  # charge .env

class Settings:
    MONGO_URL: str = os.getenv("MONGO_URL")
    DATABASE_NAME: str = os.getenv("DATABASE_NAME")
    ENV: str = os.getenv("ENV", "development")

settings = Settings()