from ..tools.authenticityTool.reverse_image_search import ReverseImageSearcher
from ..tools.authenticityTool.ai_image_detector import AIImageDetector
from ..tools.authenticityTool.vision_analyzer import VisionAnalyzer
from ..tools.authenticityTool.ela_detector import ELADetector
from ..tools.authenticityTool.exif_analysis import ExifAnalyzer
from ..tools.authenticityTool.web_comparative_search import WebComparativeSearcher
from google import genai
from dotenv import load_dotenv

load_dotenv()

class GeminiAutonomousAgent:
    def __init__(self, gemini_api_key, serpapi_key, imgbb_api_key, serper_api_key=None, openrouter_api_key=None):
        self.gemini_client = genai.Client(api_key=gemini_api_key)
        self.reverse_searcher = ReverseImageSearcher(serpapi_key=serpapi_key)
        self.ai_detector = AIImageDetector(model_type="umm-maybe")
        self.sdxl_detector = AIImageDetector(model_type="sdxl")
        self.vision_analyzer = VisionAnalyzer(openrouter_api_key=openrouter_api_key)
        self.ela_detector = ELADetector()
        self.exif_analyzer = ExifAnalyzer()
        self.comparative_searcher = WebComparativeSearcher(serper_api_key=serper_api_key)

    def _obj_to_dict(self, obj):
        """Convert result objects to JSON-serializable dicts."""
        from datetime import datetime, date
        if obj is None:
            return None
        if isinstance(obj, (datetime, date)):
            return obj.isoformat()
        if isinstance(obj, dict):
            return {k: self._obj_to_dict(v) for k, v in obj.items()}
        if isinstance(obj, (list, tuple)):
            return [self._obj_to_dict(x) for x in obj]
        if isinstance(obj, (str, int, float, bool)):
            return obj
        if hasattr(obj, "__dataclass_fields__"):
            return {f: self._obj_to_dict(getattr(obj, f)) for f in obj.__dataclass_fields__}
        if hasattr(obj, "__dict__"):
            return {k: self._obj_to_dict(v) for k, v in vars(obj).items()}
        return str(obj)

    def run(self, image_path, category=None, description=None):
        # Step 1: ELA and EXIF analysis
        ela_result = self.ela_detector.analyze(image_path)
        exif_result = self.exif_analyzer.analyze(image_path)

        # Step 2: Initial reverse image search (web presence check)
        reverse_result = self.reverse_searcher.analyze(image_path)

        # Rule-based override: si les signaux techniques sont bons, on procède sans demander à Gemini
        # (évite les faux positifs quand ELA dit "clean" mais la note contient "suggests manipulation")
        ela_verdict_ok = getattr(ela_result, 'verdict', '') in ("clean", "")
        ela_score_low = ela_result.suspicion_score < 0.5
        ela_very_low = ela_result.suspicion_score < 0.4  # Très rassurant → ignorer reverse
        reverse_score_ok = getattr(reverse_result, 'suspicion_score', 1.0) < 0.8  # Seuil relevé (0.6→0.8)

        if ela_verdict_ok and ela_very_low:
            # ELA très rassurant → procéder même si reverse est élevé (produits courants = souvent trouvés en ligne)
            pass
        elif ela_verdict_ok and ela_score_low and reverse_score_ok:
            # Signaux techniques OK → procéder directement à l'étape AI detection
            pass
        else:
            # Sinon, demander à Gemini de décider
            suspicion_explanation = (
                "Suspicion score is calculated based on the number of matches found online, "
                "the presence of matches on suspicious domains (e.g., stock photo or e-commerce sites), "
                "and whether the image appears in active product listings."
            )
            prompt = f"""
You are an autonomous agent for image validation on an auction platform.

=== ELA ANALYSIS (Error Level Analysis) ===
VERDICT: {getattr(ela_result, 'verdict', 'unknown')}  ← This is the overall conclusion (clean/suspicious/likely_manipulated)
Suspicion score: {ela_result.suspicion_score:.2f} (0=clean, 1=highly suspicious)
Notes: {ela_result.notes}
IMPORTANT: If verdict is "clean" AND suspicion_score < 0.5, the notes may mention "suggests manipulation" due to high contrast—this is often a FALSE POSITIVE for legitimate photos. Do NOT stop.

=== EXIF METADATA ===
{exif_result.get('message')}
Has EXIF: {exif_result.get('has_exif', 'unknown')}
NOTE: Missing EXIF is COMMON for screenshots, web images, converted formats—do NOT stop for this alone.

=== REVERSE IMAGE SEARCH ===
{reverse_result.notes}
Found online: {reverse_result.found_online}
Reverse suspicion score: {getattr(reverse_result, 'suspicion_score', 0):.2f}
{suspicion_explanation}

=== YOUR DECISION ===
Reply with ONLY "stop" if: ELA verdict is "likely_manipulated" OR ELA suspicion >= 0.6 OR reverse suspicion >= 0.85.
Finding product images online (PCs, electronics, common items) is EXPECTED—do NOT stop for reverse alone unless suspicion >= 0.85.
Reply with "proceed" if: ELA verdict is "clean" with score < 0.5, OR signals are ambiguous. When in doubt, PROCEED to AI detection.
"""
            gemini_decision = self.gemini_client.models.generate_content(
                model='gemini-2.5-flash',
                contents=prompt
            )
            gemini_text = (gemini_decision.text or "").lower() if hasattr(gemini_decision, 'text') and gemini_decision.text else ""
            if "stop" in gemini_text and "proceed" not in gemini_text:
                return {
                    "verdict": "duplicate_or_manipulated",
                    "details": {
                        "ela": self._obj_to_dict(ela_result),
                        "exif": self._obj_to_dict(exif_result),
                        "reverse": self._obj_to_dict(reverse_result)
                    }
                }

        # Step 4: AI detection
        ai_result = self.ai_detector.analyze(image_path)
        sdxl_result = self.sdxl_detector.analyze(image_path)

        # Règle: si les deux modèles AI ont un score bas, on procède sans demander à Gemini
        ai_scores_low = ai_result.suspicion_score < 0.7 and sdxl_result.suspicion_score < 0.7
        if ai_scores_low:
            pass  # Procéder à Vision + raisonnement authenticité
        else:
            ai_prompt = f"""
Step 4: AI detection results (detects if image is AI-generated):
umm-maybe: {ai_result.notes}, suspicion score: {ai_result.suspicion_score:.2f}
sdxl: {sdxl_result.notes}, suspicion score: {sdxl_result.suspicion_score:.2f}
Note: SDXL is more reliable for photos; umm-maybe for artistic images.
Reply "stop" ONLY if BOTH models have suspicion_score >= 0.7 (clearly AI-generated).
Reply "proceed" if scores are low (< 0.6) or ambiguous—real objects (antiques, arts décoratifs) often score mid-range. When in doubt, PROCEED.
"""
            gemini_decision = self.gemini_client.models.generate_content(
                model='gemini-2.5-flash',
                contents=ai_prompt
            )
            gemini_text = (gemini_decision.text or "").lower() if hasattr(gemini_decision, 'text') and gemini_decision.text else ""
            if "stop" in gemini_text and "proceed" not in gemini_text:
                return {
                    "verdict": "ai_generated",
                    "details": {
                        "ela": self._obj_to_dict(ela_result),
                        "exif": self._obj_to_dict(exif_result),
                        "reverse": self._obj_to_dict(reverse_result),
                        "ai": {"umm-maybe": self._obj_to_dict(ai_result), "sdxl": self._obj_to_dict(sdxl_result)}
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
You are an expert art and collectibles authenticator.
Analyze the AUTHENTICITY of the item using the following evidence:

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
        openrouter_api_key=openrouter_api_key
    )

    result = agent.run(image_path, category=category, description=description)
    print("\n" + "="*60)
    print("         IMAGE VALIDATION AGENT RESULT")
    print("="*60)
    print(f"Verdict: {result.get('verdict', 'N/A').upper()}")
    
    if result.get('verdict') == 'validated':
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