from dataclasses import dataclass
from typing import Any, Dict
import os
LLM_PROVIDER_URL = os.getenv("LLM_PROVIDER_URL", "http://ollama:11434")
LLM_MODEL = os.getenv("LLM_MODEL", "llama3.2-vision")
@dataclass
class ParseResult:
    uuid: str; total: float; currency: str
    purchased_at: str | None; merchant: dict; category: str | None
    items: list[dict]; raw_json: Dict[str, Any]
class LLMAdapter:
    def parse_receipt(self, image_uri: str) -> ParseResult:
        return ParseResult(uuid="temp-uuid", total=0.0, currency="AUD",
                           purchased_at=None, merchant={"name":"Unknown","abn":"","address":""},
                           category=None, items=[], raw_json={"note":"stub"})
