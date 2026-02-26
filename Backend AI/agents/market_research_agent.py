# agents/market_research_agent.py
from agents.base_agent import BaseAgent
from tools.web_scraper import search_similar_items
from tools.price_predictor import predict_price
from typing import List, Dict, Union

class MarketResearchAgent(BaseAgent):
    def __init__(self):
        super().__init__("market_research_agent")

    def run(self, product_description: str, images: Union[str, List[str]] = None) -> Dict:
        # 1. Search web for similar items
        similar_items = search_similar_items(product_description, images)

        # 2. Extract prices
        prices = [item["price"] for item in similar_items if "price" in item]

        # 3. Predict price
        predicted_price = predict_price({"similar_prices": prices})

        return {
            "product_description": product_description,
            "similar_items": similar_items,
            "predicted_price": predicted_price
        }