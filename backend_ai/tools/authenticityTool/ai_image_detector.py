# verifier_tools/ai_image_detector.py

from PIL import Image, UnidentifiedImageError
import torch
from transformers import AutoModelForImageClassification, AutoImageProcessor
from dataclasses import dataclass
from typing import Optional
import logging

logger = logging.getLogger(__name__)

# Best free HuggingFace models specifically fine-tuned for AI-generated image detection
MODELS = {
    "umm-maybe": "umm-maybe/AI-image-detector",   # Artistic/creative images
    "sdxl":      "Organika/sdxl-detector",        # General/photographic images
}
@dataclass
class AIDetectionResult:
    """
    Result of AI-generated image detection.

    is_ai_generated  : bool   → True if model believes image is AI-generated
    ai_probability   : float  → confidence the image is AI-generated [0.0, 1.0]
    real_probability : float  → confidence the image is real [0.0, 1.0]
    verdict          : str    → "real" | "suspicious" | "ai_generated"
    suspicion_score  : float  → normalized score for use in agent pipeline [0.0, 1.0]
    notes            : str    → human-readable explanation
    """
    is_ai_generated: bool
    ai_probability: float
    real_probability: float
    verdict: str
    suspicion_score: float
    notes: str


class AIImageDetector:
    """
    Detects AI-generated images using a ViT model fine-tuned on
    real vs AI-generated image datasets (SD, DALL-E, MidJourney etc).

    Model: umm-maybe/AI-image-detector (HuggingFace)
    - Fine-tuned ViT-base-patch16-224
    - Trained on CIFAKE dataset + augmented AI-generated samples
    - Binary classifier: real vs fake
    - Completely free, runs locally, no API needed

    Device priority: CUDA → MPS (Apple Silicon) → CPU
    """

    def __init__(
        self,
        model_type: str = "umm-maybe",  # 'umm-maybe' or 'sdxl'
        suspicious_threshold: float = 0.45,   # above this → suspicious
        ai_threshold: float = 0.75,           # above this → ai_generated
        device: Optional[str] = None,         # auto-detect if None
    ):
        if model_type not in MODELS:
            raise ValueError(f"Unknown model_type '{model_type}'. Choose from: {list(MODELS.keys())}")
        self.model_type = model_type
        self.model_id = MODELS[model_type]
        self.suspicious_threshold = suspicious_threshold
        self.ai_threshold = ai_threshold

        # Auto-detect best available device
        if device:
            self.device = device
        elif torch.cuda.is_available():
            self.device = "cuda"
        elif torch.backends.mps.is_available():
            self.device = "mps"
        else:
            self.device = "cpu"

        logger.info(f"AIImageDetector using device: {self.device}")
        logger.info(f"Loading model: {self.model_id}")

        self.processor = AutoImageProcessor.from_pretrained(self.model_id)
        self.model = AutoModelForImageClassification.from_pretrained(self.model_id, torch_dtype="auto")
        self.model.to(self.device)
        self.model.eval()

        # Resolve label mapping from model config
        self.id2label = self.model.config.id2label
        logger.info(f"Model labels: {self.id2label}")

    def _load_image(self, image_path: str) -> Image.Image:
        """Load and validate image."""
        try:
            img = Image.open(image_path).convert("RGB")
            return img
        except FileNotFoundError:
            raise FileNotFoundError(f"Image not found: {image_path}")
        except UnidentifiedImageError:
            raise ValueError(f"Cannot read image file: {image_path}")

    def _get_label_probs(self, logits: torch.Tensor) -> dict[str, float]:
        """Convert raw logits to label-probability mapping."""
        probs = torch.softmax(logits, dim=-1).squeeze().tolist()

        if isinstance(probs, float):
            probs = [probs]

        return {
            self.id2label[i]: round(probs[i], 6)
            for i in range(len(probs))
        }

    def _find_ai_prob(self, label_probs: dict[str, float]) -> tuple[float, float]:
        """
        Extract AI-generated and real probabilities from label map.
        Handles different label naming conventions across models.
        Returns (ai_prob, real_prob).
        """
        ai_keys = {"artificial", "fake", "ai", "generated", "1"}
        real_keys = {"human", "real", "authentic", "0"}

        ai_prob = 0.0
        real_prob = 0.0

        for label, prob in label_probs.items():
            if label.lower() in ai_keys:
                ai_prob = prob
            elif label.lower() in real_keys:
                real_prob = prob

        # Fallback: if label names are numeric strings
        if ai_prob == 0.0 and real_prob == 0.0:
            values = list(label_probs.values())
            if len(values) == 2:
                real_prob, ai_prob = values[0], values[1]

        return ai_prob, real_prob

    def analyze(self, image_path: str) -> AIDetectionResult:
        """
        Run AI-generated image detection on the given image.
        Returns AIDetectionResult with probabilities, verdict, and suspicion score.
        """
        logger.info(f"Running AI image detection on: {image_path}")

        img = self._load_image(image_path)

        # Preprocess and run inference
        inputs = self.processor(images=img, return_tensors="pt")
        inputs = {k: v.to(self.device) for k, v in inputs.items()}

        with torch.no_grad():
            outputs = self.model(**inputs)

        label_probs = self._get_label_probs(outputs.logits)
        ai_prob, real_prob = self._find_ai_prob(label_probs)

        # Determine verdict
        if ai_prob >= self.ai_threshold:
            verdict = "ai_generated"
            is_ai = True
            notes = (
                f"Model is {ai_prob:.1%} confident this image is AI-generated. "
                f"Likely produced by Stable Diffusion, DALL-E, or similar."
            )
        elif ai_prob >= self.suspicious_threshold:
            verdict = "suspicious"
            is_ai = False
            notes = (
                f"Image shows some AI-generation signatures ({ai_prob:.1%} confidence). "
                f"Recommend additional manual review or EXIF/ELA cross-check."
            )
        else:
            verdict = "real"
            is_ai = False
            notes = (
                f"Image appears authentic ({real_prob:.1%} confidence). "
                f"No strong AI-generation artifacts detected."
            )

        result = AIDetectionResult(
            is_ai_generated=is_ai,
            ai_probability=round(ai_prob, 6),
            real_probability=round(real_prob, 6),
            verdict=verdict,
            suspicion_score=round(ai_prob, 6),  # directly usable in agent pipeline
            notes=notes,
        )

        logger.info(
            f"AI Detection → verdict={verdict}, ai_prob={ai_prob:.4f}, "
            f"real_prob={real_prob:.4f}"
        )
        return result


# ----------------------------------------
# Example usage
if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)

    image_path = "test_watch.jpeg"

    # Run both models by default
    detectors = {
        "umm-maybe": AIImageDetector(model_type="umm-maybe", suspicious_threshold=0.45, ai_threshold=0.75),
        "sdxl": AIImageDetector(model_type="sdxl", suspicious_threshold=0.45, ai_threshold=0.75),
    }

    for model_name, detector in detectors.items():
        result = detector.analyze(image_path)
        print(f"\n--- AI Image Detection Report ({model_name}) ---")
        print(f"Verdict          : {result.verdict}")
        print(f"Is AI Generated  : {result.is_ai_generated}")
        print(f"AI Probability   : {result.ai_probability:.4f}")
        print(f"Real Probability : {result.real_probability:.4f}")
        print(f"Suspicion Score  : {result.suspicion_score:.4f}")
        print(f"Notes            : {result.notes}")