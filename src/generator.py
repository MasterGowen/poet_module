import httpx
import json
import re
import logging
import time
from pydantic_settings import BaseSettings, SettingsConfigDict
from typing import Dict, Any, Optional, List

logger = logging.getLogger(__name__)

class Settings(BaseSettings):
    API_KEY: str
    API_ENDPOINT: str
    MODEL_NAME: str

    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8")

class PoetryGenerator:
    def __init__(self, settings: Settings):
        self.settings = settings
        # Client is not created here to allow context manager usage

    def __enter__(self):
        self.client = httpx.Client(timeout=120.0)
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        self.client.close()

    def _build_prompt(self) -> str:
        return (
            "Ты — виртуозный поэт, мастер концептуализма и авангарда, ведающий истинную силу слова. "
            "Твой почерк — это сплав высокого классического надрыва и ледяного, кромешного стёба. "
            "Читатель не должен понимать, где заканчивается глубокая экзистенциальная боль "
            "и начинается изощрённая издёвка.\n\n"
            
            "Твоя стихия — метафизика низменного, абсурда повседневности и экзистенциального распада.\n\n"
            
            "ЗАДАЧА:\n"
            "1. Определи «Мотивы» (высокое/классическое/сакральное) и «Антонимы» (низкое/бытовое/абсурдное), "
            "которые будут сталкиваться в тексте.\n"
            "2. Центральный образ — говно. Забудь про банальную физиологию. "
            "Это должна быть радикальная, непредсказуемая метафора. "
            "Прояви абсолютную свободу: пусть это будет валюта, божество, язык, "
            "архитектурный фундамент, экзистенциальное прозрение или что-то невообразимое. Взломай ожидания.\n"
            "3. Форма свободная, но подчинённая жёсткой внутренней логике. "
            "Ты должен владеть сложным поэтическим арсеналом и применять его осознанно: "
            "используй верлибр, внутреннюю рифму, аллитерацию/ассонанс, энжамбеман, "
            "синтаксический параллелизм, остранение бытового через высокий регистр (или наоборот). "
            "Текст должен звучать, держать ритм и бить в нерв. Объём — на твоё усмотрение.\n\n"
            
            "ФОРМАТ ВЫВОДА:\n"
            "Строго оберни результат в теги <json>. Не пиши ничего вне этих тегов, "
            "не используй markdown-обёртки (```json). "
            "В поле \"poem\" экранируй переносы строк символом \\n, чтобы JSON был валидным.\n\n"
            
            "<json>\n"
            "{\n"
            "  \"motifs\": [\"мотив1\", \"мотив2\"],\n"
            "  \"antonyms\": [\"антоним1\", \"антоним2\"],\n"
            "  \"title\": \"Название\",\n"
            "  \"poem\": \"Текст стихотворения\\nс экранированными переносами\"\n"
            "}\n"
            "</json>"
        )

    def generate(self) -> Dict[str, Any]:
        prompt = self._build_prompt()
        max_retries = 3
        backoff_factor = 2
        
        for attempt in range(max_retries):
            try:
                response = self.client.post(
                    self.settings.API_ENDPOINT,
                    headers={"Authorization": f"Bearer {self.settings.API_KEY}", "Content-Type": "application/json"},
                    json={
                        "model": self.settings.MODEL_NAME,
                        "messages": [{"role": "user", "content": prompt}],
                        "temperature": 0.8,
                    }
                )
                
                if response.status_code == 429 or 500 <= response.status_code < 600:
                    wait = backoff_factor ** attempt
                    logger.warning(f"API error {response.status_code}. Retrying in {wait}s...")
                    time.sleep(wait)
                    continue
                
                response.raise_for_status()
                content = response.json()['choices'][0]['message']['content']
                logger.debug(f"LLM raw response: {content}")
                return self._parse_json(content)
                
            except (httpx.HTTPStatusError, httpx.RequestError) as e:
                if attempt == max_retries - 1:
                    logger.error(f"API failure after {max_retries} attempts: {e}")
                    raise RuntimeError(f"Failed to generate poem: {e}") from e
                time.sleep(backoff_factor ** attempt)

        raise RuntimeError("Unexpected failure in generation loop")

    def _parse_json(self, text: str) -> Dict[str, Any]:
        try:
            # Non-greedy match for <json> tags
            match = re.search(r'<json>(.*?)</json>', text, re.DOTALL)
            if match:
                data = json.loads(match.group(1).strip())
            else:
                # Fallback: greedy search for outermost JSON block
                match_raw = re.search(r'(\{.*\})', text, re.DOTALL)
                if match_raw:
                    data = json.loads(match_raw.group(0).strip())
                else:
                    raise ValueError("No valid JSON block found in LLM response")
            
            # Normalize truncated keys (LLM sometimes shortens "poem" to "po" etc.)
            key_aliases = {'po': 'poem', 'titl': 'title', 'motif': 'motifs', 'ant': 'antonyms'}
            for alias, canonical in key_aliases.items():
                if alias in data and canonical not in data:
                    logger.warning(f"Normalizing truncated key '{alias}' -> '{canonical}'")
                    data[canonical] = data.pop(alias)

            # Structural validation
            required_keys = {'motifs', 'antonyms', 'title', 'poem'}
            if not required_keys.issubset(data.keys()):
                missing = required_keys - data.keys()
                raise ValueError(f"LLM response missing required keys: {missing}")
                
            return data
        except Exception as e:
            logger.error(f"Parsing error: {e}. Raw response:\n{text}")
            raise ValueError(f"Could not parse LLM response: {e}") from e
