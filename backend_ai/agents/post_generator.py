"""
Auction Post Generator using two-stage LLM pipeline:
1. OpenRouter Vision (Mistral) - Analyzes image and generates detailed item description
2. Gemini - Takes the description and generates a compelling auction post

This separation allows the vision model to focus on accurate description
while Gemini excels at creative copywriting.
"""

import base64
import logging
import os
import re
import json
from dataclasses import dataclass
from typing import Optional, Dict, Any
import requests
from PIL import Image
from dotenv import load_dotenv
from google import genai

load_dotenv()
logger = logging.getLogger(__name__)


@dataclass
class AuctionPost:
    """Generated auction announcement post."""
    title: str
    description: str
    highlights: list[str]
    estimated_value: str
    condition_summary: str
    authenticity_statement: str
    call_to_action: str
    hashtags: list[str]
    full_post: str
    engine_used: str


# Prompt for vision LLM to describe the item
VISION_DESCRIPTION_PROMPT = """
You are an expert art and antiques appraiser. Analyze this image and provide a detailed description of the item.

Provide a comprehensive description including:
1. **Object Type**: What is this item? (e.g., oil painting, pocket watch, sculpture)
2. **Visual Details**: Colors, textures, patterns, composition
3. **Materials**: What materials appear to be used?
4. **Style/Period**: Artistic style, era, or design period if identifiable
5. **Condition**: Visible wear, damage, or preservation state
6. **Craftsmanship**: Quality of work, notable techniques
7. **Signatures/Marks**: Any visible signatures, hallmarks, or stamps
8. **Dimensions**: Estimated size if possible
9. **Notable Features**: Anything unique or particularly valuable
10. **Overall Assessment**: Brief professional opinion on the piece

Be detailed and specific. This description will be used to create an auction listing.
"""

# Prompt for Gemini to generate the auction post
POST_GENERATION_PROMPT = """
You are an expert auction house copywriter. Generate a compelling auction announcement post based on the item description provided.

You MUST respond in this exact JSON format and nothing else:
{
  "title": "Attention-grabbing title for the auction (max 80 chars)",
  "description": "Engaging 2-3 paragraph description highlighting the item's appeal, history, and uniqueness",
  "highlights": ["Key feature 1", "Key feature 2", "Key feature 3"],
  "estimated_value": "Price range or starting bid suggestion",
  "condition_summary": "Brief condition assessment",
  "authenticity_statement": "Statement about verification/authenticity",
  "call_to_action": "Compelling call to action for bidders",
  "hashtags": ["relevant", "hashtags", "for", "social", "media"]
}

Guidelines:
- Write in a professional yet engaging tone
- Emphasize rarity, craftsmanship, provenance, or historical significance
- Be honest about condition but frame positively
- Create urgency without being pushy
- Use descriptive language that appeals to collectors
- Include relevant auction/collecting hashtags
"""





class AuctionPostGenerator:
    """
    Two-stage auction post generator:
    1. Vision LLM (OpenRouter Mistral) - Analyzes image and generates detailed description
    2. Gemini LLM - Takes description and creates compelling auction post
    
    This separation leverages each model's strengths:
    - Vision model: Accurate visual analysis and description
    - Gemini: Creative copywriting and marketing language
    """

    def __init__(
        self,
        openrouter_api_key: Optional[str] = None,
        gemini_api_key: Optional[str] = None,
        vision_model: str = "mistralai/ministral-14b-2512",
        max_image_size: tuple = (1024, 1024),
    ):
        self.openrouter_api_key = openrouter_api_key or os.getenv("OPENROUTER_API_KEY")
        self.gemini_api_key = gemini_api_key or os.getenv("GEMINI_API_KEY")
        self.vision_model = vision_model
        self.max_image_size = max_image_size
        self.openrouter_url = "https://openrouter.ai/api/v1/chat/completions"
        
        # Initialize Gemini client
        if self.gemini_api_key:
            self.gemini_client = genai.Client(api_key=self.gemini_api_key)
        else:
            self.gemini_client = None
            logger.warning("GEMINI_API_KEY not set, post generation will be limited")

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

    def _call_openrouter(self, messages: list) -> dict:
        """Call OpenRouter API for vision description."""
        if not self.openrouter_api_key:
            logger.error("OPENROUTER_API_KEY not set.")
            return {}

        headers = {
            "Authorization": f"Bearer {self.openrouter_api_key}",
            "Content-Type": "application/json",
            "HTTP-Referer": "https://auction-platform.local",
            "X-Title": "Auction Post Generator",
        }

        payload = {
            "model": self.vision_model,
            "messages": messages,
            "temperature": 0.5,
            "max_tokens": 2000,
        }

        try:
            resp = requests.post(
                self.openrouter_url,
                headers=headers,
                json=payload,
                timeout=60,
            )
            resp.raise_for_status()
            data = resp.json()
            raw = data["choices"][0]["message"]["content"]
            return {"raw": raw, "engine": "openrouter_vision"}
        except requests.RequestException as e:
            logger.error(f"OpenRouter request failed: {e}")
            if hasattr(e, 'response') and e.response is not None:
                logger.error(f"Response: {e.response.text}")
            return {}
        except (KeyError, IndexError) as e:
            logger.error(f"Failed to parse OpenRouter response: {e}")
            return {}

    def _call_gemini(self, prompt: str) -> dict:
        """Call Gemini API for post generation."""
        if not self.gemini_client:
            logger.error("Gemini client not initialized.")
            return {}

        try:
            response = self.gemini_client.models.generate_content(
                model='gemini-2.5-flash',
                contents=prompt
            )
            return {"raw": response.text, "engine": "gemini"}
        except Exception as e:
            logger.error(f"Gemini request failed: {e}")
            return {}

    def _get_vision_description(self, image_path: str, additional_context: Optional[str] = None) -> str:
        """Use vision LLM to generate detailed item description from image."""
        logger.info(f"Getting vision description for: {image_path}")

        image_data_url = self._prepare_image_base64(image_path)
        
        prompt = VISION_DESCRIPTION_PROMPT
        if additional_context:
            prompt += f"\n\nAdditional context from seller:\n{additional_context}"

        messages = [
            {
                "role": "user",
                "content": [
                    {"type": "text", "text": prompt},
                    {"type": "image_url", "image_url": {"url": image_data_url}}
                ]
            }
        ]

        result = self._call_openrouter(messages)
        if result and result.get("raw"):
            logger.info("Vision description generated successfully")
            return result["raw"]
        
        return "Unable to generate item description from image."

    def _generate_post_with_gemini(self, item_description: str, category: Optional[str] = None, starting_bid: Optional[float] = None) -> dict:
        """Use Gemini to generate auction post from item description."""
        logger.info("Generating auction post with Gemini...")

        context_parts = [f"Item Description:\n{item_description}"]
        
        if category:
            context_parts.append(f"\nCategory: {category}")
        if starting_bid:
            context_parts.append(f"\nStarting Bid: ${starting_bid:,.2f}")

        full_prompt = f"{POST_GENERATION_PROMPT}\n\n{''.join(context_parts)}"

        result = self._call_gemini(full_prompt)
        return result

    def _parse_response(self, raw: str) -> dict:
        """Parse JSON response from model."""
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

        logger.warning("Could not parse model JSON response.")
        return {}

    def _build_full_post(self, parsed: dict) -> str:
        """Build formatted full post from parsed components."""
        lines = []
        
        # Title
        lines.append(f"🔨 {parsed.get('title', 'Exclusive Auction Item')}")
        lines.append("")
        
        # Description
        lines.append(parsed.get('description', ''))
        lines.append("")
        
        # Highlights
        highlights = parsed.get('highlights', [])
        if highlights:
            lines.append("✨ HIGHLIGHTS:")
            for h in highlights:
                lines.append(f"  • {h}")
            lines.append("")
        
        # Value & Condition
        if parsed.get('estimated_value'):
            lines.append(f"💰 Estimated Value: {parsed['estimated_value']}")
        if parsed.get('condition_summary'):
            lines.append(f"📋 Condition: {parsed['condition_summary']}")
        lines.append("")
        
        # Authenticity
        if parsed.get('authenticity_statement'):
            lines.append(f"✅ {parsed['authenticity_statement']}")
            lines.append("")
        
        # Call to action
        if parsed.get('call_to_action'):
            lines.append(f"👉 {parsed['call_to_action']}")
            lines.append("")
        
        # Hashtags
        hashtags = parsed.get('hashtags', [])
        if hashtags:
            lines.append(" ".join(f"#{tag}" for tag in hashtags))
        
        return "\n".join(lines)

    def _build_result(self, parsed: dict, engine: str) -> AuctionPost:
        """Build AuctionPost from parsed model output."""
        full_post = self._build_full_post(parsed)
        
        return AuctionPost(
            title=parsed.get("title", "Auction Item"),
            description=parsed.get("description", ""),
            highlights=parsed.get("highlights", []),
            estimated_value=parsed.get("estimated_value", "Contact for estimate"),
            condition_summary=parsed.get("condition_summary", "See description"),
            authenticity_statement=parsed.get("authenticity_statement", ""),
            call_to_action=parsed.get("call_to_action", "Place your bid now!"),
            hashtags=parsed.get("hashtags", []),
            full_post=full_post,
            engine_used=engine,
        )

    def generate_from_image(
        self,
        image_path: str,
        category: Optional[str] = None,
        additional_context: Optional[str] = None,
        starting_bid: Optional[float] = None,
    ) -> AuctionPost:
        """
        Generate auction post using two-stage LLM pipeline:
        1. Vision LLM (OpenRouter) analyzes image and generates description
        2. Gemini takes the description and creates compelling auction post
        
        Args:
            image_path: Path to item image
            category: Item category
            additional_context: Optional extra context (seller notes, etc.)
            starting_bid: Optional starting bid amount
        """
        logger.info(f"Generating post from image (two-stage): {image_path}")

        # Stage 1: Get detailed description from vision LLM
        vision_description = self._get_vision_description(image_path, additional_context)
        logger.info(f"Vision description:\n{vision_description[:200]}...")

        # Stage 2: Generate post with Gemini
        result = self._generate_post_with_gemini(vision_description, category, starting_bid)
        
        if result and result.get("raw"):
            parsed = self._parse_response(result["raw"])
            if parsed:
                return self._build_result(parsed, "vision+gemini")

        # Fallback
        return AuctionPost(
            title="Auction Item",
            description=vision_description[:500] if vision_description else "Details coming soon.",
            highlights=[],
            estimated_value=f"Starting at ${starting_bid:,.2f}" if starting_bid else "Contact for estimate",
            condition_summary="See photos",
            authenticity_statement="",
            call_to_action="Stay tuned for more details!",
            hashtags=["auction"],
            full_post=f"🔨 Auction Item\n\n{vision_description[:500] if vision_description else 'Details coming soon.'}",
            engine_used="vision_only",
        )

    def generate_from_details(
        self,
        item_name: str,
        category: str,
        description: str,
        validation_result: Optional[Dict[str, Any]] = None,
        starting_bid: Optional[float] = None,
    ) -> AuctionPost:
        """
        Generate auction post from item details using Gemini.
        
        Args:
            item_name: Name/title of item
            category: Item category (Art, Jewelry, Collectibles, etc.)
            description: Seller's description
            validation_result: Optional validation agent results
            starting_bid: Optional starting bid amount
        """
        logger.info(f"Generating post for: {item_name}")

        context_parts = [
            f"Item Name: {item_name}",
            f"Category: {category}",
            f"Seller Description: {description}",
        ]
        
        if starting_bid:
            context_parts.append(f"Starting Bid: ${starting_bid:,.2f}")
        
        if validation_result:
            details = validation_result.get('details', {})
            
            # Add vision analysis if available
            vision = details.get('vision_analysis', {})
            if vision:
                context_parts.append(f"\nVision Analysis:")
                context_parts.append(f"  Object Type: {vision.get('object_type', 'N/A')}")
                context_parts.append(f"  Estimated Period: {vision.get('estimated_period', 'N/A')}")
                context_parts.append(f"  Authenticity Score: {vision.get('authenticity_score', 'N/A')}")
            
            # Add authenticity reasoning if available
            if validation_result.get('authenticity_reasoning'):
                context_parts.append(f"\nAuthenticity Assessment:\n{validation_result['authenticity_reasoning'][:500]}")

        full_description = "\n".join(context_parts)
        
        # Use Gemini to generate the post
        result = self._generate_post_with_gemini(full_description, category, starting_bid)
        if result and result.get("raw"):
            parsed = self._parse_response(result["raw"])
            if parsed:
                return self._build_result(parsed, "gemini")

        # Fallback
        return AuctionPost(
            title=f"Auction: {item_name}",
            description=description,
            highlights=[],
            estimated_value=f"Starting at ${starting_bid:,.2f}" if starting_bid else "Contact for estimate",
            condition_summary="See description",
            authenticity_statement="",
            call_to_action="Place your bid now!",
            hashtags=["auction", category.lower().replace(" ", "")],
            full_post=f"🔨 Auction: {item_name}\n\n{description}",
            engine_used="none",
        )

    def generate_combined(
        self,
        image_path: str,
        item_name: str,
        category: str,
        description: str,
        validation_result: Optional[Dict[str, Any]] = None,
        starting_bid: Optional[float] = None,
    ) -> AuctionPost:
        """
        Generate auction post using two-stage pipeline with both image and item details.
        Best quality results by combining vision analysis with seller information.
        
        Stage 1: Vision LLM analyzes image and generates description
        Stage 2: Gemini combines vision description + seller details to create post
        """
        logger.info(f"Generating combined post for: {item_name}")

        # Stage 1: Get detailed description from vision LLM
        additional_context = f"Item Name: {item_name}\nCategory: {category}\nSeller Description: {description}"
        vision_description = self._get_vision_description(image_path, additional_context)
        logger.info(f"Vision description:\n{vision_description[:200]}...")

        # Combine vision description with seller details and validation results
        combined_description = f"""
=== VISION ANALYSIS (AI Visual Inspection) ===
{vision_description}

=== SELLER PROVIDED INFORMATION ===
Item Name: {item_name}
Category: {category}
Description: {description}
"""
        
        if validation_result:
            details = validation_result.get('details', {})
            vision = details.get('vision_analysis', {})
            if vision and vision.get('full_report'):
                combined_description += f"\n=== EXPERT ASSESSMENT ===\n{vision['full_report'][:300]}"
            if validation_result.get('authenticity_reasoning'):
                combined_description += f"\n\n✓ Authenticity Verified: Item has passed multi-stage validation."

        # Stage 2: Generate post with Gemini
        result = self._generate_post_with_gemini(combined_description, category, starting_bid)
        
        if result and result.get("raw"):
            parsed = self._parse_response(result["raw"])
            if parsed:
                return self._build_result(parsed, "vision+gemini")

        # Fallback to text-only generation
        return self.generate_from_details(item_name, category, description, validation_result, starting_bid)


# ----------------------------------------
# Example usage for testing
if __name__ == "__main__":
    import sys
    logging.basicConfig(level=logging.INFO)

    generator = AuctionPostGenerator()

    if len(sys.argv) > 1:
        # Image-based generation
        image_path = sys.argv[1]
        category = sys.argv[2] if len(sys.argv) > 2 else "Collectible"
        description = sys.argv[3] if len(sys.argv) > 3 else ""
        
        if description:
            post = generator.generate_combined(
                image_path=image_path,
                item_name="Auction Item",
                category=category,
                description=description,
            )
        else:
            post = generator.generate_from_image(image_path, category=category)
    else:
        # Demo with text-only
        post = generator.generate_from_details(
            item_name="Vintage Pocket Watch",
            category="Watches",
            description="Beautiful antique pocket watch from the 1920s. Gold-filled case with intricate engraving. Runs perfectly.",
            starting_bid=500.00,
        )

    print("\n" + "="*60)
    print("         GENERATED AUCTION POST")
    print("="*60)
    print(f"\nEngine: {post.engine_used}")
    print("\n--- FULL POST ---")
    print(post.full_post)
    print("\n--- COMPONENTS ---")
    print(f"Title: {post.title}")
    print(f"Value: {post.estimated_value}")
    print(f"Condition: {post.condition_summary}")
    print(f"Highlights: {', '.join(post.highlights)}")
    print(f"Hashtags: {' '.join('#' + h for h in post.hashtags)}")
