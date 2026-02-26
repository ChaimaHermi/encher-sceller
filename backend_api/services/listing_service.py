from datetime import datetime
from typing import List, Dict, Any
from backend_api.models.listing_models import ListingCreate, ImageModel, BlockchainModel
from backend_api.database.mongo import get_listings_collection


def build_listing_document(
    listing_id: str,
    images_data: List[Dict[str, str]],
    seller_id: str,
):
    images = [
        ImageModel(
            filename=img["filename"],
            original_name=img["original_name"],
            local_path=img["local_path"],
            mime_type=img["mime_type"],
        )
        for img in images_data
    ]
    blockchain = BlockchainModel()
    listing = ListingCreate(
        listing_id=listing_id,
        seller_id=seller_id,
        images=images,
        created_at=datetime.utcnow(),
        updated_at=datetime.utcnow(),
        blockchain=blockchain
    )
    return listing.dict()


async def get_listing_by_id(listing_id: str) -> Any:
    collection = get_listings_collection()
    listing = await collection.find_one({"listing_id": listing_id})
    if listing:
        listing.pop("_id", None)
        # Rétrocompatibilité : image (singulier) -> images
        if "image" in listing and "images" not in listing:
            listing["images"] = [listing.pop("image")]
    return listing


def _normalize_listing_images(doc: dict) -> None:
    if "image" in doc and "images" not in doc:
        doc["images"] = [doc.pop("image")]


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
        items.append(doc)
    return items


async def get_listings_by_seller(seller_id: str):
    coll = get_listings_collection()
    cursor = coll.find({"seller_id": seller_id}).sort("created_at", -1)
    items = []
    async for doc in cursor:
        doc.pop("_id", None)
        _normalize_listing_images(doc)
        items.append(doc)
    return items
