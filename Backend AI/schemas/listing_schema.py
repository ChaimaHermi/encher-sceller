from pydantic import BaseModel
from typing import List


class AuctionListing(BaseModel):
    title: str
    description: str
    condition: str
    category: str
    tags: List[str]
    price_range: str