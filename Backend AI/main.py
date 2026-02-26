# main.py
from agents.vision_agent import VisionAgent
import json

if __name__ == "__main__":
    vision_agent = VisionAgent()

    images = [
        "images/dar1.0.jpg",
        "images/dar1.1.jpg",
        "images/dar1.2.jpg"
    ]

    description = """
s+1 haut standing a riadh el andalous
situé au 2ème étage avec ascenseur dans une résidence calme et bien sécurisée à Riadh el Andalous
 deux climatiseurs et un grand dressing dans la chambre à coucher La résidence est bien localisée, proche de toutes commodités
 
"""

    images1 = [
        "images/ford1.jpg",
        "images/ford2.jpg"
    ]

    description2 = """
Ford Fiesta
Mise en circulation 10/2014
130000 km
color Blue
Motorisation Essence
Boite Manuelle
Well maintained
No accidents
"""

    #result = vision_agent.run(images, description)
    result = vision_agent.run(images1, description2)

    print(json.dumps(result, indent=2, ensure_ascii=False))