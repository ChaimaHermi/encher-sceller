# verifier_tools/exif_analysis.py

from datetime import datetime, timezone
import logging
from pathlib import Path
from typing import Any, Dict

from PIL import Image
from PIL.ExifTags import TAGS

logger = logging.getLogger(__name__)


class ExifAnalyzer:
    """
    EXIF metadata analyzer designed for agent-tool pipelines.

    Intended pipeline: EXIF -> ELA -> CLIP description matching -> reverse image search.
    This tool provides an evidence-rich EXIF verdict and does not make a final fraud decision.
    """

    def extract_exif(self, image_path: str) -> Dict[str, Any]:
        """Extract EXIF metadata from an image into a JSON-serializable dict."""
        try:
            with Image.open(image_path) as image:
                exif_data = image.getexif()

                if not exif_data:
                    return {}

                extracted: Dict[str, Any] = {}
                for tag_id, value in exif_data.items():
                    tag_name = TAGS.get(tag_id, str(tag_id))
                    if isinstance(value, bytes):
                        extracted[str(tag_name)] = value.decode(
                            "utf-8", errors="replace"
                        )
                    else:
                        extracted[str(tag_name)] = value

                return extracted

        except FileNotFoundError:
            raise FileNotFoundError(f"Image not found: {image_path}")
        except Exception as error:
            logger.error("EXIF extraction error for %s: %s", image_path, error)
            return {}

    def analyze(self, image_path: str) -> Dict[str, Any]:
        """
        Return raw EXIF metadata.
        If EXIF is missing, return an explicit status.
        """
        exif = self.extract_exif(image_path)

        if not exif:
            return {
                "tool": "exif_analysis",
                "image_path": str(Path(image_path).as_posix()),
                "generated_at": datetime.now(timezone.utc)
                .isoformat()
                .replace("+00:00", "Z"),
                "has_exif": False,
                "message": "EXIF does not exist",
                "exif_raw": {},
            }

        return {
            "tool": "exif_analysis",
            "image_path": str(Path(image_path).as_posix()),
            "generated_at": datetime.now(timezone.utc)
            .isoformat()
            .replace("+00:00", "Z"),
            "has_exif": True,
            "message": "EXIF exists",
            "exif_raw": exif,
        }


def run_exif_analysis_tool(image_path: str) -> Dict[str, Any]:
    """
    Lightweight wrapper to call EXIF analysis as an agent tool.
    """
    analyzer = ExifAnalyzer()
    return analyzer.analyze(image_path)


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)
    test_image = "test_watch.jpeg"
    analysis = run_exif_analysis_tool(test_image)

    print("\nEXIF Analysis Result\n")
    for key, value in analysis.items():
        print(f"{key}: {value}")