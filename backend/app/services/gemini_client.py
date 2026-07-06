from __future__ import annotations

import json
import re
from typing import Any

import httpx

from app.config import get_settings

GEMINI_API_BASE = "https://generativelanguage.googleapis.com/v1beta"


class GeminiUnavailableError(Exception):
    pass


class GeminiParseError(Exception):
    pass


class GeminiClient:
    def __init__(self) -> None:
        self.settings = get_settings()
        self.total_tokens = 0

    def _api_key(self) -> str:
        key = (self.settings.gemini_api_key or "").strip()
        if not key or key.lower() in ("your_gemini_api_key_here", "changeme", "xxx"):
            raise GeminiUnavailableError(
                "GEMINI_API_KEY is not set. Add it to backend/.env — get a free key at "
                "https://aistudio.google.com/apikey"
            )
        return key

    async def check_health(self) -> bool:
        try:
            self._api_key()
            return True
        except GeminiUnavailableError:
            return False

    async def generate_json(self, system: str, user: str, retry: bool = True, temperature: float = 0.7) -> dict[str, Any]:
        api_key = self._api_key()
        model = self.settings.gemini_model
        url = f"{GEMINI_API_BASE}/models/{model}:generateContent"

        payload: dict[str, Any] = {
            "systemInstruction": {"parts": [{"text": system}]},
            "contents": [{"role": "user", "parts": [{"text": user}]}],
            "generationConfig": {
                "responseMimeType": "application/json",
                "temperature": temperature,
            },
        }

        try:
            data = await self._post_generate(url, api_key, payload)
        except httpx.HTTPError as exc:
            raise GeminiUnavailableError(
                f"Gemini API request failed: {exc}"
            ) from exc

        try:
            return self._parse_response(data)
        except GeminiParseError:
            if retry:
                payload["contents"].append(
                    {
                        "role": "model",
                        "parts": [{"text": self._extract_text(data)}],
                    }
                )
                payload["contents"].append(
                    {
                        "role": "user",
                        "parts": [
                            {
                                "text": (
                                    "Your response was not valid JSON. "
                                    "Respond with ONLY valid JSON, no markdown."
                                )
                            }
                        ],
                    }
                )
                data2 = await self._post_generate(url, api_key, payload)
                return self._parse_response(data2)
            raise

    async def _post_generate(
        self, url: str, api_key: str, payload: dict[str, Any]
    ) -> dict[str, Any]:
        async with httpx.AsyncClient(timeout=180.0) as client:
            resp = await client.post(
                url,
                params={"key": api_key},
                json=payload,
            )

        if resp.status_code != 200:
            detail = resp.text[:400]
            if resp.status_code in (401, 403):
                raise GeminiUnavailableError(
                    "Invalid or unauthorized GEMINI_API_KEY. Check backend/.env"
                )
            if resp.status_code == 429:
                raise GeminiUnavailableError(
                    "Gemini API rate limit exceeded. Wait a moment and retry."
                )
            raise GeminiUnavailableError(
                f"Gemini returned status {resp.status_code}: {detail}"
            )

        data = resp.json()
        usage = data.get("usageMetadata", {})
        self.total_tokens += int(usage.get("totalTokenCount", 0) or 0)
        return data

    def _extract_text(self, data: dict[str, Any]) -> str:
        candidates = data.get("candidates") or []
        if not candidates:
            block_reason = data.get("promptFeedback", {}).get("blockReason")
            if block_reason:
                raise GeminiUnavailableError(f"Gemini blocked the prompt: {block_reason}")
            raise GeminiParseError("Gemini returned no candidates")

        parts = candidates[0].get("content", {}).get("parts") or []
        texts = [p.get("text", "") for p in parts if p.get("text")]
        content = "".join(texts).strip()
        if not content:
            raise GeminiParseError("Gemini returned empty content")
        return content

    def _parse_response(self, data: dict[str, Any]) -> dict[str, Any]:
        content = self._extract_text(data)
        return self._parse_json(content)

    def _parse_json(self, content: str) -> dict[str, Any]:
        text = content.strip()
        if text.startswith("```"):
            text = re.sub(r"^```(?:json)?\s*", "", text)
            text = re.sub(r"\s*```$", "", text)
        try:
            return json.loads(text)
        except json.JSONDecodeError as exc:
            match = re.search(r"\{.*\}", text, re.DOTALL)
            if match:
                try:
                    return json.loads(match.group())
                except json.JSONDecodeError:
                    pass
            raise GeminiParseError(f"Failed to parse Gemini JSON: {content[:300]}") from exc
