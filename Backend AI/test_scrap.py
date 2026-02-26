from agents.market_research_agent import MarketResearchAgent
import json

if __name__ == "__main__":
    agent = MarketResearchAgent()

    description = "ford fiesta Mise en circulation 10/2014 130000 km"
    images = ["images/ford1.jpg",
        "images/ford2.jpg"]  # optional local images

    result = agent.run(description, images)

    print(json.dumps(result, indent=2, ensure_ascii=False))