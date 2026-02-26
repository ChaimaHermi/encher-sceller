"""
Agent de recommandation de prix — utilise Gemini pour estimer un prix de vente
basé sur le titre, la catégorie, la description et les images du produit.
"""

import os
import json
import re
from typing import Optional, Union

from google import genai
from google.genai.types import Part
from dotenv import load_dotenv

load_dotenv()


PRICE_RECOMMENDATION_PROMPT = """Tu es un expert en estimation de prix pour une plateforme d'enchères scellées (objets d'art, antiquités, collection).

Tu dois recommander une fourchette de prix (en euros) pour le produit décrit et représenté ci-dessous.

=== INFORMATIONS DU PRODUIT ===
**Titre:** {title}
**Catégorie:** {category}
**Description:** {description}

=== IMAGE(S) ===
{image_instruction}

=== INSTRUCTIONS ===
1. Analyse les informations fournies (titre, catégorie, description).
2. Examine attentivement l'image (ou les images) du produit : qualité, matériaux visibles, état, rareté, signes distinctifs.
3. Recommande une fourchette de prix réaliste en euros pour le marché français/européen.
4. Réponds UNIQUEMENT avec un objet JSON valide, sans texte avant ou après :

{{
  "low": <prix minimum en euros (nombre)>,
  "median": <prix médian suggéré en euros (nombre)>,
  "high": <prix maximum en euros (nombre)>,
  "starting_price": <prix de départ suggéré pour l'enchère, entre low et median>,
  "reasoning": "<court raisonnement expliquant l'estimation en 1-3 phrases>"
}}

Exemple de réponse :
{{"low": 80, "median": 120, "high": 180, "starting_price": 90, "reasoning": "Objet courant, marché actif, état correct visible sur l'image."}}
"""


class RecommandationPrixAgent:
    """Agent utilisant Gemini pour recommander un prix de vente (description, catégorie, images)."""

    def __init__(self, gemini_api_key: Optional[str] = None):
        key = gemini_api_key or os.getenv("GEMINI_API_KEY")
        if not key:
            raise ValueError("GEMINI_API_KEY manquant : configurez-le dans .env")
        self.client = genai.Client(api_key=key)

    def run(
        self,
        title: str,
        category: Optional[str] = None,
        description: Optional[str] = None,
        image_paths: Optional[Union[str, list[str]]] = None,
    ) -> dict:
        """
        Génère une recommandation de prix pour un produit.

        Args:
            title: Titre du produit
            category: Catégorie du produit
            description: Description détaillée
            image_paths: Chemin(s) vers l'image ou les images du produit (optionnel)

        Returns:
            Dict avec low, median, high, starting_price, reasoning
        """
        if isinstance(image_paths, str):
            image_paths = [image_paths] if image_paths else []
        elif not image_paths:
            image_paths = []

        # Chemins valides existants
        valid_paths = [p for p in image_paths if p and os.path.isfile(p)]

        if valid_paths:
            image_instruction = f"Voir {len(valid_paths)} image(s) jointe(s) du produit — analyse-les pour l'estimation."
        else:
            image_instruction = "Aucune image fournie — base ton estimation sur le titre, la catégorie et la description uniquement."

        prompt = PRICE_RECOMMENDATION_PROMPT.format(
            title=title or "Non spécifié",
            category=category or "Non spécifié",
            description=description or "Aucune description.",
            image_instruction=image_instruction,
        )

        # Construire le contenu : prompt + images (multimodal)
        contents = [prompt]
        mime_map = {
            ".jpg": "image/jpeg", ".jpeg": "image/jpeg", ".jfif": "image/jpeg",
            ".png": "image/png", ".webp": "image/webp", ".gif": "image/gif",
        }
        for path in valid_paths[:3]:  # max 3 images pour éviter la limite
            try:
                with open(path, "rb") as f:
                    data = f.read()
                ext = os.path.splitext(path)[1].lower() or ".jpg"
                mime = mime_map.get(ext, "image/jpeg")
                contents.append(Part.from_bytes(data=data, mime_type=mime))
            except Exception:
                pass

        response = self.client.models.generate_content(
            model="gemini-2.5-flash",
            contents=contents,
        )
        text = (response.text or "").strip()

        # Extraire le JSON de la réponse (parfois entouré de markdown)
        parsed = self._parse_json_response(text)
        if not parsed:
            return {
                "low": 50,
                "median": 100,
                "high": 200,
                "starting_price": 75,
                "reasoning": "Impossible de parser la réponse Gemini. Valeurs par défaut appliquées.",
            }

        # S'assurer que les champs numériques sont des floats
        for key in ("low", "median", "high", "starting_price"):
            if key in parsed and parsed[key] is not None:
                try:
                    parsed[key] = float(parsed[key])
                except (TypeError, ValueError):
                    parsed[key] = 100.0
            else:
                parsed[key] = 100.0

        return parsed

    def _parse_json_response(self, text: str) -> Optional[dict]:
        """Extrait un objet JSON de la réponse texte."""
        text = text.strip()
        json_match = re.search(r"```(?:json)?\s*(\{[\s\S]*?\})\s*```", text)
        if json_match:
            try:
                return json.loads(json_match.group(1))
            except json.JSONDecodeError:
                pass

        try:
            return json.loads(text)
        except json.JSONDecodeError:
            pass

        brace_match = re.search(r"\{[^{}]*(?:\{[^{}]*\}[^{}]*)*\}", text)
        if brace_match:
            try:
                return json.loads(brace_match.group(0))
            except json.JSONDecodeError:
                pass

        return None


# --- Exécution en ligne de commande ---
if __name__ == "__main__":
    import sys

    agent = RecommandationPrixAgent()
    title = sys.argv[1] if len(sys.argv) > 1 else "Tableau huile sur toile 50x60 cm"
    category = sys.argv[2] if len(sys.argv) > 2 else "Art"
    description = sys.argv[3] if len(sys.argv) > 3 else "Peinture à l'huile, signée, cadre ancien."
    image_path = sys.argv[4] if len(sys.argv) > 4 else None

    result = agent.run(
        title=title,
        category=category,
        description=description,
        image_paths=image_path,
    )
    print(json.dumps(result, indent=2, ensure_ascii=False))
