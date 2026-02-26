import requests
from config.settings import AUCTION_API_URL, AUCTION_API_KEY


def post_to_auction(listing: dict) -> dict:
    headers = {
        "Authorization": f"Bearer {AUCTION_API_KEY}",
        "Content-Type": "application/json"
    }

    payload = {
        "title": listing["title"],
        "description": listing["description"],
        "condition": listing["condition"],
        "category": listing["category"],
        "tags": listing["tags"],
        "starting_price": 0,
        "auction_duration_days": 7
    }

    response = requests.post(
        f"{AUCTION_API_URL}/listings",
        json=payload,
        headers=headers
    )

    return response.json()