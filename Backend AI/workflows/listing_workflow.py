from agents.vision_agent import VisionAgent
from agents.auction_agent import AuctionAgent


class ListingWorkflow:
    def __init__(self):
        self.vision = VisionAgent()
        self.auction = AuctionAgent()

    def run(self, image, description, publish=False):
        listing = self.vision.run(image, description)

        if "error" in listing:
            return listing

        if publish:
            result = self.auction.run(listing)
            return {"listing": listing, "auction_result": result}

        return listing