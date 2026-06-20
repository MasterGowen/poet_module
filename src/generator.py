import httpx
import json
import re
import logging
from pydantic_settings import BaseSettings
from typing import Dict, Any, Optional

logger = logging.getLogger(__name__)

class Settings(BaseSettings):
    API_KEY: str
    API_ENDPOINT: str
    MODEL_NAME: str

    class Config:
        env_file = ".env"
        env_file_encoding = "utf-8"

class PoetryGenerator:
    def __init__(self, settings: Settings):
        self.settings = settings
        self.client = httpx.Client(timeout=30.0)

    def _build_prompt(self) -> str:
        return (
            "You are a conceptual poet who mixes classical poetry styles with absurd realism. "
            "Your theme is 'the philosophy of manure, concrete, and the banality of existence'. "
            "Combine the style of a classical poet (e.g., Pasternak, Blok, Lermontov) with a "
            "modern absurdist or a gritty realist (e.g., Prigov, Grigoryev). "
            "\n\nREQUIREMENTS:\n"
            "1. Define a set of 'Motifs' (high/classical) and 'Antonyms' (low/gritty).\n"
            "2. Write a poem that reflects this tension.\n"
            "3. The central image must involve manure, concrete, or the grime of daily life.\n"
            "\nOUTPUT FORMAT:\n"
            "You MUST wrap your final result in <json> tags exactly like this:\n"
            "<json>\n"
            "{\n"
            "  \"motifs\": [\"motif1\", \"motif2\"],\n"
            "  \"antonyms\": [\"antonym1\", \"antonym2\"],\n"
            "  \"title\": \"Poem Title\",\n"
            "  \"poem\": \"Full text of the poem...\"\n"
            "}\n"
            "</json>\n"
            "Do not write anything outside the <json> tags."
        )

    def generate(self) -> Dict[str, Any]:
        prompt = self._build_prompt()
        
        try:
            response = self.client.post(
                self.settings.API_ENDPOINT,
                headers={"Authorization": f"Bearer {self.settings.API_KEY}", "Content-Type": "application/json"},
                json={
                    "model": self.settings.MODEL_NAME,
                    "messages": [{"role": "system", "content": prompt}],
                    "temperature": 0.8
                }
            )
            response.raise_for_status()
            content = response.json()['choices'][0]['message']['content']
            return self._parse_json(content)
        except Exception as e:
            logger.error(f"API Generation error: {e}")
            raise RuntimeError(f"Failed to generate poem: {e}")

    def _parse_json(self, text: str) -> Dict[str, Any]:
        try:
            # Extract content between <json> tags
            match = re.search(r'<json>(.*?)</json>', text, re.DOTALL)
            if match:
                return json.loads(match.group(1).strip())
            
            # Fallback: try to find any JSON-like block
            match_raw = re.search(r'\{.*\}', text, re.DOTALL)
            if match_raw:
                return json.loads(match_raw.group(0).strip())
            
            raise ValueError("No JSON block found in LLM response")
        except Exception as e:
            logger.error(f"Parsing error: {e}. Raw text: {text}")
            raise ValueError(f"Could not parse LLM response: {e}")
