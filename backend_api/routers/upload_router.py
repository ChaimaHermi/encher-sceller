import os
import uuid
import shutil

from datetime import datetime, timedelta
from fastapi import APIRouter, UploadFile, File, HTTPException, Depends, Body

from backend_api.database.mongo import get_listings_collection
from backend_api.services.listing_service import build_listing_document, get_listing_by_id
from backend_api.models.listing_models import ListingResponse
from backend_api.core.auth import require_seller, require_buyer, get_current_user


router = APIRouter()

UPLOAD_FOLDER = "uploads"
os.makedirs(UPLOAD_FOLDER, exist_ok=True)


# --------------------------------------------------
# 📌 POST - Upload Images (1 ou plusieurs)
# --------------------------------------------------
@router.post(
    "/upload",
    summary="Upload une ou plusieurs images produit (vendeur)"
)
async def upload_images(
    files: list[UploadFile] = File(...),
    user=Depends(require_seller),
):
    if not files:
        raise HTTPException(status_code=400, detail="Au moins une image requise")

    listing_id = str(uuid.uuid4())
    images_data = []
    saved_paths = []

    for i, file in enumerate(files):
        if not file.content_type or not file.content_type.startswith("image/"):
            for p in saved_paths:
                if os.path.exists(p):
                    os.remove(p)
            raise HTTPException(status_code=400, detail=f"Fichier invalide : {file.filename} doit être une image")

        ext = file.filename.split(".")[-1].lower() if "." in file.filename else "jpg"
        new_filename = f"{listing_id}-{i}.{ext}"
        file_path = os.path.join(UPLOAD_FOLDER, new_filename)

        try:
            with open(file_path, "wb") as buffer:
                shutil.copyfileobj(file.file, buffer)
        except Exception:
            for p in saved_paths:
                if os.path.exists(p):
                    os.remove(p)
            raise HTTPException(status_code=500, detail="Échec sauvegarde fichier")

        saved_paths.append(file_path)
        images_data.append({
            "filename": new_filename,
            "original_name": file.filename,
            "local_path": file_path,
            "mime_type": file.content_type,
        })

    document = build_listing_document(
        listing_id=listing_id,
        images_data=images_data,
        seller_id=user["user_id"],
    )

    try:
        await get_listings_collection().insert_one(document)
    except Exception:
        for p in saved_paths:
            if os.path.exists(p):
                os.remove(p)
        raise HTTPException(status_code=500, detail="Échec insertion base de données")

    return {"listing_id": listing_id, "message": "Annonce créée avec succès"}


# --------------------------------------------------
# 📌 GET - Retrieve Listing by ID
# --------------------------------------------------
@router.get(
    "/listing/{listing_id}",
    summary="Get listing by ID (auth requise)"
)
async def fetch_listing(
    listing_id: str,
    user=Depends(get_current_user),
):
    listing = await get_listing_by_id(listing_id)
    if not listing:
        raise HTTPException(status_code=404, detail="Listing not found")
    if user["role"] == "buyer":
        listing.pop("price_estimation", None)
        listing.pop("ai_analysis", None)
        listing.pop("seller_id", None)
        listing.pop("generated_post", None)
        listing.pop("blockchain", None)
        listing.pop("pipeline_phase", None)  # Acheteur ne voit pas le pipeline
    return listing


# --- Pipeline vendeur (mock pour démo) ---

@router.post("/listing/{listing_id}/analyze")
async def run_authenticity(listing_id: str, user=Depends(require_seller)):
    coll = get_listings_collection()
    listing = await coll.find_one({"listing_id": listing_id, "seller_id": user["user_id"]})
    if not listing:
        raise HTTPException(404, "Listing introuvable")
    await coll.update_one(
        {"listing_id": listing_id},
        {"$set": {
            "pipeline_phase": 2,
            "status": "AUTHENTICATED",
            "ai_analysis": {"score": 87, "verdict": "Authentique", "details": "Analyse IA simulée"},
            "updated_at": datetime.utcnow(),
        }}
    )
    return {"message": "Vérification authenticité terminée", "phase": 2}


@router.post("/listing/{listing_id}/estimate")
async def run_pricing(listing_id: str, user=Depends(require_seller)):
    coll = get_listings_collection()
    listing = await coll.find_one({"listing_id": listing_id, "seller_id": user["user_id"]})
    if not listing:
        raise HTTPException(404, "Listing introuvable")
    await coll.update_one(
        {"listing_id": listing_id},
        {"$set": {
            "pipeline_phase": 3,
            "status": "PRICED",
            "starting_price": 150.0,
            "price_estimation": {"low": 100, "median": 150, "high": 200},
            "updated_at": datetime.utcnow(),
        }}
    )
    return {"message": "Estimation prix terminée", "phase": 3, "starting_price": 150}


@router.post("/listing/{listing_id}/generate")
async def run_post_gen(listing_id: str, user=Depends(require_seller)):
    coll = get_listings_collection()
    listing = await coll.find_one({"listing_id": listing_id, "seller_id": user["user_id"]})
    if not listing:
        raise HTTPException(404, "Listing introuvable")
    await coll.update_one(
        {"listing_id": listing_id},
        {"$set": {
            "pipeline_phase": 4,
            "status": "POSTED",
            "title": "Objet d'art - Titre généré par IA",
            "generated_post": {"title": "...", "description": "..."},
            "updated_at": datetime.utcnow(),
        }}
    )
    return {"message": "Post généré", "phase": 4}


@router.post("/listing/{listing_id}/deploy")
async def deploy_auction(listing_id: str, user=Depends(require_seller)):
    coll = get_listings_collection()
    listing = await coll.find_one({"listing_id": listing_id, "seller_id": user["user_id"]})
    if not listing:
        raise HTTPException(404, "Listing introuvable")
    end_time = datetime.utcnow() + timedelta(days=7)
    await coll.update_one(
        {"listing_id": listing_id},
        {"$set": {
            "pipeline_phase": 5,
            "status": "AUCTION_ACTIVE",
            "participants_count": 0,
            "end_time": end_time,
            "blockchain": {"auction_address": f"0x{listing_id[:40]}", "tx_hash": "0x..."},
            "updated_at": datetime.utcnow(),
        }}
    )
    return {"message": "Enchère lancée", "phase": 5, "end_time": end_time.isoformat()}


# --- Enchère : acheteur propose un prix (scellé, pas visible par les autres) ---

@router.post("/listing/{listing_id}/bid")
async def place_bid(
    listing_id: str,
    body: dict = Body(...),
    user=Depends(require_buyer),
):
    from backend_api.database.mongo import get_bids_collection
    amount = body.get("amount")
    if amount is None or not isinstance(amount, (int, float)) or amount <= 0:
        raise HTTPException(400, "Montant invalide")
    amount = float(amount)
    coll_listings = get_listings_collection()
    listing = await coll_listings.find_one({"listing_id": listing_id, "status": "AUCTION_ACTIVE"})
    if not listing:
        raise HTTPException(404, "Enchère introuvable ou terminée")
    min_price = listing.get("starting_price") or 0
    if amount < min_price:
        raise HTTPException(400, f"Le montant doit être au moins {min_price} €")
    bids_coll = get_bids_collection()
    await bids_coll.insert_one({
        "listing_id": listing_id,
        "user_id": user["user_id"],
        "amount": amount,
        "created_at": datetime.utcnow(),
    })
    distinct_bidders = await bids_coll.distinct("user_id", {"listing_id": listing_id})
    await coll_listings.update_one(
        {"listing_id": listing_id},
        {"$set": {"participants_count": len(distinct_bidders), "updated_at": datetime.utcnow()}}
    )
    return {"message": "Offre enregistrée (scellée)", "participants": len(distinct_bidders)}