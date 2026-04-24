from motor.motor_asyncio import AsyncIOMotorClient
from app.config import get_settings
from typing import Optional, Dict, Any
import logging

logger = logging.getLogger(__name__)
settings = get_settings()

_client: Optional[AsyncIOMotorClient] = None


def get_client() -> AsyncIOMotorClient:
    global _client
    if _client is None:
        _client = AsyncIOMotorClient(settings.MONGODB_URL)
    return _client


def get_db():
    return get_client()[settings.MONGODB_DB]


async def save_file_document(doc: Dict[str, Any]) -> str:
    """Save file document to MongoDB."""
    db = get_db()
    result = await db.files.insert_one(doc)
    return str(result.inserted_id)


async def get_file_document(file_id: str) -> Optional[Dict[str, Any]]:
    """Retrieve file document by file_id."""
    db = get_db()
    doc = await db.files.find_one({"file_id": file_id})
    return doc


async def update_file_document(file_id: str, updates: Dict[str, Any]) -> bool:
    """Update an existing file document."""
    db = get_db()
    result = await db.files.update_one(
        {"file_id": file_id},
        {"$set": updates}
    )
    return result.modified_count > 0


async def list_file_documents(user_id: Optional[str] = None) -> list:
    """List all file documents, optionally filtered by user."""
    db = get_db()
    query = {}
    if user_id:
        query["user_id"] = user_id
    cursor = db.files.find(query, {"_id": 0})
    return await cursor.to_list(length=100)


async def save_user(user_data: Dict[str, Any]) -> bool:
    """Save a user to the database."""
    db = get_db()
    existing = await db.users.find_one({"username": user_data["username"]})
    if existing:
        return False
    await db.users.insert_one(user_data)
    return True


async def get_user(username: str) -> Optional[Dict[str, Any]]:
    """Retrieve user by username."""
    db = get_db()
    return await db.users.find_one({"username": username})


async def close_connection():
    global _client
    if _client:
        _client.close()
        _client = None
