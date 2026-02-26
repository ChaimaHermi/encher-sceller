import os
import uuid
import shutil
import tempfile

from datetime import datetime, timedelta
from fastapi import APIRouter, UploadFile, File, Form, HTTPException, Depends, Body

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
    title: str = Form(""),
    category: str = Form(""),
    description: str = Form(""),
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

        # Lire le contenu pour sauvegarder en double (disque + MongoDB)
        file_content = await file.read()
        try:
            with open(file_path, "wb") as buffer:
                buffer.write(file_content)
        except Exception:
            for p in saved_paths:
                if os.path.exists(p):
                    os.remove(p)
            raise HTTPException(status_code=500, detail="Échec sauvegarde fichier")

        # Stocker l'image dans le document listing (BinData, pas de chunks GridFS)
        # Limite 10 Mo par image pour respecter la limite MongoDB 16 Mo/doc
        img_data = {
            "filename": new_filename,
            "original_name": file.filename,
            "local_path": file_path,
            "mime_type": file.content_type,
        }
        if len(file_content) <= 10 * 1024 * 1024:  # 10 Mo max
            img_data["data"] = file_content

        saved_paths.append(file_path)
        images_data.append(img_data)

    document = build_listing_document(
        listing_id=listing_id,
        images_data=images_data,
        seller_id=user["user_id"],
        title=title.strip() or None,
        category=category.strip() or None,
        description=description.strip() or None,
    )
    # Injecter les données binaires des images (non incluses dans ImageModel)
    for i, img in enumerate(images_data):
        if "data" in img:
            document["images"][i]["data"] = img["data"]

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


# --- Pipeline vendeur ---

@router.post("/listing/{listing_id}/analyze")
async def run_authenticity(listing_id: str, user=Depends(require_seller)):
    from backend_api.services.authenticity_service import run_authenticity_analysis

    coll = get_listings_collection()
    listing = await coll.find_one({"listing_id": listing_id, "seller_id": user["user_id"]})
    if not listing:
        raise HTTPException(404, "Listing introuvable")

    images = listing.get("images") or ([listing["image"]] if listing.get("image") else [])
    if not images:
        raise HTTPException(400, "Aucune image dans ce listing")
    first_img = images[0]

    # Récupérer l'image : priorité données dans le listing (MongoDB), sinon fichier local
    image_path = None
    temp_file_path = None

    image_bytes = first_img.get("data")
    if image_bytes:
        ext = first_img.get("filename", "image.jpg").split(".")[-1].lower() or "jpg"
        fd, temp_file_path = tempfile.mkstemp(suffix=f".{ext}", prefix="auth_")
        try:
            os.write(fd, image_bytes)
            os.close(fd)
            image_path = temp_file_path
        except Exception:
            if fd >= 0:
                try:
                    os.close(fd)
                except Exception:
                    pass
            if temp_file_path and os.path.exists(temp_file_path):
                os.remove(temp_file_path)
            raise HTTPException(500, "Impossible d'écrire l'image temporaire")

    if not image_path:
        # Fallback : fichier local (listings anciens)
        local_path = first_img.get("local_path")
        abs_path = os.path.abspath(local_path) if local_path else None
        if abs_path and os.path.isfile(abs_path):
            image_path = abs_path
        elif local_path and os.path.isfile(local_path):
            image_path = local_path

    if not image_path:
        raise HTTPException(400, "Image introuvable (ni dans MongoDB ni sur disque)")

    try:
        ai_result = await run_authenticity_analysis(
            image_path=image_path,
            category=listing.get("category") or listing.get("title"),
            description=listing.get("description") or (listing.get("generated_post", {}).get("description") if isinstance(listing.get("generated_post"), dict) else None),
        )
    except ValueError as e:
        raise HTTPException(400, str(e))
    except Exception as e:
        import logging
        logging.exception("Erreur analyse authenticité")
        raise HTTPException(500, f"Erreur analyse : {str(e)}")
    finally:
        if temp_file_path and os.path.exists(temp_file_path):
            try:
                os.remove(temp_file_path)
            except Exception:
                pass

    await coll.update_one(
        {"listing_id": listing_id},
        {"$set": {
            "pipeline_phase": 2,
            "status": "AUTHENTICATED",
            "ai_analysis": ai_result,
            "updated_at": datetime.utcnow(),
        }}
    )
    return {"message": "Vérification authenticité terminée", "phase": 2, "ai_analysis": ai_result}


@router.post("/listing/{listing_id}/estimate")
async def run_pricing(listing_id: str, user=Depends(require_seller)):
    import asyncio
    from backend_ai.agents.recommandation_prix_agent import RecommandationPrixAgent

    coll = get_listings_collection()
    listing = await coll.find_one({"listing_id": listing_id, "seller_id": user["user_id"]})
    if not listing:
        raise HTTPException(404, "Listing introuvable")

    # Récupérer le(s) chemin(s) des images (MongoDB data ou fichier local)
    image_paths = []
    images = listing.get("images") or ([listing["image"]] if listing.get("image") else [])
    temp_files = []
    for img in images[:3]:
        path = None
        if img.get("data"):
            ext = img.get("filename", "image.jpg").split(".")[-1].lower() or "jpg"
            fd, tmp = tempfile.mkstemp(suffix=f".{ext}", prefix="price_")
            try:
                os.write(fd, img["data"])
                os.close(fd)
                path = tmp
                temp_files.append(tmp)
            except Exception:
                if fd >= 0:
                    try:
                        os.close(fd)
                    except Exception:
                        pass
        if not path:
            local = img.get("local_path")
            if local and os.path.isfile(local):
                path = local
            elif local and os.path.isfile(os.path.abspath(local)):
                path = os.path.abspath(local)
        if path:
            image_paths.append(path)

    def _run():
        agent = RecommandationPrixAgent()
        return agent.run(
            title=listing.get("title") or "Objet",
            category=listing.get("category"),
            description=listing.get("description"),
            image_paths=image_paths if image_paths else None,
        )

    try:
        loop = asyncio.get_event_loop()
        price_result = await loop.run_in_executor(None, _run)
    except ValueError as e:
        for t in temp_files:
            if os.path.exists(t):
                try:
                    os.remove(t)
                except Exception:
                    pass
        raise HTTPException(400, str(e))
    except Exception as e:
        import logging
        logging.exception("Erreur estimation prix")
        price_result = {"low": 50, "median": 100, "high": 200, "starting_price": 75, "reasoning": str(e)}
    finally:
        for t in temp_files:
            if os.path.exists(t):
                try:
                    os.remove(t)
                except Exception:
                    pass

    starting = price_result.get("starting_price", price_result.get("median", 100))
    price_estimation = {
        "low": price_result.get("low", starting * 0.6),
        "median": price_result.get("median", starting),
        "high": price_result.get("high", starting * 1.5),
        "reasoning": price_result.get("reasoning", ""),
    }

    await coll.update_one(
        {"listing_id": listing_id},
        {"$set": {
            "pipeline_phase": 3,
            "status": "PRICED",
            "starting_price": float(starting),
            "price_estimation": price_estimation,
            "updated_at": datetime.utcnow(),
        }}
    )
    return {
        "message": "Estimation prix terminée",
        "phase": 3,
        "starting_price": float(starting),
        "price_estimation": price_estimation,
    }


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