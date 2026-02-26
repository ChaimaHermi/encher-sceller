from agents.base_agent import BaseAgent
from tools.groq_client import groq_client
from prompts.auction_prompt import AUCTION_PROMPT_TEMPLATE
from config.settings import MODEL_NAME
import base64
import os
import json
import re
from typing import List, Union

class VisionAgent(BaseAgent):
    def __init__(self):
        super().__init__("vision_agent")

    # ------------------------------
    # Helper: encode local image to base64
    # ------------------------------
    def _encode_image(self, image_path: str) -> str:
        with open(image_path, "rb") as f:
            return base64.b64encode(f.read()).decode()

    # ------------------------------
    # Helper: extract JSON from model output
    # ------------------------------
    def _extract_json(self, text: str):
        try:
            return json.loads(text)
        except:
            pass

        match = re.search(r"\{.*\}", text, re.DOTALL)
        if match:
            try:
                return json.loads(match.group())
            except:
                pass

        return None

    # ------------------------------
    # Helper: repair invalid JSON via Groq
    # ------------------------------
    def _repair_json(self, bad_output: str):
        repair_prompt = f"""
Convert the following text into VALID JSON only.
Return only JSON.

Text:
{bad_output}
"""
        completion = groq_client.chat.completions.create(
            model=MODEL_NAME,
            messages=[{"role": "user", "content": repair_prompt}],
            temperature=0,
        )

        return self._extract_json(completion.choices[0].message.content)

    # ------------------------------
    # Main function: accepts 1 or multiple images
    # ------------------------------
    def run(self, images: Union[str, List[str]], user_description: str) -> dict:
        # allow a single string input
        if isinstance(images, str):
            images = [images]

        # encode or use URLs
        images_content = []
        for img in images:
            if os.path.exists(img):
                image_b64 = self._encode_image(img)
                images_content.append({
                    "type": "image_url",
                    "image_url": {"url": f"data:image/jpeg;base64,{image_b64}"},
                })
            else:
                images_content.append({
                    "type": "image_url",
                    "image_url": {"url": img},
                })

        # insert user description into prompt
        prompt = AUCTION_PROMPT_TEMPLATE.format(user_description=user_description)

        # send request to Groq
        completion = groq_client.chat.completions.create(
            model=MODEL_NAME,
            messages=[{
                "role": "user",
                "content": [
                    {"type": "text", "text": prompt},
                    *images_content,
                ],
            }],
            temperature=0,  # deterministic output
            max_completion_tokens=1024,
        )

        # extract text from model
        text = completion.choices[0].message.content.strip()

        # try parsing JSON
        data = self._extract_json(text)

        # repair if invalid
        if not data:
            data = self._repair_json(text)

        if data:
            return data

        return {"error": "INVALID_JSON", "raw": text}