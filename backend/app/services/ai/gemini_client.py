"""Gemini API client integration for Compliance Sentinel.

Provides asynchronous structured generation against the Google Gemini REST API,
with exponential backoff retries, JSON response mode, and a test-friendly
MockGeminiClient for deterministic offline testing.
"""

from __future__ import annotations

import asyncio
import json
import logging
from typing import Any, Dict, List, Optional
import httpx

from app.config import settings

logger = logging.getLogger(__name__)


class GeminiAPIError(Exception):
    """Exception raised for Gemini API communication or parse errors."""

    def __init__(self, message: str, status_code: Optional[int] = None, details: Optional[Any] = None) -> None:
        super().__init__(message)
        self.status_code = status_code
        self.details = details


class BaseGeminiClient:
    """Abstract base client for Gemini interactions."""

    async def generate_structured(
        self,
        prompt: str,
        system_instruction: Optional[str] = None,
        temperature: Optional[float] = None,
        max_output_tokens: Optional[int] = None,
    ) -> Dict[str, Any]:
        raise NotImplementedError


class GeminiClient(BaseGeminiClient):
    """Production Gemini API Client utilizing HTTP/REST with structured JSON output mode."""

    def __init__(
        self,
        api_key: Optional[str] = None,
        model: Optional[str] = None,
        temperature: Optional[float] = None,
        max_output_tokens: Optional[int] = None,
        timeout: Optional[int] = None,
    ) -> None:
        self.api_key = api_key or settings.GEMINI_API_KEY
        self.model = model or settings.GEMINI_MODEL
        self.temperature = temperature if temperature is not None else settings.GEMINI_TEMPERATURE
        self.max_output_tokens = max_output_tokens if max_output_tokens is not None else settings.GEMINI_MAX_OUTPUT_TOKENS
        self.timeout = timeout if timeout is not None else settings.GEMINI_TIMEOUT_SECONDS
        self.base_url = "https://generativelanguage.googleapis.com/v1beta/models"

    async def generate_structured(
        self,
        prompt: str,
        system_instruction: Optional[str] = None,
        temperature: Optional[float] = None,
        max_output_tokens: Optional[int] = None,
    ) -> Dict[str, Any]:
        """Calls Gemini API requesting strict application/json output."""
        if not self.api_key or self.api_key.strip() in ("", "mock", "test"):
            raise GeminiAPIError("GEMINI_API_KEY is not configured or invalid.")

        url = f"{self.base_url}/{self.model}:generateContent?key={self.api_key}"

        body: Dict[str, Any] = {
            "contents": [
                {
                    "role": "user",
                    "parts": [{"text": prompt}],
                }
            ],
            "generationConfig": {
                "temperature": temperature if temperature is not None else self.temperature,
                "maxOutputTokens": max_output_tokens if max_output_tokens is not None else self.max_output_tokens,
                "responseMimeType": "application/json",
            },
        }

        if system_instruction:
            body["systemInstruction"] = {
                "parts": [{"text": system_instruction}],
            }

        headers = {"Content-Type": "application/json"}
        max_retries = 3
        backoff_seconds = 1.0

        for attempt in range(1, max_retries + 1):
            try:
                async with httpx.AsyncClient(timeout=float(self.timeout)) as client:
                    response = await client.post(url, json=body, headers=headers)

                if response.status_code == 200:
                    data = response.json()
                    candidates = data.get("candidates", [])
                    if not candidates:
                        raise GeminiAPIError("Gemini returned no candidates in response.")

                    first_cand = candidates[0]
                    finish_reason = first_cand.get("finishReason")
                    if finish_reason in ("SAFETY", "RECITATION"):
                        raise GeminiAPIError(f"Generation stopped due to: {finish_reason}")

                    parts = first_cand.get("content", {}).get("parts", [])
                    if not parts or "text" not in parts[0]:
                        raise GeminiAPIError("Empty text parts in Gemini response candidate.")

                    raw_text = parts[0]["text"]
                    try:
                        return json.loads(raw_text)
                    except json.JSONDecodeError as json_err:
                        # Attempt markdown codeblock strip if present
                        cleaned = raw_text.strip()
                        if cleaned.startswith("```json"):
                            cleaned = cleaned[7:]
                        elif cleaned.startswith("```"):
                            cleaned = cleaned[3:]
                        if cleaned.endswith("```"):
                            cleaned = cleaned[:-3]
                        return json.loads(cleaned.strip())

                elif response.status_code in (429, 503) and attempt < max_retries:
                    logger.warning(
                        f"Gemini API rate limited (status {response.status_code}), retrying in {backoff_seconds}s (attempt {attempt}/{max_retries})"
                    )
                    await asyncio.sleep(backoff_seconds)
                    backoff_seconds *= 2
                    continue
                else:
                    error_text = response.text
                    logger.error(f"Gemini API error (status {response.status_code}): {error_text}")
                    raise GeminiAPIError(
                        f"Gemini API failed with status {response.status_code}: {error_text}",
                        status_code=response.status_code,
                    )

            except httpx.TimeoutException as timeout_err:
                if attempt < max_retries:
                    logger.warning(f"Gemini API request timed out, retrying (attempt {attempt}/{max_retries})")
                    await asyncio.sleep(backoff_seconds)
                    backoff_seconds *= 2
                    continue
                raise GeminiAPIError("Gemini API call timed out after multiple attempts.") from timeout_err
            except (httpx.RequestError, json.JSONDecodeError) as e:
                raise GeminiAPIError(f"Gemini API request or JSON parsing failed: {str(e)}") from e

        raise GeminiAPIError("Gemini API failed after all retry attempts.")


class MockGeminiClient(BaseGeminiClient):
    """Deterministic mock client for offline automated tests and development."""

    def __init__(self, responses: Optional[List[Dict[str, Any]]] = None) -> None:
        self.responses: List[Dict[str, Any]] = list(responses or [])
        self.call_history: List[Dict[str, Any]] = []

    def queue_response(self, response: Dict[str, Any]) -> None:
        self.responses.append(response)

    async def generate_structured(
        self,
        prompt: str,
        system_instruction: Optional[str] = None,
        temperature: Optional[float] = None,
        max_output_tokens: Optional[int] = None,
    ) -> Dict[str, Any]:
        self.call_history.append({
            "prompt": prompt,
            "system_instruction": system_instruction,
            "temperature": temperature,
            "max_output_tokens": max_output_tokens,
        })

        if self.responses:
            return self.responses.pop(0)

        # Default fallback mock response
        return {
            "requirements": [
                {
                    "requirement_code": "REQ-MOCK-001",
                    "title": "Access Control and Authentication",
                    "requirement_statement": "The organization shall enforce multi-factor authentication for all remote administrative access.",
                    "detailed_description": "All interactive administrative access originating outside the internal network must require at least two distinct authentication factors.",
                    "obligation_type": "mandatory",
                    "category": "Identity and Access Management",
                    "subcategory": "Authentication",
                    "applicability": "general",
                    "applicability_conditions": "Applies to all administrative interfaces and remote access portals.",
                    "jurisdiction": "Global",
                    "source_section": "Section 4.1",
                    "source_page": 1,
                    "source_excerpt": "The organization shall enforce multi-factor authentication for all remote administrative access.",
                    "confidence_score": 0.95,
                }
            ],
            "document_summary": "Extracted from mock input chunk.",
            "notes": "Automated test extraction result.",
        }


# Global client instance / provider accessor
_default_client: Optional[BaseGeminiClient] = None


def get_gemini_client() -> BaseGeminiClient:
    global _default_client
    if _default_client is None:
        if settings.GEMINI_API_KEY and settings.GEMINI_API_KEY.strip() not in ("", "mock", "test"):
            _default_client = GeminiClient()
        else:
            _default_client = MockGeminiClient()
    return _default_client


def set_gemini_client(client: BaseGeminiClient) -> None:
    global _default_client
    _default_client = client

