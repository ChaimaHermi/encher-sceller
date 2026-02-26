
import base64
import logging
import os
import re
from dataclasses import dataclass, field
from typing import Optional
import requests
from PIL import Image
from dotenv import load_dotenv
load_dotenv()
logger = logging.getLogger(__name__)


@dataclass
class VisionAnalysisResult:
    """
    Result of AI vision analysis on auction item.

    object_type         : str   → identified object (e.g. "pocket watch", "oil painting")
    estimated_period    : str   → estimated era/period (e.g. "1920s–1940s")
    style               : str   → artistic/design style if applicable
    materials           : list  → apparent materials detected
    wear_assessment     : str   → "natural" | "artificial" | "minimal" | "unknown"
    signatures_detected : list  → any signatures, hallmarks, poinçons found
    suspicious_zones    : list  → described areas of concern
    authenticity_score  : float → 0.0 to 1.0 (1.0 = highly likely authentic)
    suspicion_score     : float → 0.0 to 1.0 for agent pipeline
    verdict             : str   → "authentic" | "suspicious" | "likely_fake"
    full_report         : str   → complete LLM analysis text
    engine_used         : str   → "openrouter_mistral"
    """
    object_type: str
    estimated_period: str
    style: str
    materials: list[str]
    wear_assessment: str
    signatures_detected: list[str]
    suspicious_zones: list[str]
    authenticity_score: float
    suspicion_score: float
    verdict: str
    full_report: str
    engine_used: str


VISION_PROMPT = """
You are an expert authenticator and appraiser for auction items.
Analyze this image and provide a structured assessment.

You MUST respond in this exact JSON format and nothing else:
{
  "object_type": "specific object name",
  "estimated_period": "decade or era (e.g. 1920s-1940s)",
  "style": "artistic or design style",
  "materials": ["material1", "material2"],
  "wear_assessment": "natural | artificial | minimal | unknown",
  "wear_notes": "explanation of wear patterns observed",
  "signatures_detected": ["description of any signatures, hallmarks, poincons, stamps"],
  "suspicious_zones": ["description of zone 1", "description of zone 2"],
  "authenticity_score": 0.85,
  "authenticity_reasoning": "detailed reasoning for the score",
  "red_flags": ["flag1", "flag2"]
}

Guidelines:
- wear_assessment: 'natural' means consistent aging patterns, 'artificial' means fake aging signs
- authenticity_score: 0.0 = certainly fake, 1.0 = certainly authentic
- suspicious_zones: describe specific areas that look wrong (e.g. "bottom-left corner shows inconsistent patina")
- Be specific about materials, proportions, and construction details visible
- Flag any signs of reproduction, modern materials in old items, or inconsistent aging
"""


class VisionAnalyzer:
    """
    AI vision analysis for auction item authentication.

    Uses OpenRouter API with Mistral Ministral 14B model for vision analysis.
    """

    def __init__(
        self,
        openrouter_api_key: Optional[str] = None,
        model: str = "mistralai/ministral-14b-2512",
        suspicious_threshold: float = 0.45,
        fake_threshold: float = 0.25,
        max_image_size: tuple = (1024, 1024),
    ):
        self.openrouter_api_key = openrouter_api_key or os.getenv("OPENROUTER_API_KEY")
        self.model = model
        self.suspicious_threshold = suspicious_threshold
        self.fake_threshold = fake_threshold
        self.max_image_size = max_image_size
        self.api_url = "https://openrouter.ai/api/v1/chat/completions"

    def _prepare_image_base64(self, image_path: str) -> str:
        """Resize if needed and convert to base64 data URL."""
        with Image.open(image_path) as img:
            img = img.convert("RGB")
            img.thumbnail(self.max_image_size, Image.LANCZOS)
            import io
            buffer = io.BytesIO()
            img.save(buffer, format="JPEG", quality=90)
            b64 = base64.b64encode(buffer.getvalue()).decode("utf-8")
            return f"data:image/jpeg;base64,{b64}"

    # ── OpenRouter Mistral ───────────────────────────────────────────────────

    def _analyze_openrouter(self, image_path: str) -> dict:
        """Call OpenRouter API with Mistral Ministral 14B model."""
        if not self.openrouter_api_key:
            logger.error("OPENROUTER_API_KEY not set.")
            return {}

        logger.info(f"Calling OpenRouter ({self.model})...")

        image_data_url = self._prepare_image_base64(image_path)

        headers = {
            "Authorization": f"Bearer {self.openrouter_api_key}",
            "Content-Type": "application/json",
            "HTTP-Referer": "https://auction-platform.local",
            "X-Title": "Auction Image Validator",
        }

        payload = {
            "model": self.model,
            "messages": [
                {
                    "role": "user",
                    "content": [
                        {
                            "type": "text",
                            "text": VISION_PROMPT
                        },
                        {
                            "type": "image_url",
                            "image_url": {
                                "url": image_data_url
                            }
                        }
                    ]
                }
            ],
            "temperature": 0.1,
            "max_tokens": 2000,
        }

        try:
            resp = requests.post(
                self.api_url,
                headers=headers,
                json=payload,
                timeout=60,
            )
            resp.raise_for_status()
            data = resp.json()
            raw = data["choices"][0]["message"]["content"]
            return {"raw": raw, "engine": "openrouter_mistral"}
        except requests.RequestException as e:
            logger.error(f"OpenRouter request failed: {e}")
            if hasattr(e, 'response') and e.response is not None:
                logger.error(f"Response: {e.response.text}")
            return {}
        except (KeyError, IndexError) as e:
            logger.error(f"Failed to parse OpenRouter response: {e}")
            return {}

    # ── response parser ──────────────────────────────────────────────────────

    def _parse_response(self, raw: str) -> dict:
        """Parse JSON response from vision model, handle malformed output."""
        import json

        # Strip markdown fences if present
        clean = re.sub(r"```(?:json)?|```", "", raw).strip()

        try:
            return json.loads(clean)
        except json.JSONDecodeError:
            # Try to extract JSON object with regex
            match = re.search(r"\{.*\}", clean, re.DOTALL)
            if match:
                try:
                    return json.loads(match.group())
                except json.JSONDecodeError:
                    pass

        logger.warning("Could not parse vision model JSON response.")
        return {}

    def _build_result(self, parsed: dict, engine: str, raw: str) -> VisionAnalysisResult:
        """Build VisionAnalysisResult from parsed model output."""
        authenticity_score = float(parsed.get("authenticity_score", 0.5))
        suspicion_score = round(1.0 - authenticity_score, 4)

        if authenticity_score <= self.fake_threshold:
            verdict = "likely_fake"
        elif authenticity_score <= self.suspicious_threshold + 0.3:
            verdict = "suspicious"
        else:
            verdict = "authentic"

        return VisionAnalysisResult(
            object_type=parsed.get("object_type", "unknown"),
            estimated_period=parsed.get("estimated_period", "unknown"),
            style=parsed.get("style", "unknown"),
            materials=parsed.get("materials", []),
            wear_assessment=parsed.get("wear_assessment", "unknown"),
            signatures_detected=parsed.get("signatures_detected", []),
            suspicious_zones=parsed.get("suspicious_zones", []),
            authenticity_score=round(authenticity_score, 4),
            suspicion_score=suspicion_score,
            verdict=verdict,
            full_report=parsed.get("authenticity_reasoning", raw[:500]),
            engine_used=engine,
        )

    # ── public API ───────────────────────────────────────────────────────────

    def analyze(self, image_path: str) -> VisionAnalysisResult:
        """
        Run vision analysis using OpenRouter Mistral model.
        """
        logger.info(f"Running vision analysis on: {image_path}")

        result = self._analyze_openrouter(image_path)
        if result:
            parsed = self._parse_response(result["raw"])
            if parsed:
                return self._build_result(parsed, result["engine"], result["raw"])

        # Fallback if engine fails
        logger.error("Vision analysis failed.")
        return VisionAnalysisResult(
            object_type="unknown", estimated_period="unknown",
            style="unknown", materials=[], wear_assessment="unknown",
            signatures_detected=[], suspicious_zones=[],
            authenticity_score=0.5, suspicion_score=0.5,
            verdict="suspicious",
            full_report="Vision analysis unavailable.",
            engine_used="none",
        )
    
# ----------------------------------------
# Example usage for testing
if __name__ == "__main__":
    import sys
    logging.basicConfig(level=logging.INFO)
    # Use image path from command line or default
    image_path = sys.argv[1] if len(sys.argv) > 1 else "test_watch.jpeg"
    analyzer = VisionAnalyzer()
    result = analyzer.analyze(image_path)
    print("\n--- Vision Analyzer Report ---")
    print(f"Object Type         : {result.object_type}")
    print(f"Estimated Period    : {result.estimated_period}")
    print(f"Style               : {result.style}")
    print(f"Materials           : {', '.join(result.materials)}")
    print(f"Wear Assessment     : {result.wear_assessment}")
    print(f"Signatures Detected : {', '.join(result.signatures_detected)}")
    print(f"Suspicious Zones    : {', '.join(result.suspicious_zones)}")
    print(f"Authenticity Score  : {result.authenticity_score:.2f}")
    print(f"Suspicion Score     : {result.suspicion_score:.2f}")
    print(f"Verdict             : {result.verdict}")
    print(f"Engine Used         : {result.engine_used}")
    print(f"\nFull Report:\n{result.full_report}")