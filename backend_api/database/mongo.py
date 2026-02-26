from motor.motor_asyncio import AsyncIOMotorClient
from backend_api.core.config import settings
import logging

logger = logging.getLogger(__name__)

class MongoDB:
    client: AsyncIOMotorClient = None
    db = None

mongodb = MongoDB()


# 🔌 Connexion au démarrage de FastAPI
async def connect_to_mongo():
    try:
        mongodb.client = AsyncIOMotorClient(settings.MONGO_URL)
        mongodb.db = mongodb.client[settings.DATABASE_NAME]

        # Ping pour vérifier connexion
        await mongodb.client.admin.command("ping")

        logger.info("✅ Connected to MongoDB")

    except Exception as e:
        logger.error("❌ MongoDB connection failed", exc_info=True)
        raise e


# 🔌 Fermeture propre
async def close_mongo_connection():
    if mongodb.client:
        mongodb.client.close()
        logger.info("🔌 MongoDB connection closed")


# 📦 Collections centralisées
def get_listings_collection():
    return mongodb.db["listings"]


def get_users_collection():
    return mongodb.db["users"]


def get_bids_collection():
    return mongodb.db["bids"]