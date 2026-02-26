# verifier_tools/duplicate_check_qdrant.py

from PIL import Image, UnidentifiedImageError
import imagehash
import numpy as np
from qdrant_client import QdrantClient
from qdrant_client.models import (
    Distance,
    VectorParams,
    PointStruct,
    Filter,
    FieldCondition,
    MatchValue,
    SearchRequest,
)
import os
import uuid
import logging
from typing import Optional
from dotenv import load_dotenv
logger = logging.getLogger(__name__)

# pHash with hash_size=8 → 64-bit hash → 64-dimensional vector
VECTOR_SIZE = 64
COLLECTION_NAME = "image_hashes"


def phash_to_vector(ph: imagehash.ImageHash) -> list[float]:
    """
    Convert a 64-bit pHash into a 64-dimensional binary float vector.
    Each bit in the hash becomes a 0.0 or 1.0.
    This lets Qdrant compute Euclidean distance == Hamming distance.
    """
    bits = bin(int(str(ph), 16))[2:].zfill(VECTOR_SIZE)
    return [float(b) for b in bits]


class DuplicateCheckerQdrant:
    """
    Perceptual hash duplicate checker using Qdrant vector search.
    Stores 64-dim binary vectors derived from pHash.
    Euclidean distance between binary vectors == Hamming distance.
    """

    def __init__(
        self,
        url: str = "http://localhost:6333",
        api_key: Optional[str] = None,
        collection_name: str = COLLECTION_NAME,
        hash_size: int = 8,
        threshold: int = 10,  # max Hamming distance to consider a duplicate
    ):
        self.hash_size = hash_size
        self.threshold = threshold
        self.collection_name = collection_name

        # Use api_key=None for local Docker instance
        self.client = QdrantClient(url=url, api_key=api_key)
        self._ensure_collection()

    def _ensure_collection(self):
        existing = [c.name for c in self.client.get_collections().collections]

        if self.collection_name not in existing:
            self.client.create_collection(
                collection_name=self.collection_name,
                vectors_config=VectorParams(
                    size=VECTOR_SIZE,
                    distance=Distance.EUCLID,
                ),
            )

            # 🔥 CREATE PAYLOAD INDEX FOR filename
            self.client.create_payload_index(
                collection_name=self.collection_name,
                field_name="filename",
                field_schema="keyword",
            )

            logger.info(f"Created Qdrant collection '{self.collection_name}'")
        else:
            logger.info(f"Collection '{self.collection_name}' already exists.")

    def _compute_phash(self, image_path: str) -> imagehash.ImageHash:
        """Compute pHash from image. Raises on bad input."""
        try:
            with Image.open(image_path) as img:
                img = img.convert("RGB")
                return imagehash.phash(img, hash_size=self.hash_size)
        except FileNotFoundError:
            raise FileNotFoundError(f"Image not found: {image_path}")
        except UnidentifiedImageError:
            raise ValueError(f"Unreadable image file: {image_path}")

    def check_duplicate(
        self, image_path: str
    ) -> tuple[bool, Optional[dict]]:
        """
        Search Qdrant for near-duplicate images using ANN search.
        Returns (is_duplicate, payload of matching point or None).
        """
        ph = self._compute_phash(image_path)
        vector = phash_to_vector(ph)

        results = self.client.query_points(
            collection_name=self.collection_name,
            query=vector,
            limit=1,
        )

        if not results.points:
            return False, None

        top = results.points[0]

        # Qdrant Euclidean distance on binary vectors = sqrt(hamming_distance)
        # So we compare sqrt(threshold) on the score, or just square the distance
        hamming_approx = round(top.score ** 2)

        if hamming_approx <= self.threshold:
            logger.warning(
                f"Duplicate found: '{image_path}' ~ '{top.payload.get('filename')}' "
                f"(Hamming ≈ {hamming_approx})"
            )
            return True, top.payload

        return False, None

    def add_to_db(
        self, image_path: str, metadata: Optional[dict] = None
    ) -> str:
        """
        Add image hash vector to Qdrant.
        Returns the point ID (UUID string).
        Skips insert if filename already exists.
        """
        filename = os.path.basename(image_path)

        # Check if filename already stored (prevent duplicate entries)
        existing = self.client.scroll(
            collection_name=self.collection_name,
            scroll_filter=Filter(
                must=[
                    FieldCondition(
                        key="filename",
                        match=MatchValue(value=filename),
                    )
                ]
            ),
            limit=1,
        )
        if existing[0]:  # existing[0] is list of points, existing[1] is next offset
            logger.info(f"'{filename}' already in Qdrant. Skipping.")
            return str(existing[0][0].id)

        ph = self._compute_phash(image_path)
        vector = phash_to_vector(ph)
        point_id = str(uuid.uuid4())

        payload = {"filename": filename, "phash": str(ph)}
        if metadata:
            payload.update(metadata)

        self.client.upsert(
            collection_name=self.collection_name,
            points=[
                PointStruct(
                    id=point_id,
                    vector=vector,
                    payload=payload,
                )
            ],
        )
        logger.info(f"Added '{filename}' to Qdrant with id={point_id}")
        return point_id

    def close(self):
        self.client.close()

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        self.close()


# -------------------------------
# Example usage
if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)
    load_dotenv()
    with DuplicateCheckerQdrant(
        url=os.getenv("QDRANT_URL"),
        api_key=os.getenv("QDRANT_API_KEY"),
    ) as checker:
        test_image = "test_watch.jpeg"

        is_dup, match = checker.check_duplicate(test_image)
        if is_dup:
            print(f"Duplicate detected! Matches: {match}")
        else:
            print("No duplicate. Adding to DB.")
            checker.add_to_db(
                test_image,
                metadata={"user": "alice", "category": "watch"},
            )