from fastapi import APIRouter, Depends, HTTPException
from backend_api.database.mongo import get_listings_collection
from backend_api.services.listing_service import (
    get_listing_by_id,
    get_listings_for_buyer,
    get_listings_by_seller,
)
from backend_api.core.auth import get_current_user, require_seller, require_buyer

router = APIRouter(prefix="/listings", tags=["Listings"])


@router.get("/")
async def list_auctions(user=Depends(get_current_user)):
    """Liste des enchères selon le rôle."""
    if user["role"] == "buyer":
        return await get_listings_for_buyer()
    return await get_listings_by_seller(user["user_id"])


@router.get("/me")
async def my_listings(user=Depends(require_seller)):
    """Listings du vendeur connecté."""
    return await get_listings_by_seller(user["user_id"])


@router.get("/{listing_id}")
async def get_listing(listing_id: str, user=Depends(get_current_user)):
    """Détail d'un listing. Vue limitée pour acheteur (pas les offres)."""
    listing = await get_listing_by_id(listing_id)
    if not listing:
        raise HTTPException(status_code=404, detail="Listing introuvable")
    if user["role"] == "buyer":
        listing.pop("price_estimation", None)
        listing.pop("ai_analysis", None)
        listing.pop("seller_id", None)
        listing.pop("generated_post", None)
        listing.pop("blockchain", None)
    return listing
