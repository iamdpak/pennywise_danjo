from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, Iterable

import base64
import json
import logging
import os
import re
import uuid
from urllib.parse import urlparse

import requests


logger = logging.getLogger(__name__)


LLM_PROVIDER_URL = os.getenv("LLM_PROVIDER_URL", "http://ollama:11434")
LLM_MODEL = os.getenv("LLM_MODEL", "llama3.2-vision")
LLM_TIMEOUT = int(os.getenv("LLM_TIMEOUT", "60"))


PROMPT_TEMPLATE = """
You are a receipt analysis assistant. Extract the structured information listed
below from the image. Respond with JSON only, wrapped in triple backticks.

Schema:
{
  "uuid": string (uuid4),
  "total": number,
  "currency": string,
  "purchased_at": string (ISO 8601 date or datetime) or null,
  "merchant": {
    "name": string,
    "abn": string,
    "address": string
  },
  "category": string or null,
  "items": [
    {
      "line_text": string,
      "quantity": number or null,
      "unit_price": number or null,
      "amount": number or null
    }
  ]
}

Rules:
- Always include all fields even if values are null.
- Use plain numbers for monetary fields (no currency symbols).
- When the receipt total is missing, approximate from the items.
- Choose the best matching category among: grocery, fuel, food. If none apply,
  produce a descriptive alternative.
- Use ISO format (YYYY-MM-DD or YYYY-MM-DDThh:mm:ss) for purchased_at.
- If items are not readable, return an empty list.
"""


@dataclass
class ParseResult:
    uuid: str
    total: float
    currency: str
    purchased_at: datetime | None
    merchant: Dict[str, Any]
    category: str | None
    items: list[dict]
    raw_json: Dict[str, Any]


class LLMAdapterError(RuntimeError):
    pass


class LLMAdapter:
    def __init__(self) -> None:
        self._endpoint = f"{LLM_PROVIDER_URL.rstrip('/')}/api/generate"

    def parse_receipt(self, image_uri: str) -> ParseResult:
        image_b64 = self._load_image_as_base64(image_uri)
        llm_response = self._call_model(PROMPT_TEMPLATE, image_b64)
        payload = self._extract_json_payload(llm_response)
        normalized = self._normalize_payload(payload)
        return ParseResult(
            uuid=normalized["uuid"],
            total=normalized["total"],
            currency=normalized["currency"],
            purchased_at=normalized.get("purchased_at"),
            merchant=normalized["merchant"],
            category=normalized.get("category"),
            items=normalized.get("items", []),
            raw_json=payload,
        )

    def _load_image_as_base64(self, image_uri: str) -> str:
        parsed = urlparse(image_uri)
        if parsed.scheme in {"http", "https"}:
            logger.debug("Downloading receipt image from %s", image_uri)
            response = requests.get(image_uri, timeout=LLM_TIMEOUT)
            response.raise_for_status()
            data = response.content
        else:
            path = Path(parsed.path if parsed.scheme == "file" else image_uri)
            if not path.exists():
                raise LLMAdapterError(f"Receipt image not found at {image_uri}")
            data = path.read_bytes()
        return base64.b64encode(data).decode("utf-8")

    def _call_model(self, prompt: str, image_b64: str) -> str:
        payload = {
            "model": LLM_MODEL,
            "prompt": prompt,
            "images": [image_b64],
            "stream": False,
        }
        logger.debug("Calling LLM %s at %s", LLM_MODEL, self._endpoint)
        response = requests.post(self._endpoint, json=payload, timeout=LLM_TIMEOUT)
        response.raise_for_status()
        result = response.json()
        llm_response = result.get("response")
        if not llm_response:
            raise LLMAdapterError("Empty response from LLM provider")
        return llm_response

    def _extract_json_payload(self, llm_response: str) -> Dict[str, Any]:
        match = re.search(r"```(?:json)?\s*(.*?)\s*```", llm_response, re.DOTALL)
        raw_json = match.group(1) if match else llm_response
        try:
            payload = json.loads(raw_json)
        except json.JSONDecodeError as exc:
            logger.error("Failed to parse LLM JSON output: %s", raw_json)
            raise LLMAdapterError("LLM response was not valid JSON") from exc
        if not isinstance(payload, dict):
            raise LLMAdapterError("LLM response JSON must be an object")
        return payload

    def _normalize_payload(self, payload: Dict[str, Any]) -> Dict[str, Any]:
        record = payload.get("receipt_data") if "receipt_data" in payload else payload

        def pick(keys: Iterable[str], default: str | None = None) -> str | None:
            for key in keys:
                value = record.get(key)
                if value not in (None, ""):
                    return value
            return default

        uuid_value = pick(["uuid"]) or str(uuid.uuid4())
        total_value = self._to_float(pick(["total", "amount", "grand_total"], default="0"))
        currency_value = pick(["currency"], default="AUD") or "AUD"
        category_value = pick(["category", "receipt_category"]) or None

        purchased_raw = pick(["purchased_at", "date_purchased", "purchase_date"])
        purchased_dt = self._parse_datetime(purchased_raw)

        merchant_block = record.get("merchant", {}) or {}
        merchant = {
            "name": pick(["merchant_name", "shop_name"], default=merchant_block.get("name") or "Unknown"),
            "abn": pick(["merchant_abn", "shop_abn"], default=merchant_block.get("abn") or ""),
            "address": pick(["merchant_address", "shop_address"], default=merchant_block.get("address") or ""),
        }
        merchant.update({k: v for k, v in merchant_block.items() if k not in merchant})

        items = self._normalize_items(record.get("items") or record.get("line_items") or [])

        return {
            "uuid": uuid_value,
            "total": total_value,
            "currency": currency_value,
            "purchased_at": purchased_dt,
            "category": category_value,
            "merchant": merchant,
            "items": items,
        }

    def _normalize_items(self, items: Any) -> list[dict]:
        normalized: list[dict] = []
        if not isinstance(items, list):
            return normalized
        for item in items:
            if isinstance(item, str):
                normalized.append({"line_text": item, "quantity": None, "unit_price": None, "amount": None})
                continue
            if isinstance(item, dict):
                normalized.append({
                    "line_text": item.get("line_text") or item.get("description") or item.get("name") or "",
                    "quantity": self._to_float(item.get("quantity")) if item.get("quantity") not in (None, "") else None,
                    "unit_price": self._to_float(item.get("unit_price")) if item.get("unit_price") not in (None, "") else None,
                    "amount": self._to_float(item.get("amount")) if item.get("amount") not in (None, "") else None,
                })
        return normalized

    @staticmethod
    def _to_float(value: Any) -> float:
        if value in (None, ""):
            return 0.0
        try:
            return float(value)
        except (TypeError, ValueError):
            return 0.0

    @staticmethod
    def _parse_datetime(value: Any) -> datetime | None:
        if not value:
            return None
        if isinstance(value, datetime):
            return value
        try:
            text = str(value).strip()
            if not text:
                return None
            if len(text) == 10:
                return datetime.fromisoformat(text)
            return datetime.fromisoformat(text)
        except ValueError:
            logger.debug("Could not parse purchased_at value %r", value)
            return None
