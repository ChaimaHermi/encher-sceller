from datetime import datetime
from backend_api.models.listing_models import ListingCreate, ImageModel, BlockchainModel


def build_listing_document(
    listing_id: str,
    filename: str,
    original_name: str,
    local_path: str,
    mime_type: str,
    seller_id: str,
):

    image = ImageModel(
        filename=filename,
        original_name=original_name,
        local_path=local_path,
        mime_type=mime_type
    )

    blockchain = BlockchainModel()

    listing = ListingCreate(
        listing_id=listing_id,
        seller_id=seller_id,
        image=image,
        created_at=datetime.utcnow(),
        updated_at=datetime.utcnow(),
        blockchain=blockchain
    )

    return listing.dict()


from backend_api.database.mongo import get_listings_collection


async def get_listing_by_id(listing_id: str):
    collection = get_listings_collection()
    listing = await collection.find_one({"listing_id": listing_id})
    if listing:
        listing.pop("_id", None)
    return listing


async def get_listings_for_buyer():
    """Enchères actives uniquement — l'acheteur ne voit pas le pipeline."""
    coll = get_listings_collection()
    cursor = coll.find({"status": "AUCTION_ACTIVE"})
    items = []
    async for doc in cursor:
        doc.pop("_id", None)
        doc.pop("price_estimation", None)
        doc.pop("ai_analysis", None)
        doc.pop("seller_id", None)
        doc.pop("generated_post", None)
        doc.pop("blockchain", None)
        doc.pop("pipeline_phase", None)  # Acheteur ne voit pas le pipeline
        items.append(doc)
    return items


async def get_listings_by_seller(seller_id: str):
    coll = get_listings_collection()
    cursor = coll.find({"seller_id": seller_id}).sort("created_at", -1)
    items = []
    async for doc in cursor:
        doc.pop("_id", None)
        items.append(doc)
    return items