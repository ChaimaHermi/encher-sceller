import uuid
from datetime import timedelta

from fastapi import APIRouter, HTTPException, Depends
from backend_api.database.mongo import get_users_collection
from backend_api.models.user_models import UserCreate, UserLogin, UserResponse, TokenResponse
from backend_api.core.auth import (
    hash_password,
    verify_password,
    create_token,
    get_current_user,
    ACCESS_TOKEN_EXPIRE_MINUTES,
)

router = APIRouter(prefix="/auth", tags=["Auth"])


@router.post("/register", response_model=TokenResponse)
async def register(data: UserCreate):
    coll = get_users_collection()
    if await coll.find_one({"email": data.email}):
        raise HTTPException(status_code=400, detail="Cet email est déjà utilisé")
    user_id = str(uuid.uuid4())
    doc = {
        "user_id": user_id,
        "email": data.email,
        "password_hash": hash_password(data.password),
        "role": data.role,
        "name": data.name or "",
    }
    await coll.insert_one(doc)
    token = create_token({"sub": user_id}, timedelta(minutes=ACCESS_TOKEN_EXPIRE_MINUTES))
    return TokenResponse(
        access_token=token,
        user=UserResponse(
            user_id=user_id,
            email=data.email,
            role=data.role,
            name=data.name or "",
        ),
    )


@router.post("/login", response_model=TokenResponse)
async def login(data: UserLogin):
    coll = get_users_collection()
    user = await coll.find_one({"email": data.email})
    if not user or not verify_password(data.password, user["password_hash"]):
        raise HTTPException(status_code=401, detail="Email ou mot de passe incorrect")
    token = create_token({"sub": user["user_id"]}, timedelta(minutes=ACCESS_TOKEN_EXPIRE_MINUTES))
    return TokenResponse(
        access_token=token,
        user=UserResponse(
            user_id=user["user_id"],
            email=user["email"],
            role=user["role"],
            name=user.get("name", ""),
        ),
    )


@router.get("/me", response_model=UserResponse)
async def me(user=Depends(get_current_user)):
    return UserResponse(
        user_id=user["user_id"],
        email=user["email"],
        role=user["role"],
        name=user.get("name", ""),
    )
