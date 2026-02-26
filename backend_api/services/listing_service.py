from datetime import datetime
from typing import List, Dict, Any
from backend_api.models.listing_models import ListingCreate, ImageModel, BlockchainModel
from backend_api.database.mongo import get_listings_collection


def build_listing_document(
    listing_id: str,
    images_data: List[Dict[str, str]],
    seller_id: str,
    title: str | None = None,
    category: str | None = None,
    description: str | None = None,
):
    images = [
        ImageModel(
            filename=img["filename"],
            original_name=img["original_name"],
            local_path=img["local_path"],
            mime_type=img["mime_type"],
            gridfs_file_id=img.get("gridfs_file_id"),
        )
        for img in images_data
    ]
    blockchain = BlockchainModel()
    listing = ListingCreate(
        listing_id=listing_id,
        seller_id=seller_id,
        images=images,
        title=title or None,
        category=category or None,
        description=description or None,
        created_at=datetime.utcnow(),
        updated_at=datetime.utcnow(),
        blockchain=blockchain
    )
    return listing.dict()


def _normalize_listing_images(doc: dict) -> None:
    if "image" in doc and "images" not in doc:
        doc["images"] = [doc.pop("image")]


def _strip_image_data(doc: dict) -> None:
    """Retire les données binaires des images avant envoi au client."""
    images = doc.get("images") or []
    for img in images:
        if isinstance(img, dict):
            img.pop("data", None)


async def get_listing_by_id(listing_id: str, strip_image_data: bool = True) -> Any:
    collection = get_listings_collection()
    listing = await collection.find_one({"listing_id": listing_id})
    if listing:
        listing.pop("_id", None)
        if "image" in listing and "images" not in listing:
            listing["images"] = [listing.pop("image")]
        if strip_image_data:
            _strip_image_data(listing)
    return listing


async def get_listings_for_buyer():
    coll = get_listings_collection()
    cursor = coll.find({"status": "AUCTION_ACTIVE"})
    items = []
    async for doc in cursor:
        doc.pop("_id", None)
        _normalize_listing_images(doc)
        doc.pop("price_estimation", None)
        doc.pop("ai_analysis", None)
        doc.pop("seller_id", None)
        doc.pop("generated_post", None)
        doc.pop("blockchain", None)
        doc.pop("pipeline_phase", None)
        _strip_image_data(doc)
        items.append(doc)
    return items


async def get_listings_by_seller(seller_id: str):
    coll = get_listings_collection()
    cursor = coll.find({"seller_id": seller_id}).sort("created_at", -1)
    items = []
    async for doc in cursor:
        doc.pop("_id", None)
        _normalize_listing_images(doc)
        _strip_image_data(doc)
        items.append(doc)
    return items
