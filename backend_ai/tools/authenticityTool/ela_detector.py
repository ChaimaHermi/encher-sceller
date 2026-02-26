# verifier_tools/ela_detector.py

from PIL import Image, UnidentifiedImageError
import numpy as np
import os
import logging
from dataclasses import dataclass
from typing import Optional
import tempfile

logger = logging.getLogger(__name__)


@dataclass
class ELAResult:
    """
    Result of ELA analysis on an image.
    
    suspicion_score : float  → 0.0 (clean) to 1.0 (highly suspicious)
    mean_error      : float  → average pixel-level difference after recompression
    max_error       : float  → highest localized error found (flags hotspots)
    high_error_ratio: float  → % of pixels exceeding the anomaly threshold
    verdict         : str    → "clean" | "suspicious" | "likely_manipulated"
    ela_image_path  : str    → path to saved ELA visualization (amplified diff)
    notes           : str    → human-readable explanation
    """
    suspicion_score: float
    mean_error: float
    max_error: float
    high_error_ratio: float
    verdict: str
    ela_image_path: Optional[str]
    notes: str


class ELADetector:
    """
    Error Level Analysis (ELA) detector.

    How it works:
    1. Re-save the input image at a known JPEG quality level.
    2. Compute the pixel-wise absolute difference between original and re-saved.
    3. Amplify the difference so subtle errors are visible.
    4. Analyze the error distribution to flag anomalies.

    Authentic unedited images compress uniformly — errors are spread evenly.
    Manipulated regions were already compressed at a different quality level,
    so they show either much lower OR much higher error than surrounding areas.
    """

    def __init__(
        self,
        resave_quality: int = 90,       # JPEG quality for re-compression step
        amplify_factor: int = 20,       # how much to amplify diff for visualization
        anomaly_threshold: float = 15.0,# per-pixel error above this = anomaly
        suspicious_score: float = 0.4,  # suspicion_score cutoff for "suspicious"
        manipulated_score: float = 0.7, # suspicion_score cutoff for "likely_manipulated"
    ):
        self.resave_quality = resave_quality
        self.amplify_factor = amplify_factor
        self.anomaly_threshold = anomaly_threshold
        self.suspicious_score = suspicious_score
        self.manipulated_score = manipulated_score

    def _load_and_normalize(self, image_path: str) -> Image.Image:
        """Load image, normalize to RGB JPEG-compatible format."""
        try:
            img = Image.open(image_path).convert("RGB")
            return img
        except FileNotFoundError:
            raise FileNotFoundError(f"Image not found: {image_path}")
        except UnidentifiedImageError:
            raise ValueError(f"Cannot read image: {image_path}")

    def _resave_as_jpeg(self, img: Image.Image, quality: int) -> Image.Image:
        """Re-save image at given JPEG quality and reload it."""
        with tempfile.NamedTemporaryFile(suffix=".jpg", delete=False) as tmp:
            tmp_path = tmp.name

        try:
            img.save(tmp_path, format="JPEG", quality=quality)
            reloaded = Image.open(tmp_path).convert("RGB")
            reloaded.load()  # force read before file is deleted
        finally:
            os.unlink(tmp_path)

        return reloaded

    def _compute_ela_array(
        self, original: Image.Image, recompressed: Image.Image
    ) -> np.ndarray:
        """
        Compute absolute difference between original and recompressed image.
        Returns float32 array of shape (H, W, 3).
        """
        orig_arr = np.array(original, dtype=np.float32)
        recomp_arr = np.array(recompressed, dtype=np.float32)
        ela_arr = np.abs(orig_arr - recomp_arr)
        return ela_arr

    def _amplify_for_visualization(self, ela_arr: np.ndarray) -> Image.Image:
        """
        Amplify ELA array so subtle errors are visible, clip to [0, 255].
        Returns PIL Image for saving/display.
        """
        amplified = np.clip(ela_arr * self.amplify_factor, 0, 255).astype(np.uint8)
        return Image.fromarray(amplified)

    def _compute_scores(self, ela_arr: np.ndarray) -> tuple[float, float, float]:
        """
        Compute mean error, max error, and ratio of high-error pixels.
        Returns (mean_error, max_error, high_error_ratio).
        """
        # Per-pixel magnitude (average across RGB channels)
        pixel_errors = ela_arr.mean(axis=2)  # shape (H, W)

        mean_error = float(pixel_errors.mean())
        max_error = float(pixel_errors.max())

        total_pixels = pixel_errors.size
        high_error_pixels = np.sum(pixel_errors > self.anomaly_threshold)
        high_error_ratio = float(high_error_pixels / total_pixels)

        return mean_error, max_error, high_error_ratio

    def _build_suspicion_score(
        self,
        mean_error: float,
        max_error: float,
        high_error_ratio: float,
    ) -> tuple[float, str]:
        """
        Combine metrics into a single suspicion score [0.0, 1.0].

        Scoring rationale:
        - High mean_error alone isn't suspicious (low quality source image compresses badly).
        - High VARIANCE / uneven error distribution IS suspicious.
        - High high_error_ratio (many localized hotspots) is suspicious.
        - Very low mean_error with isolated high_error spikes = classic splice signature.
        """
        score = 0.0
        notes_parts = []

        # 1. High error ratio contributes up to 0.5
        ratio_score = min(high_error_ratio * 5.0, 0.5)
        score += ratio_score
        if high_error_ratio > 0.05:
            notes_parts.append(
                f"{high_error_ratio:.1%} of pixels show anomalous error (threshold: {self.anomaly_threshold})"
            )

        # 2. Contrast between mean and max: large gap = isolated tampering
        if mean_error > 0:
            contrast_ratio = max_error / (mean_error + 1e-6)
            contrast_score = min((contrast_ratio - 1.0) / 30.0, 0.3)
            score += max(contrast_score, 0.0)
            if contrast_ratio > 10:
                notes_parts.append(
                    f"High contrast between mean ({mean_error:.2f}) and max ({max_error:.2f}) error — "
                    f"suggests localized manipulation"
                )

        # 3. Very low mean error with high ratio = clean background + spliced region
        if mean_error < 5.0 and high_error_ratio > 0.02:
            score += 0.2
            notes_parts.append(
                "Low global error but localized hotspots — classic copy-paste or splice pattern"
            )

        score = min(score, 1.0)

        if not notes_parts:
            notes = "No strong manipulation indicators detected."
        else:
            notes = " | ".join(notes_parts)

        return score, notes

    def analyze(self, image_path: str) -> ELAResult:
        """
        Run ELA on the given image.
        Returns an ELAResult with scores, verdict, and optional visualization path.
        """
        logger.info(f"Running ELA on: {image_path}")

        original = self._load_and_normalize(image_path)
        recompressed = self._resave_as_jpeg(original, quality=self.resave_quality)
        ela_arr = self._compute_ela_array(original, recompressed)

        mean_error, max_error, high_error_ratio = self._compute_scores(ela_arr)
        suspicion_score, notes = self._build_suspicion_score(
            mean_error, max_error, high_error_ratio
        )

        # Determine verdict
        if suspicion_score >= self.manipulated_score:
            verdict = "likely_manipulated"
        elif suspicion_score >= self.suspicious_score:
            verdict = "suspicious"
        else:
            verdict = "clean"

        # Do not save ELA visualization
        ela_image_path = None

        result = ELAResult(
            suspicion_score=round(suspicion_score, 4),
            mean_error=round(mean_error, 4),
            max_error=round(max_error, 4),
            high_error_ratio=round(high_error_ratio, 6),
            verdict=verdict,
            ela_image_path=ela_image_path,
            notes=notes,
        )

        logger.info(
            f"ELA result → verdict={verdict}, score={suspicion_score:.3f}, "
            f"mean_err={mean_error:.2f}, max_err={max_error:.2f}, "
            f"high_ratio={high_error_ratio:.4f}"
        )
        return result



# ----------------------------------------
# Tool wrapper for agent integration
def run_ela_detector_tool(image_path: str) -> dict:
    """
    Lightweight wrapper to call ELA detector as an agent tool.
    Returns a dictionary for easy pipeline integration.
    """
    detector = ELADetector()
    result = detector.analyze(image_path)
    return {
        "tool": "ela_detector",
        "image_path": image_path,
        "suspicion_score": result.suspicion_score,
        "mean_error": result.mean_error,
        "max_error": result.max_error,
        "high_error_ratio": result.high_error_ratio,
        "verdict": result.verdict,
        "ela_image_path": result.ela_image_path,
        "notes": result.notes,
    }


# Example usage
if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)

    detector = ELADetector(
        resave_quality=90,
        amplify_factor=20,
        anomaly_threshold=15.0,
    )

    result = detector.analyze("test_watch.jpeg")

    print(f"\n--- ELA Report ---")
    print(f"Verdict         : {result.verdict}")
    print(f"Suspicion Score : {result.suspicion_score:.4f}")
    print(f"Mean Error      : {result.mean_error:.4f}")
    print(f"Max Error       : {result.max_error:.4f}")
    print(f"High Error Ratio: {result.high_error_ratio:.4%}")
    print(f"Notes           : {result.notes}")
    if result.ela_image_path:
        print(f"ELA Image       : {result.ela_image_path}")