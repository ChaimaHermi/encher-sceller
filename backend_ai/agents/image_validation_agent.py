from ..tools.reverse_image_search import ReverseImageSearcher
from ..tools.ai_image_detector import AIImageDetector
from ..tools.vision_analyzer import VisionAnalyzer
from ..tools.ela_detector import ELADetector
from ..tools.exif_analysis import ExifAnalyzer
from ..tools.web_comparative_search import WebComparativeSearcher
from ..tools.duplicate_check import DuplicateCheckerQdrant
from google import genai
from dotenv import load_dotenv

load_dotenv()

class GeminiAutonomousAgent:
    def __init__(self, gemini_api_key, serpapi_key, imgbb_api_key, serper_api_key=None, qdrant_url="http://localhost:6333", qdrant_api_key=None, openrouter_api_key=None):
        self.gemini_client = genai.Client(api_key=gemini_api_key)
        self.reverse_searcher = ReverseImageSearcher(serpapi_key=serpapi_key)
        self.ai_detector = AIImageDetector(model_type="umm-maybe")
        self.sdxl_detector = AIImageDetector(model_type="sdxl")
        self.vision_analyzer = VisionAnalyzer(openrouter_api_key=openrouter_api_key)
        self.ela_detector = ELADetector()
        self.exif_analyzer = ExifAnalyzer()
        self.comparative_searcher = WebComparativeSearcher(serper_api_key=serper_api_key)
        self.duplicate_checker = DuplicateCheckerQdrant(url=qdrant_url, api_key=qdrant_api_key)

    def run(self, image_path, category=None, description=None):
        # Step 0: Duplicate check against vector DB (Qdrant)
        is_duplicate, duplicate_payload = self.duplicate_checker.check_duplicate(image_path)
        if is_duplicate:
            return {
                "verdict": "duplicate",
                "details": {
                    "source": "vector_db",
                    "matched_filename": duplicate_payload.get("filename") if duplicate_payload else None,
                    "phash": duplicate_payload.get("phash") if duplicate_payload else None
                }
            }

        # Image is not a duplicate, add it to the vector DB for future checks
        self.duplicate_checker.add_to_db(image_path, metadata={"category": category, "description": description})

        # Step 1: ELA and EXIF analysis
        ela_result = self.ela_detector.analyze(image_path)
        exif_result = self.exif_analyzer.analyze(image_path)

        # Step 2: Initial reverse image search (web presence check)
        reverse_result = self.reverse_searcher.analyze(image_path)

        # Explain suspicion score calculation for reverse image search
        suspicion_explanation = (
            "Suspicion score is calculated based on the number of matches found online, "
            "the presence of matches on suspicious domains (e.g., stock photo or e-commerce sites), "
            "and whether the image appears in active product listings. "
            "A higher score means the image is more likely to be stolen, fake, or duplicated."
        )

        prompt = f"""
You are an autonomous agent for image validation on an auction platform.

Step 1: Duplicate check: If the image matches a previously uploaded image or is found online with a high suspicion score, it is considered a duplicate and the process stops.

Step 2: ELA and EXIF analysis:
ELA result: {ela_result.notes} (Suspicion score: {ela_result.suspicion_score})
EXIF: {exif_result.get('message')}

Step 3: Reverse image search:
{reverse_result.notes}
Found online: {reverse_result.found_online}, Suspicion score: {reverse_result.suspicion_score}
How suspicion score is calculated: {suspicion_explanation}

If duplicate is found and suspicion score is high, or ELA/EXIF indicate manipulation, stop and return a high suspicion verdict.
Otherwise, proceed to AI detection.
"""
        gemini_decision = self.gemini_client.models.generate_content(
            model='gemini-2.5-flash',
            contents=prompt
        )
        if "stop" in gemini_decision.text.lower():
            return {
                "verdict": "duplicate_or_manipulated",
                "details": {
                    "ela": ela_result,
                    "exif": exif_result,
                    "reverse": reverse_result
                }
            }

        # Step 4: AI detection
        ai_result = self.ai_detector.analyze(image_path)
        sdxl_result = self.sdxl_detector.analyze(image_path)
        ai_prompt = f"""
Step 4: AI detection results:
umm-maybe: {ai_result.notes}, suspicion score: {ai_result.suspicion_score}
sdxl: {sdxl_result.notes}, suspicion score: {sdxl_result.suspicion_score}
Note: The SDXL model is generally more reliable for photographic and general images, while umm-maybe is best for artistic/creative images. Prioritize SDXL's result for most cases.
If SDXL suspicion score is high, stop and return verdict.
Otherwise, proceed to category/description reasoning.
"""
        gemini_decision = self.gemini_client.models.generate_content(
            model='gemini-2.5-flash',
            contents=ai_prompt
        )
        if "stop" in gemini_decision.text.lower():
            return {
                "verdict": "ai_generated",
                "details": {
                    "ela": ela_result,
                    "exif": exif_result,
                    "reverse": reverse_result,
                    "ai": {"umm-maybe": ai_result, "sdxl": sdxl_result}
                }
            }

        # Step 5: Vision analysis - detailed visual inspection
        vision_result = self.vision_analyzer.analyze(image_path)

        # Step 6: Comparative web search - search for similar items online
        is_artwork = False
        if category and category.lower() in ["artwork", "painting", "sculpture", "drawing", "print", "photograph"]:
            is_artwork = True
        if description and any(word in description.lower() for word in ["artwork", "painting", "sculpture", "museum", "gallery", "canvas", "oil", "watercolor", "drawing", "print", "photograph"]):
            is_artwork = True

        # Build search query from category, description, and vision analysis
        search_query = " ".join(filter(None, [category, description]))
        if vision_result and hasattr(vision_result, 'full_report'):
            # Extract key visual descriptors from vision analysis for better search
            search_query += f" {vision_result.full_report[:200]}" if vision_result.full_report else ""
        
        comparative_result = None
        if search_query.strip():
            comparative_result = self.comparative_searcher.search(search_query.strip())

        # Step 7: Authenticity Reasoning - LLM reasons on item authenticity using vision + comparative results
        authenticity_prompt = f"""
You are an expert art and collectibles authenticator. The image has passed uniqueness verification (not a duplicate).
Now analyze the AUTHENTICITY of the item using the following evidence:

=== VISION ANALYSIS (AI Visual Inspection) ===
{vision_result.full_report if vision_result else 'No vision analysis available'}

=== COMPARATIVE WEB SEARCH ===
{comparative_result.notes if comparative_result else 'No comparative results found'}
Found matches: {comparative_result.match_count if comparative_result else 0}
Suspicion indicators: {comparative_result.suspicious_sources if comparative_result and hasattr(comparative_result, 'suspicious_sources') else 'None'}

=== ITEM CONTEXT ===
Category: {category or 'Unknown'}
Seller Description: {description or 'No description provided'}
Is Artwork: {is_artwork}

=== PREVIOUS ANALYSIS RESULTS ===
- ELA (Error Level Analysis): Suspicion {ela_result.suspicion_score:.2f} - {ela_result.notes}
- EXIF Metadata: {exif_result.get('message', 'No EXIF data')}
- Reverse Image Search: Found online={reverse_result.found_online}, Suspicion={reverse_result.suspicion_score:.2f}, Avg Similarity={getattr(reverse_result, 'avg_similarity', 'N/A')}
- AI Detection: SDXL={sdxl_result.suspicion_score:.2f}, UMM-Maybe={ai_result.suspicion_score:.2f}

=== YOUR TASK ===
Based on the vision analysis and web comparison results, reason about the item's authenticity:

1. **Visual Assessment**: What does the vision analysis reveal about quality, materials, craftsmanship, and potential red flags?

2. **Market Context**: Does the comparative search show this item in known collections, auction houses, or suspicious marketplaces?

3. **Consistency Check**: Does the seller's description match what is visually observed?

4. **Risk Indicators**: 
   - If item appears in museum/major collection → likely fake or stolen
   - If item appears on stock photo sites → suspicious
   - If visual quality doesn't match claimed provenance → potential fraud

5. **Final Verdict**:
   - Authenticity Probability (0.0 to 1.0)
   - Confidence Level (low/medium/high)
   - Key reasoning points
   - Recommended action (approve/reject/request more info)

Provide your analysis in a structured format.
"""
        
        authenticity_reasoning = self.gemini_client.models.generate_content(
            model='gemini-2.5-flash',
            contents=authenticity_prompt
        )

        # Parse authenticity probability from response if possible
        authenticity_text = authenticity_reasoning.text
        
        return {
            "verdict": "validated",
            "authenticity_reasoning": authenticity_text,
            "details": {
                "ela": {
                    "suspicion_score": ela_result.suspicion_score,
                    "notes": ela_result.notes
                },
                "exif": exif_result,
                "reverse_search": {
                    "found_online": reverse_result.found_online,
                    "suspicion_score": reverse_result.suspicion_score,
                    "match_count": reverse_result.match_count,
                    "avg_similarity": getattr(reverse_result, 'avg_similarity', None)
                },
                "ai_detection": {
                    "sdxl": {"suspicion_score": sdxl_result.suspicion_score, "notes": sdxl_result.notes},
                    "umm_maybe": {"suspicion_score": ai_result.suspicion_score, "notes": ai_result.notes}
                },
                "vision_analysis": {
                    "full_report": vision_result.full_report if vision_result else None,
                    "suspicion_score": vision_result.suspicion_score if vision_result else None
                },
                "comparative_search": {
                    "notes": comparative_result.notes if comparative_result else None,
                    "match_count": comparative_result.match_count if comparative_result else 0
                } if comparative_result else None
            }
        }


# --- Main block for testing ---
if __name__ == "__main__":
    import os
    import sys
    # Example usage: python image_validation_agent.py <image_path> <category> <description>
    gemini_api_key = os.getenv("GEMINI_API_KEY")
    serpapi_key = os.getenv("SERPAPI_KEY")
    imgbb_api_key = os.getenv("IMGBB_API_KEY")
    serper_api_key = os.getenv("SERPER_API_KEY")
    qdrant_url = os.getenv("QDRANT_URL", "http://localhost:6333")
    qdrant_api_key = os.getenv("QDRANT_API_KEY")
    openrouter_api_key = os.getenv("OPENROUTER_API_KEY")

    if len(sys.argv) < 2:
        print("Usage: python image_validation_agent.py <image_path> [category] [description]")
        sys.exit(1)

    image_path = sys.argv[1]
    category = sys.argv[2] if len(sys.argv) > 2 else None
    description = sys.argv[3] if len(sys.argv) > 3 else None

    agent = GeminiAutonomousAgent(
        gemini_api_key=gemini_api_key,
        serpapi_key=serpapi_key,
        imgbb_api_key=imgbb_api_key,
        serper_api_key=serper_api_key,
        qdrant_url=qdrant_url,
        qdrant_api_key=qdrant_api_key,
        openrouter_api_key=openrouter_api_key
    )

    result = agent.run(image_path, category=category, description=description)
    print("\n" + "="*60)
    print("         IMAGE VALIDATION AGENT RESULT")
    print("="*60)
    print(f"Verdict: {result.get('verdict', 'N/A').upper()}")
    
    if result.get('verdict') == 'duplicate':
        print(f"\nDuplicate detected!")
        print(f"  Matched file: {result['details'].get('matched_filename')}")
        print(f"  pHash: {result['details'].get('phash')}")
    elif result.get('verdict') == 'validated':
        print("\n--- Authenticity Reasoning ---")
        print(result.get('authenticity_reasoning', 'No reasoning available'))
        print("\n--- Tool Results Summary ---")
        details = result.get('details', {})
        if details.get('ela'):
            print(f"ELA: Suspicion {details['ela'].get('suspicion_score', 0):.2f}")
        if details.get('reverse_search'):
            rs = details['reverse_search']
            print(f"Reverse Search: Found={rs.get('found_online')}, Suspicion={rs.get('suspicion_score', 0):.2f}, Matches={rs.get('match_count')}")
        if details.get('ai_detection'):
            ai = details['ai_detection']
            print(f"AI Detection: SDXL={ai['sdxl'].get('suspicion_score', 0):.2f}, UMM={ai['umm_maybe'].get('suspicion_score', 0):.2f}")
        if details.get('vision_analysis') and details['vision_analysis'].get('full_report'):
            print(f"Vision: Suspicion {details['vision_analysis'].get('suspicion_score', 0):.2f}")
    else:
        print(f"\nDetails: {result.get('details', {})}")