# verifier_tools/clip_matcher.py

from PIL import Image, UnidentifiedImageError
import torch
import clip
from dataclasses import dataclass
from typing import Optional
import logging

logger = logging.getLogger(__name__)


@dataclass
class CLIPMatchResult:
    """
    Result of CLIP semantic matching between image and text description.

    image_text_score     : float → cosine similarity between image and full description [0.0, 1.0]
    category_score       : float → cosine similarity between image and category alone [0.0, 1.0]
    combined_score       : float → weighted combination of both scores [0.0, 1.0]
    verdict              : str   → "consistent" | "suspicious" | "mismatch"
    suspicion_score      : float → 0.0 (consistent) to 1.0 (total mismatch), for agent pipeline
    notes                : str   → human-readable explanation
    top_category_matches : list  → ranked similarity of image against all provided categories
    """
    image_text_score: float
    category_score: float
    combined_score: float
    verdict: str
    suspicion_score: float
    notes: str
    top_category_matches: list[dict]


class CLIPMatcher:
    """
    Semantic consistency checker using OpenAI CLIP.

    Verifies that the uploaded image actually matches:
      1. The product category the user selected
      2. The product description the user wrote

    If someone uploads a photo of a car engine but lists it as
    a "vintage watch", CLIP will catch the mismatch.

    Model: ViT-B/32 (default) — good balance of speed and accuracy.
    Runs fully locally, no API needed, completely free.
    """

    # Candidate categories for cross-comparison
    # Used to detect if image better matches a different category
    DEFAULT_CATEGORIES = [
        "watch", "jewelry", "electronics", "clothing", "shoes",
        "handbag", "furniture", "artwork", "collectible", "sports equipment",
        "camera", "musical instrument", "book", "toy", "vehicle",
        "phone", "computer", "kitchen appliance", "antique", "coin",
    ]

    def __init__(
        self,
        model_name: str = "ViT-B/32",
        suspicious_threshold: float = 0.20,   # combined_score below this → suspicious
        mismatch_threshold: float = 0.12,     # combined_score below this → mismatch
        category_weight: float = 0.4,         # weight of category score in combined
        description_weight: float = 0.6,      # weight of description score in combined
        device: Optional[str] = None,
        extra_categories: Optional[list[str]] = None,
    ):
        self.suspicious_threshold = suspicious_threshold
        self.mismatch_threshold = mismatch_threshold
        self.category_weight = category_weight
        self.description_weight = description_weight

        # Device setup
        if device:
            self.device = device
        elif torch.cuda.is_available():
            self.device = "cuda"
        elif torch.backends.mps.is_available():
            self.device = "mps"
        else:
            self.device = "cpu"

        logger.info(f"CLIPMatcher using device: {self.device}")
        logger.info(f"Loading CLIP model: {model_name}")

        self.model, self.preprocess = clip.load(model_name, device=self.device)
        self.model.eval()

        # Build candidate category list
        self.candidate_categories = self.DEFAULT_CATEGORIES.copy()
        if extra_categories:
            self.candidate_categories.extend(extra_categories)

    def _load_image(self, image_path: str) -> torch.Tensor:
        """Load, preprocess, and move image to device tensor."""
        try:
            img = Image.open(image_path).convert("RGB")
            return self.preprocess(img).unsqueeze(0).to(self.device)
        except FileNotFoundError:
            raise FileNotFoundError(f"Image not found: {image_path}")
        except UnidentifiedImageError:
            raise ValueError(f"Cannot read image file: {image_path}")

    def _encode_texts(self, texts: list[str]) -> torch.Tensor:
        """Tokenize and encode a list of text strings."""
        tokens = clip.tokenize(texts, truncate=True).to(self.device)
        with torch.no_grad():
            return self.model.encode_text(tokens)

    def _encode_image(self, image_tensor: torch.Tensor) -> torch.Tensor:
        """Encode preprocessed image tensor."""
        with torch.no_grad():
            return self.model.encode_image(image_tensor)

    def _cosine_similarity(
        self, vec_a: torch.Tensor, vec_b: torch.Tensor
    ) -> float:
        """Compute cosine similarity between two embedding vectors."""
        vec_a = vec_a / vec_a.norm(dim=-1, keepdim=True)
        vec_b = vec_b / vec_b.norm(dim=-1, keepdim=True)
        return float((vec_a @ vec_b.T).squeeze())

    def _build_description_prompt(
        self, category: str, product_info: Optional[str]
    ) -> str:
        """
        Construct a natural language prompt from user inputs.
        CLIP performs better with full sentences than raw keywords.
        Handles None product_info.
        """
        if product_info is None or not str(product_info).strip():
            return f"a photo of a {category}"
        return f"a photo of a {category}: {product_info}"

    def _rank_categories(
        self,
        image_features: torch.Tensor,
        user_category: str,
    ) -> list[dict]:
        """
        Rank all candidate categories by similarity to the image.
        Includes user's stated category for reference.
        """
        # Ensure user category is in the list
        categories = list(set(self.candidate_categories + [user_category.lower()]))
        prompts = [f"a photo of a {cat}" for cat in categories]

        text_features = self._encode_texts(prompts)

        # Normalize and compute similarities
        image_norm = image_features / image_features.norm(dim=-1, keepdim=True)
        text_norm = text_features / text_features.norm(dim=-1, keepdim=True)
        similarities = (image_norm @ text_norm.T).squeeze().tolist()

        if isinstance(similarities, float):
            similarities = [similarities]

        ranked = sorted(
            [
                {"category": cat, "score": round(sim, 6)}
                for cat, sim in zip(categories, similarities)
            ],
            key=lambda x: x["score"],
            reverse=True,
        )
        return ranked

    def analyze(
        self,
        image_path: str,
        category: str,
        product_info: Optional[str] = None,
    ) -> CLIPMatchResult:
        """
        Check semantic consistency between image, category, and product description.

        Args:
            image_path   : path to uploaded product image
            category     : user-selected product category (e.g. "watch", "handbag")
            product_info : user-written product description (e.g. "1965 Rolex Submariner, stainless steel")

        Returns CLIPMatchResult with scores, verdict, and category ranking.
        """
        logger.info(
            f"Running CLIP matching | image={image_path} | "
            f"category='{category}' | info='{product_info[:60]}...'"
        )

        image_tensor = self._load_image(image_path)
        image_features = self._encode_image(image_tensor)

        # Score 1: image vs full description prompt
        description_prompt = self._build_description_prompt(category, product_info)
        desc_features = self._encode_texts([description_prompt])
        image_text_score = self._cosine_similarity(image_features, desc_features)

        # Score 2: image vs category alone
        category_prompt = f"a photo of a {category}"
        cat_features = self._encode_texts([category_prompt])
        category_score = self._cosine_similarity(image_features, cat_features)

        # If no description, rely only on category score for combined
        if product_info is None or not str(product_info).strip():
            combined_score = category_score
        else:
            combined_score = (
                self.description_weight * image_text_score
                + self.category_weight * category_score
            )

        # (moved above: combined_score now handles missing description)

        # Rank image against all candidate categories
        top_category_matches = self._rank_categories(image_features, category)

        # Check if user's category is actually the top match
        top_match = top_category_matches[0]["category"].lower()
        user_cat_rank = next(
            (i + 1 for i, r in enumerate(top_category_matches)
             if r["category"].lower() == category.lower()),
            None,
        )

        # Build verdict and notes
        notes_parts = []

        if combined_score < self.mismatch_threshold:
            verdict = "mismatch"
            suspicion_score = 1.0
            notes_parts.append(
                f"Image does not match the stated category '{category}' or description. "
                f"Combined similarity score is very low ({combined_score:.3f})."
            )
        elif combined_score < self.suspicious_threshold:
            verdict = "suspicious"
            suspicion_score = round(
                1.0 - (combined_score / self.suspicious_threshold), 4
            )
            notes_parts.append(
                f"Weak semantic match between image and description "
                f"(score: {combined_score:.3f}). Manual review recommended."
            )
        else:
            verdict = "consistent"
            suspicion_score = round(
                max(0.0, 1.0 - (combined_score / 0.35)), 4
            )
            notes_parts.append(
                f"Image is semantically consistent with category '{category}' "
                f"and provided description (score: {combined_score:.3f})."
            )

        # Flag if image matches a completely different category better
        if (
            top_match != category.lower()
            and top_category_matches[0]["score"] > category_score + 0.05
        ):
            notes_parts.append(
                f"Image appears to better match '{top_match}' "
                f"(score: {top_category_matches[0]['score']:.3f}) "
                f"than stated category '{category}' "
                f"(rank: #{user_cat_rank})."
            )
            if verdict == "consistent":
                verdict = "suspicious"
                suspicion_score = max(suspicion_score, 0.5)

        result = CLIPMatchResult(
            image_text_score=round(image_text_score, 6),
            category_score=round(category_score, 6),
            combined_score=round(combined_score, 6),
            verdict=verdict,
            suspicion_score=round(suspicion_score, 6),
            notes=" | ".join(notes_parts),
            top_category_matches=top_category_matches[:5],  # top 5 only
        )

        logger.info(
            f"CLIP result → verdict={verdict}, combined={combined_score:.4f}, "
            f"desc={image_text_score:.4f}, cat={category_score:.4f}"
        )
        return result


# ----------------------------------------
# Example usage
if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)

    matcher = CLIPMatcher(
        suspicious_threshold=0.20,
        mismatch_threshold=0.12,
    )

    result = matcher.analyze(
        image_path="test_watch.jpeg",
        category="watch",
        product_info="1965 Rolex Submariner stainless steel black dial, ref 5513",
    )

    print(f"\n--- CLIP Match Report ---")
    print(f"Verdict              : {result.verdict}")
    print(f"Suspicion Score      : {result.suspicion_score:.4f}")
    print(f"Image-Text Score     : {result.image_text_score:.4f}")
    print(f"Category Score       : {result.category_score:.4f}")
    print(f"Combined Score       : {result.combined_score:.4f}")
    print(f"Notes                : {result.notes}")
    print(f"\nTop Category Matches :")
    for match in result.top_category_matches:
        marker = " ← user stated" if match["category"] == "watch" else ""
        print(f"  {match['category']:<25} {match['score']:.4f}{marker}")