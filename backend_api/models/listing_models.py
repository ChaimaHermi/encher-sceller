from pydantic import BaseModel
from datetime import datetime
from typing import Optional, Dict, List


class ImageModel(BaseModel):
    filename: str
    original_name: str
    local_path: str
    mime_type: str
    gridfs_file_id: Optional[str] = None  # ID MongoDB GridFS pour récupérer l'image


class BlockchainModel(BaseModel):
    auction_address: Optional[str] = None
    tx_hash: Optional[str] = None


class ListingCreate(BaseModel):
    listing_id: str
    seller_id: str
    images: List[ImageModel]
    status: str = "UPLOADED"
    pipeline_phase: int = 1
    created_at: datetime
    updated_at: datetime
    title: Optional[str] = None
    category: Optional[str] = None
    description: Optional[str] = None
    starting_price: Optional[float] = None
    participants_count: int = 0
    end_time: Optional[datetime] = None
    ai_analysis: Optional[Dict] = None
    price_estimation: Optional[Dict] = None
    generated_post: Optional[Dict] = None
    blockchain: BlockchainModel


class ListingResponse(BaseModel):
    listing_id: str
    seller_id: str
    images: List[ImageModel]
    status: str
    pipeline_phase: int
    created_at: datetime
    updated_at: datetime
    title: Optional[str] = None
    category: Optional[str] = None
    description: Optional[str] = None
    starting_price: Optional[float] = None
    participants_count: int = 0
    end_time: Optional[datetime] = None
    ai_analysis: Optional[Dict] = None
    price_estimation: Optional[Dict] = None
    generated_post: Optional[Dict] = None
    blockchain: BlockchainModel

    class Config:
        from_attributes = True


class ListingBuyerView(BaseModel):
    """Vue limitée pour acheteur : pas les offres, pas le prix de réserve."""
    listing_id: str
    images: List[ImageModel]
    title: Optional[str] = None
    starting_price: Optional[float] = None
    participants_count: int = 0
    end_time: Optional[datetime] = None
    status: str