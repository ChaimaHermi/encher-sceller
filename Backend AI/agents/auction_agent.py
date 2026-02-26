from agents.base_agent import BaseAgent
from tools.auction_client import post_to_auction


class AuctionAgent(BaseAgent):
    def __init__(self):
        super().__init__("auction_agent")

    def run(self, listing: dict) -> dict:
        return post_to_auction(listing)