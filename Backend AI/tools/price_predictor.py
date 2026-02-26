# tools/price_predictor.py
from typing import List, Dict

def predict_price(features: Dict) -> float:
    """
    Simple heuristic: return the average price of similar items
    """
    similar_prices: List[float] = features.get("similar_prices", [])
    if not similar_prices:
        return 0.0
    return round(sum(similar_prices) / len(similar_prices), 2)