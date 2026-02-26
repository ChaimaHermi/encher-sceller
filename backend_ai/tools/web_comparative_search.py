# verifier_tools/web_comparative_search.py

import logging
import os
from dataclasses import dataclass, field
from typing import Optional
import requests

logger = logging.getLogger(__name__)

EUROPEANA_ENDPOINT    = "https://api.europeana.eu/record/v2/search.json"
MET_ENDPOINT          = "https://collectionapi.metmuseum.org/public/collection/v1"
HARVARD_ENDPOINT      = "https://api.harvardartmuseums.org/object"
WIKIPEDIA_ENDPOINT    = "https://en.wikipedia.org/api/rest_v1/page/summary"
SERPER_ENDPOINT       = "https://google.serper.dev/search"


@dataclass
class ComparativeSearchResult:
    """
    Result of web comparative search.

    museum_matches      : list  → matches found in museum/auction databases
    stolen_art_flags    : list  → potential matches in theft registries
    publications        : list  → academic/press references found
    auction_comparables : list  → similar items sold at auction with prices
    wikipedia_context   : str   → relevant Wikipedia summary if found
    estimated_value     : Optional[float] → market estimate from auction comparables
    suspicion_score     : float → 0.0 to 1.0
    verdict             : str   → "clear" | "flagged" | "stolen_risk"
    notes               : str
    sources_checked     : list[str]
    """
    museum_matches: list[dict]
    stolen_art_flags: list[dict]
    publications: list[dict]
    auction_comparables: list[dict]
    wikipedia_context: str
    estimated_value: Optional[float]
    suspicion_score: float
    verdict: str
    notes: str
    sources_checked: list[str]


class WebComparativeSearcher:
    """
    Web comparative search for auction item verification.

    Free sources used:
    - Metropolitan Museum API     (free, no key)
    - Europeana API               (free, key required but free registration)
    - Harvard Art Museums API     (free, key required)
    - Wikipedia REST API          (free, no key)
    - Serper.dev                  (free tier: 2500 queries/month)
      └ searches: Christie's, Sotheby's, Interpol, general web
    """

    def __init__(
        self,
        serper_api_key: Optional[str] = None,
        europeana_api_key: Optional[str] = None,
        harvard_api_key: Optional[str] = None,
        timeout: int = 10,
    ):
        self.serper_key    = serper_api_key    or os.getenv("SERPER_API_KEY")
        self.europeana_key = europeana_api_key or os.getenv("EUROPEANA_API_KEY")
        self.harvard_key   = harvard_api_key   or os.getenv("HARVARD_API_KEY")
        self.timeout = timeout

    # ── Metropolitan Museum (free, no key) ───────────────────────────────────

    def _search_met(self, query: str) -> list[dict]:
        """Search Met Museum open collection."""
        logger.info(f"Searching Met Museum for: {query}")
        try:
            search_resp = requests.get(
                f"{MET_ENDPOINT}/search",
                params={"q": query, "hasImages": True},
                timeout=self.timeout,
            )
            search_resp.raise_for_status()
            object_ids = search_resp.json().get("objectIDs") or []

            results = []
            for obj_id in object_ids[:3]:    # limit to 3 to save time
                obj_resp = requests.get(
                    f"{MET_ENDPOINT}/objects/{obj_id}",
                    timeout=self.timeout,
                )
                if obj_resp.ok:
                    obj = obj_resp.json()
                    results.append({
                        "source": "Metropolitan Museum",
                        "title": obj.get("title"),
                        "period": obj.get("period") or obj.get("objectDate"),
                        "medium": obj.get("medium"),
                        "url": obj.get("objectURL"),
                        "image": obj.get("primaryImageSmall"),
                        "artist": obj.get("artistDisplayName"),
                    })
            return results
        except requests.RequestException as e:
            logger.error(f"Met API error: {e}")
            return []

    # ── Europeana (free, needs key) ───────────────────────────────────────────

    def _search_europeana(self, query: str) -> list[dict]:
        """Search Europeana — 50M+ museum objects across Europe."""
        if not self.europeana_key:
            logger.warning("EUROPEANA_API_KEY not set, skipping.")
            return []

        logger.info(f"Searching Europeana for: {query}")
        try:
            resp = requests.get(
                EUROPEANA_ENDPOINT,
                params={
                    "query": query,
                    "wskey": self.europeana_key,
                    "rows": 3,
                    "media": True,
                    "profile": "rich",
                },
                timeout=self.timeout,
            )
            resp.raise_for_status()
            items = resp.json().get("items", [])

            return [
                {
                    "source": "Europeana",
                    "title": item.get("title", [""])[0],
                    "period": item.get("year", [""])[0] if item.get("year") else "",
                    "url": f"https://www.europeana.eu/item{item.get('id', '')}",
                    "provider": item.get("dataProvider", [""])[0],
                    "country": item.get("country", [""])[0],
                }
                for item in items
            ]
        except requests.RequestException as e:
            logger.error(f"Europeana error: {e}")
            return []

    # ── Harvard Art Museums (free, needs key) ────────────────────────────────

    def _search_harvard(self, query: str) -> list[dict]:
        """Search Harvard Art Museums collection."""
        if not self.harvard_key:
            logger.warning("HARVARD_API_KEY not set, skipping.")
            return []

        logger.info(f"Searching Harvard Art Museums for: {query}")
        try:
            resp = requests.get(
                HARVARD_ENDPOINT,
                params={
                    "apikey": self.harvard_key,
                    "keyword": query,
                    "size": 3,
                    "fields": "title,dated,medium,url,primaryimageurl,people",
                },
                timeout=self.timeout,
            )
            resp.raise_for_status()
            records = resp.json().get("records", [])

            return [
                {
                    "source": "Harvard Art Museums",
                    "title": r.get("title"),
                    "period": r.get("dated"),
                    "medium": r.get("medium"),
                    "url": r.get("url"),
                    "image": r.get("primaryimageurl"),
                }
                for r in records
            ]
        except requests.RequestException as e:
            logger.error(f"Harvard API error: {e}")
            return []

    # ── Wikipedia ────────────────────────────────────────────────────────────

    def _search_wikipedia(self, query: str) -> str:
        """Fetch Wikipedia summary for context."""
        logger.info(f"Searching Wikipedia for: {query}")
        try:
            resp = requests.get(
                f"{WIKIPEDIA_ENDPOINT}/{query.replace(' ', '_')}",
                timeout=self.timeout,
            )
            if resp.ok:
                return resp.json().get("extract", "")
        except requests.RequestException:
            pass
        return ""

    # ── Serper (auction houses + stolen art) ─────────────────────────────────

    def _serper_search(self, query: str, num: int = 5) -> list[dict]:
        """Run a web search via Serper.dev."""
        if not self.serper_key:
            logger.warning("SERPER_API_KEY not set, skipping web search.")
            return []

        try:
            resp = requests.post(
                SERPER_ENDPOINT,
                headers={
                    "X-API-KEY": self.serper_key,
                    "Content-Type": "application/json",
                },
                json={"q": query, "num": num},
                timeout=self.timeout,
            )
            resp.raise_for_status()
            return resp.json().get("organic", [])
        except requests.RequestException as e:
            logger.error(f"Serper error for query '{query}': {e}")
            return []

    def _search_auction_houses(self, object_type: str, period: str) -> list[dict]:
        """Search Christie's and Sotheby's for auction comparables."""
        query = f"{object_type} {period} site:christies.com OR site:sothebys.com"
        results = self._serper_search(query, num=6)

        comparables = []
        price_pattern = __import__("re").compile(r"[\$£€]\s?([\d,]+(?:\.\d{1,2})?)")

        for r in results:
            snippet = r.get("snippet", "")
            prices = price_pattern.findall(snippet)
            comparables.append({
                "source": "Christie's/Sotheby's",
                "title": r.get("title"),
                "url": r.get("link"),
                "snippet": snippet,
                "price_found": prices[0].replace(",", "") if prices else None,
            })
        return comparables

    def _search_stolen_registries(self, object_type: str) -> list[dict]:
        """
        Search Interpol public database and Art Loss Register mentions.
        Uses SerpAPI to search their public-facing pages.
        """
        query = f"stolen {object_type} site:interpol.int OR site:artloss.com"
        results = self._serper_search(query, num=4)

        return [
            {
                "source": "Interpol/ALR",
                "title": r.get("title"),
                "url": r.get("link"),
                "snippet": r.get("snippet"),
            }
            for r in results
        ]

    def _search_publications(self, object_type: str, period: str) -> list[dict]:
        """Search for scholarly articles and press about the item type."""
        query = f'"{object_type}" "{period}" authentication provenance'
        results = self._serper_search(query, num=5)

        return [
            {
                "title": r.get("title"),
                "url": r.get("link"),
                "source": r.get("displayedLink"),
                "snippet": r.get("snippet"),
            }
            for r in results
        ]

    # ── scoring ───────────────────────────────────────────────────────────────

    def _compute_verdict(
        self,
        stolen_flags: list,
        museum_matches: int,
        auction_comparables: list,
    ) -> tuple[float, str, str]:
        """Compute final suspicion score and verdict."""
        score = 0.0
        notes = []

        if stolen_flags:
            score += 0.6
            notes.append(
                f"Possible match in stolen art registries ({len(stolen_flags)} results). "
                f"Manual verification strongly recommended."
            )

        if museum_matches > 0:
            notes.append(
                f"Found {museum_matches} similar items in museum collections — "
                f"useful for authentication comparison."
            )

        if not auction_comparables:
            score += 0.1
            notes.append("No auction comparables found — market value unverifiable.")
        else:
            notes.append(
                f"Found {len(auction_comparables)} auction comparables for valuation reference."
            )

        score = min(score, 1.0)

        if score >= 0.6:
            verdict = "stolen_risk"
        elif score >= 0.3:
            verdict = "flagged"
        else:
            verdict = "clear"

        return round(score, 4), verdict, " | ".join(notes) or "No issues detected."

    # ── public API ────────────────────────────────────────────────────────────

    def analyze(
        self,
        object_type: str,
        period: str,
        category: str,
    ) -> ComparativeSearchResult:
        """
        Run comparative web search for the identified item.

        Args:
            object_type : from VisionAnalysisResult.object_type
            period      : from VisionAnalysisResult.estimated_period
            category    : user-provided category
        """
        logger.info(
            f"Web comparative search | object='{object_type}' "
            f"period='{period}' category='{category}'"
        )

        query = f"{object_type} {period}"
        sources_checked = []

        # Run all searches
        met_results       = self._search_met(query);           sources_checked.append("Met Museum")
        europeana_results = self._search_europeana(query);     sources_checked.append("Europeana")
        harvard_results   = self._search_harvard(query);       sources_checked.append("Harvard Art Museums")
        wiki_context      = self._search_wikipedia(query);     sources_checked.append("Wikipedia")
        auction_comps     = self._search_auction_houses(object_type, period); sources_checked.append("Christie's/Sotheby's")
        stolen_flags      = self._search_stolen_registries(object_type);      sources_checked.append("Interpol/ALR")
        publications      = self._search_publications(object_type, period);   sources_checked.append("Web Publications")

        museum_matches = met_results + europeana_results + harvard_results

        # Extract best price estimate from auction comparables
        estimated_value = None
        for comp in auction_comps:
            if comp.get("price_found"):
                try:
                    estimated_value = float(comp["price_found"])
                    break
                except ValueError:
                    continue

        suspicion_score, verdict, notes = self._compute_verdict(
            stolen_flags, len(museum_matches), auction_comps
        )

        return ComparativeSearchResult(
            museum_matches=museum_matches,
            stolen_art_flags=stolen_flags,
            publications=publications,
            auction_comparables=auction_comps,
            wikipedia_context=wiki_context[:800] if wiki_context else "",
            estimated_value=estimated_value,
            suspicion_score=suspicion_score,
            verdict=verdict,
            notes=notes,
            sources_checked=sources_checked,
        )

        