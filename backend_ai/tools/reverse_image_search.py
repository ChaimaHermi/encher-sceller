
IMGBB_UPLOAD_URL = "https://api.imgbb.com/1/upload"

# verifier_tools/reverse_image_search.py

import os
import re
import io
import base64
import logging
import tempfile
from dataclasses import dataclass, field
from typing import Optional
from urllib.parse import urlparse
from dotenv import load_dotenv
import requests
from PIL import Image
import imagehash

logger = logging.getLogger(__name__)
load_dotenv()
# ── constants ────────────────────────────────────────────────────────────────

SERPAPI_ENDPOINT = "https://serpapi.com/search"

# Domains that suggest the image is stolen from a listing or stock site
SUSPICIOUS_DOMAINS = {
    "shutterstock.com", "gettyimages.com", "istockphoto.com",
    "alamy.com", "dreamstime.com", "123rf.com",
    "ebay.com", "amazon.com", "aliexpress.com", "taobao.com","wikipedia.com"
}

# Domains that are neutral / expected (social, news, blogs)
NEUTRAL_DOMAINS = {
    "wikipedia.org", "wikimedia.org", "reddit.com",
    "pinterest.com", "instagram.com",
}


# ── result dataclass ─────────────────────────────────────────────────────────

@dataclass
class ReverseSearchResult:
    """
    Result of reverse image search.

    found_online        : bool   → image (or near-duplicate) exists on the web
    match_count         : int    → number of web matches found
    suspicious_sources  : list   → matches from stock/listing sites (red flag)
    all_matches         : list   → all found matches with title, url, source
    estimated_price     : Optional[float] → market price if found on listing site
    suspicion_score     : float  → 0.0 (clean) to 1.0 (stolen/fake), for agent pipeline
    similarity_scores   : list[dict] → similarity score for each compared match
    avg_similarity      : float  → average similarity score across matches (0-1, higher = more similar)
    verdict             : str    → "clean" | "suspicious" | "stolen"
    engine_used         : str    → "serpapi" | "bing" | "both" | "none"
    notes               : str    → human-readable explanation
    """
    found_online: bool
    match_count: int
    suspicious_sources: list[dict]
    all_matches: list[dict]
    estimated_price: Optional[float]
    suspicion_score: float
    similarity_scores: list[dict]
    avg_similarity: float
    verdict: str
    engine_used: str
    notes: str


# ── main class ───────────────────────────────────────────────────────────────

class ReverseImageSearcher:
    def _upload_to_imgbb(self, image_path: str, api_key: Optional[str] = None) -> Optional[str]:
        """Upload image to imgbb and return the public URL."""
        api_key = api_key or os.getenv("IMGBB_API_KEY")
        if not api_key:
            logger.error("IMGBB_API_KEY is required for imgbb uploads.")
            return None
        with open(image_path, "rb") as img_file:
            import base64
            encoded = base64.b64encode(img_file.read()).decode("utf-8")
        data = {"key": api_key, "image": encoded}
        try:
            resp = requests.post(IMGBB_UPLOAD_URL, data=data)
            resp.raise_for_status()
            data = resp.json()
            return data["data"]["url"]
        except Exception as e:
            logger.error(f"imgbb upload failed: {e}")
            return None
    """
    Reverse image search using SerpAPI (Google).

    Detects:
    - Images stolen from stock photo sites
    - Images copied from existing e-commerce listings
    - Near-duplicate product images already listed elsewhere
    - Estimated market price from found listings

    Free tier:
    - SerpAPI  : 100 searches / month → https://serpapi.com
    """

    def __init__(
        self,
        serpapi_key: Optional[str] = None,
        suspicious_threshold: float = 0.4,
        stolen_threshold: float = 0.7,
        max_image_size_kb: int = 1024,        # resize before upload if larger
        timeout: int = 15,                    # request timeout in seconds
    ):
        self.serpapi_key = serpapi_key or os.getenv("SERPAPI_KEY")
        self.suspicious_threshold = suspicious_threshold
        self.stolen_threshold     = stolen_threshold
        self.max_image_size_kb    = max_image_size_kb
        self.timeout              = timeout

        if not self.serpapi_key:
            raise ValueError(
                "SERPAPI_KEY is required. Set it as an environment variable or pass directly."
            )

    # ── image preparation ────────────────────────────────────────────────────

    def _resize_if_needed(self, image_path: str) -> str:
        """
        Resize image if it exceeds max_image_size_kb.
        Returns path to (possibly resized) temp image.
        """
        size_kb = os.path.getsize(image_path) / 1024
        if size_kb <= self.max_image_size_kb:
            return image_path

        with Image.open(image_path) as img:
            img = img.convert("RGB")
            scale = (self.max_image_size_kb / size_kb) ** 0.5
            new_size = (int(img.width * scale), int(img.height * scale))
            img = img.resize(new_size, Image.LANCZOS)

            tmp = tempfile.NamedTemporaryFile(suffix=".jpg", delete=False)
            img.save(tmp.name, format="JPEG", quality=85)
            logger.info(f"Resized image from {size_kb:.0f}KB → {self.max_image_size_kb}KB")
            return tmp.name

    def _image_to_base64(self, image_path: str) -> str:
        """Convert image to base64 string."""
        with open(image_path, "rb") as f:
            return base64.b64encode(f.read()).decode("utf-8")

    def _compute_phash(self, image_path: str, hash_size: int = 8) -> Optional[imagehash.ImageHash]:
        """Compute perceptual hash of local image."""
        try:
            with Image.open(image_path) as img:
                img = img.convert("RGB")
                return imagehash.phash(img, hash_size=hash_size)
        except Exception as e:
            logger.error(f"Failed to compute pHash for {image_path}: {e}")
            return None

    def _download_and_hash_thumbnail(self, thumbnail_url: str, hash_size: int = 8) -> Optional[imagehash.ImageHash]:
        """Download thumbnail from URL and compute its perceptual hash."""
        if not thumbnail_url:
            return None
        try:
            resp = requests.get(thumbnail_url, timeout=5)
            resp.raise_for_status()
            img = Image.open(io.BytesIO(resp.content)).convert("RGB")
            return imagehash.phash(img, hash_size=hash_size)
        except Exception as e:
            logger.debug(f"Failed to download/hash thumbnail {thumbnail_url}: {e}")
            return None

    def _compute_similarity(self, hash1: imagehash.ImageHash, hash2: imagehash.ImageHash) -> float:
        """
        Compute similarity score between two pHashes.
        Returns 0.0 (completely different) to 1.0 (identical).
        Hamming distance of 0 = identical, max distance = 64 for 8x8 hash.
        """
        if hash1 is None or hash2 is None:
            return 0.0
        hamming_distance = hash1 - hash2  # imagehash overloads __sub__ for hamming distance
        max_distance = 64  # 8x8 hash = 64 bits
        similarity = 1.0 - (hamming_distance / max_distance)
        return max(0.0, min(1.0, similarity))

    def _compare_with_matches(self, image_path: str, matches: list[dict], max_compare: int = 10) -> tuple[list[dict], float]:
        """
        Compare original image with thumbnails from matches using pHash.
        Returns list of similarity results and average similarity score.
        """
        original_hash = self._compute_phash(image_path)
        if original_hash is None:
            logger.warning("Could not compute hash for original image, skipping similarity check.")
            return [], 0.0

        similarity_results = []
        total_similarity = 0.0
        compared_count = 0

        for match in matches[:max_compare]:
            thumbnail_url = match.get("thumbnail")
            if not thumbnail_url:
                continue

            match_hash = self._download_and_hash_thumbnail(thumbnail_url)
            if match_hash is None:
                continue

            similarity = self._compute_similarity(original_hash, match_hash)
            similarity_results.append({
                "url": match.get("url", ""),
                "thumbnail": thumbnail_url,
                "similarity": round(similarity, 4),
                "domain": match.get("domain", self._extract_domain(match.get("url", ""))),
            })
            total_similarity += similarity
            compared_count += 1

        avg_similarity = total_similarity / compared_count if compared_count > 0 else 0.0
        logger.info(f"Compared {compared_count} thumbnails, avg similarity: {avg_similarity:.3f}")
        return similarity_results, round(avg_similarity, 4)

    # ── SerpAPI ──────────────────────────────────────────────────────────────

    def _search_serpapi(self, image_path: str) -> list[dict]:
        """
        Run Google Reverse Image Search via SerpAPI using a public imgbb URL.
        Returns list of match dicts.
        """
        if not self.serpapi_key:
            logger.warning("SerpAPI key not set, skipping.")
            return []

        logger.info("Uploading image to imgbb for SerpAPI search...")
        imgbb_url = self._upload_to_imgbb(image_path)
        if not imgbb_url:
            logger.error("Failed to upload image to imgbb. Aborting search.")
            return []

        logger.info(f"Running SerpAPI reverse image search with URL: {imgbb_url}")
        params = {
            "engine":    "google_reverse_image",
            "image_url": imgbb_url,
            "api_key":   self.serpapi_key,
            "hl":        "en",
            "gl":        "us",
        }

        try:
            resp = requests.get(
                SERPAPI_ENDPOINT,
                params=params,
                timeout=self.timeout,
            )
            resp.raise_for_status()
            data = resp.json()
        except requests.RequestException as e:
            logger.error(f"SerpAPI request failed: {e}")
            return []

        matches = []

        # Parse inline images (visually similar)
        for item in data.get("inline_images", []):
            matches.append({
                "title":  item.get("title", ""),
                "url":    item.get("link", ""),
                "source": item.get("source", ""),
                "thumbnail": item.get("thumbnail", ""),
                "engine": "serpapi",
            })

        # Parse image results
        for item in data.get("image_results", []):
            matches.append({
                "title":  item.get("title", ""),
                "url":    item.get("link", ""),
                "source": item.get("displayed_link", ""),
                "thumbnail": item.get("thumbnail", ""),
                "engine": "serpapi",
            })

        logger.info(f"SerpAPI returned {len(matches)} matches.")
        return matches


    # ── analysis ─────────────────────────────────────────────────────────────

    def _extract_domain(self, url: str) -> str:
        """Extract root domain from URL."""
        try:
            return urlparse(url).netloc.replace("www.", "")
        except Exception:
            return ""

    def _extract_price(self, matches: list[dict]) -> Optional[float]:
        """
        Try to extract a market price from listing matches.
        Looks for price patterns in titles and explicit price fields.
        """
        price_pattern = re.compile(r"\$\s?([\d,]+(?:\.\d{1,2})?)")

        for match in matches:
            # Check explicit price field (Bing shopping)
            if match.get("price") and isinstance(match["price"], (int, float)):
                return float(match["price"])

            # Check title for price string
            title = match.get("title", "")
            found = price_pattern.findall(title)
            if found:
                try:
                    return float(found[0].replace(",", ""))
                except ValueError:
                    continue

        return None

    def _analyze_matches(
        self, matches: list[dict], similarity_scores: list[dict], avg_similarity: float
    ) -> tuple[list[dict], float, str, str]:
        """
        Analyze match list to compute suspicion score and verdict.
        Incorporates image similarity scores into the calculation.
        Returns (suspicious_sources, suspicion_score, verdict, notes).
        """
        if not matches:
            return [], 0.0, "clean", "No matching images found on the web."

        suspicious_sources = []
        notes_parts = []
        score = 0.0

        for match in matches:
            domain = self._extract_domain(match.get("url", ""))
            match["domain"] = domain

            if any(s in domain for s in SUSPICIOUS_DOMAINS):
                suspicious_sources.append(match)

        # Scoring logic
        total = len(matches)
        sus_count = len(suspicious_sources)

        # Base score: any match online adds some suspicion
        if total > 0:
            score += min(total / 20.0, 0.3)   # up to 0.3 for volume of matches
            notes_parts.append(f"Found {total} matching images online.")

        # Heavy penalty for stock photo or listing site matches
        if sus_count > 0:
            score += min(sus_count / 3.0, 0.5)
            domains_found = list({m["domain"] for m in suspicious_sources})
            notes_parts.append(
                f"Image found on suspicious domains: {', '.join(domains_found)}. "
                f"Possible stolen stock photo or copied listing."
            )

        # Check if image appears on e-commerce listing sites specifically
        listing_domains = {"ebay.com", "amazon.com", "aliexpress.com", "taobao.com"}
        listing_hits = [
            m for m in suspicious_sources
            if any(d in m.get("domain", "") for d in listing_domains)
        ]
        if listing_hits:
            score += 0.2
            notes_parts.append(
                f"Image already used in an active product listing — "
                f"possible fraudulent re-listing."
            )

        # NEW: Incorporate image similarity into suspicion score
        # High similarity to online matches = higher suspicion
        if avg_similarity > 0:
            # Scale similarity contribution: 0.9+ similarity adds up to 0.3 to score
            similarity_penalty = 0.0
            if avg_similarity >= 0.95:
                similarity_penalty = 0.3
                notes_parts.append(f"Very high visual similarity ({avg_similarity:.1%}) to online matches — likely exact or near-duplicate.")
            elif avg_similarity >= 0.85:
                similarity_penalty = 0.2
                notes_parts.append(f"High visual similarity ({avg_similarity:.1%}) to online matches.")
            elif avg_similarity >= 0.70:
                similarity_penalty = 0.1
                notes_parts.append(f"Moderate visual similarity ({avg_similarity:.1%}) to online matches.")
            score += similarity_penalty

            # Check for any highly similar matches on suspicious domains
            high_sim_suspicious = [
                s for s in similarity_scores
                if s["similarity"] >= 0.90 and any(d in s["domain"] for d in SUSPICIOUS_DOMAINS)
            ]
            if high_sim_suspicious:
                score += 0.15
                notes_parts.append(
                    f"{len(high_sim_suspicious)} match(es) with >90% similarity found on suspicious domains."
                )

        score = min(score, 1.0)

        if score >= self.stolen_threshold:
            verdict = "stolen"
        elif score >= self.suspicious_threshold:
            verdict = "suspicious"
        else:
            verdict = "clean"

        if not notes_parts:
            notes = "Image appears original, no concerning web matches."
        else:
            notes = " | ".join(notes_parts)

        return suspicious_sources, round(score, 4), verdict, notes

    # ── public API ───────────────────────────────────────────────────────────

    def analyze(self, image_path: str) -> ReverseSearchResult:
        """
        Run reverse image search using SerpAPI only.

        Returns ReverseSearchResult with matches, scores, and verdict.
        """
        logger.info(f"Starting reverse image search for: {image_path}")

        resized_path = self._resize_if_needed(image_path)
        all_matches = []
        engine_used = "serpapi"

        # Only SerpAPI
        serp_matches = self._search_serpapi(resized_path)
        if serp_matches:
            all_matches.extend(serp_matches)

        # Deduplicate by URL
        seen_urls = set()
        deduped = []
        for m in all_matches:
            url = m.get("url", "")
            if url and url not in seen_urls:
                seen_urls.add(url)
                deduped.append(m)

        # Compute visual similarity between original image and matched thumbnails
        similarity_scores, avg_similarity = self._compare_with_matches(image_path, deduped)

        suspicious_sources, suspicion_score, verdict, notes = self._analyze_matches(
            deduped, similarity_scores, avg_similarity
        )
        estimated_price = self._extract_price(deduped)

        result = ReverseSearchResult(
            found_online=len(deduped) > 0,
            match_count=len(deduped),
            suspicious_sources=suspicious_sources,
            all_matches=deduped[:20],           # cap at 20 for agent payload size
            estimated_price=estimated_price,
            suspicion_score=suspicion_score,
            similarity_scores=similarity_scores,
            avg_similarity=avg_similarity,
            verdict=verdict,
            engine_used=engine_used,
            notes=notes,
        )

        logger.info(
            f"Reverse search → verdict={verdict}, score={suspicion_score:.3f}, "
            f"matches={len(deduped)}, avg_similarity={avg_similarity:.3f}, engine={engine_used}"
        )
        return result


# ── example usage ────────────────────────────────────────────────────────────

if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)

    searcher = ReverseImageSearcher(
        serpapi_key=os.getenv("SERPAPI_KEY"),
    )

    result = searcher.analyze("test_watch.jpeg")

    print(f"\n--- Reverse Image Search Report ---")
    print(f"Suspicion Score    : {result.suspicion_score:.4f}")
    print(f"Avg Similarity     : {result.avg_similarity:.4f}")
    print(f"Found Online       : {result.found_online}")
    print(f"Match Count        : {result.match_count}")
    print(f"Engine Used        : {result.engine_used}")
    print(f"Estimated Price    : {'$' + str(result.estimated_price) if result.estimated_price else 'N/A'}")
    print(f"Notes              : {result.notes}")

    if result.similarity_scores:
        print(f"\nSimilarity Scores (top matches):")
        for s in result.similarity_scores[:5]:
            print(f"  {s['similarity']:.1%} - {s['domain']}")

    if result.suspicious_sources:
        print(f"\nSuspicious Sources ({len(result.suspicious_sources)}):")
        for s in result.suspicious_sources[:5]:
            print(f"  [{s['engine']}] {s['domain']} — {s['title'][:60]}")