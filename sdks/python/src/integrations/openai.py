"""
OpenAI Integration for the zv1 engine.

Provides access to OpenAI's embeddings and moderation APIs.
"""

from __future__ import annotations

import logging
import time
from typing import Any

from src.utilities.sanitize_api_call import emit_api_call_event

try:
    import httpx

    HAS_HTTPX = True
except ImportError:
    HAS_HTTPX = False

logger = logging.getLogger(__name__)


class OpenAIIntegration:
    """
    Integration with OpenAI's API for embeddings and moderation.
    """

    def __init__(
        self,
        api_key: str,
        base_url: str = "https://api.openai.com/v1",
        timeout: float = 30.0,
    ) -> None:
        """
        Initialize the OpenAI integration.

        Args:
            api_key: OpenAI API key.
            base_url: Base URL for the API.
            timeout: Request timeout in seconds.
        """
        if not HAS_HTTPX:
            raise ImportError(
                "httpx package is required for OpenAI integration. "
                "Install with: pip install httpx"
            )

        self.api_key = api_key
        self.base_url = base_url
        self.timeout = timeout

        self.client = httpx.AsyncClient(
            timeout=timeout,
            headers={
                "Content-Type": "application/json",
                "Authorization": f"Bearer {api_key}",
            },
        )

    async def create_embedding(
        self,
        input_text: str | list[str],
        model: str = "text-embedding-3-small",
    ) -> dict[str, Any]:
        """
        Create embeddings for text using OpenAI's embedding models.

        Args:
            input_text: Text or array of texts to embed.
            model: Embedding model to use.

        Returns:
            Embedding response with data, model, and usage.

        Raises:
            Exception: On API errors.
        """
        request_url = f"{self.base_url}/embeddings"
        request_body = {"model": model, "input": input_text}
        start_time = int(time.time() * 1000)

        try:
            response = await self.client.post(request_url, json=request_body)

            await emit_api_call_event(getattr(self, "_engine_config", None), {
                "timestamp": start_time, "integration": "openai", "nodeId": None, "nodeType": None,
                "request": {"method": "POST", "url": request_url, "headers": dict(self.client.headers), "body": request_body},
                "response": {"status": response.status_code, "statusText": response.reason_phrase or ""},
                "duration": int(time.time() * 1000) - start_time, "error": None,
            })

            if response.status_code >= 400:
                try:
                    error_data = response.json()
                    error_msg = error_data.get("error", {}).get(
                        "message", response.reason_phrase
                    )
                except Exception:
                    error_msg = response.reason_phrase

                raise Exception(
                    f"OpenAI API error: {response.status_code} - {error_msg}"
                )

            data = response.json()
            return {
                "data": data.get("data"),
                "model": data.get("model"),
                "usage": data.get("usage"),
            }

        except httpx.HTTPStatusError as e:
            status = e.response.status_code
            status_text = e.response.reason_phrase
            try:
                response_data = e.response.json()
                error_detail = response_data.get("error", {}).get("message", "")
            except Exception:
                error_detail = ""

            error_message = f"OpenAI Embeddings API Error ({status} {status_text})"
            if error_detail:
                error_message += f": {error_detail}"

            raise Exception(error_message) from e

        except httpx.RequestError as e:
            raise Exception(f"OpenAI Embeddings API Error: {e}") from e

    async def moderate_content(
        self, input_content: str | list[Any] | dict[str, Any]
    ) -> dict[str, Any]:
        """
        Moderate content using OpenAI's moderation API.

        Args:
            input_content: Content to moderate (string, array, or Message object).

        Returns:
            Moderation results with category flags and scores.

        Raises:
            Exception: On API errors.
        """
        try:
            # Extract content from Message object or use input directly
            moderation_input = input_content

            # Handle Message object with {role, content} structure
            if (
                isinstance(input_content, dict)
                and "content" in input_content
            ):
                moderation_input = input_content["content"]

            # If not string or list, wrap in list
            if not isinstance(moderation_input, (str, list)):
                moderation_input = [moderation_input]

            mod_url = f"{self.base_url}/moderations"
            mod_body = {"model": "omni-moderation-latest", "input": moderation_input}
            mod_start = int(time.time() * 1000)

            response = await self.client.post(mod_url, json=mod_body)

            await emit_api_call_event(getattr(self, "_engine_config", None), {
                "timestamp": mod_start, "integration": "openai", "nodeId": None, "nodeType": None,
                "request": {"method": "POST", "url": mod_url, "headers": dict(self.client.headers), "body": mod_body},
                "response": {"status": response.status_code, "statusText": response.reason_phrase or ""},
                "duration": int(time.time() * 1000) - mod_start, "error": None,
            })

            if response.status_code >= 400:
                try:
                    error_data = response.json()
                    error_msg = error_data.get("error", {}).get(
                        "message", response.reason_phrase
                    )
                except Exception:
                    error_msg = response.reason_phrase

                raise Exception(
                    f"OpenAI Moderation API error: {response.status_code} - {error_msg}"
                )

            data = response.json()

            # Extract the first result
            results = data.get("results", [])
            result = results[0] if results else {}
            categories = result.get("categories", {})
            category_scores = result.get("category_scores", {})

            return {
                "flagged": result.get("flagged", False),
                "sexual": categories.get("sexual", False),
                "sexual_score": category_scores.get("sexual", 0),
                "sexual_minors": categories.get("sexual/minors", False),
                "sexual_minors_score": category_scores.get("sexual/minors", 0),
                "harassment": categories.get("harassment", False),
                "harassment_score": category_scores.get("harassment", 0),
                "harassment_threatening": categories.get("harassment/threatening", False),
                "harassment_threatening_score": category_scores.get(
                    "harassment/threatening", 0
                ),
                "hate": categories.get("hate", False),
                "hate_score": category_scores.get("hate", 0),
                "hate_threatening": categories.get("hate/threatening", False),
                "hate_threatening_score": category_scores.get("hate/threatening", 0),
                "illicit": categories.get("illicit", False),
                "illicit_score": category_scores.get("illicit", 0),
                "illicit_violent": categories.get("illicit/violent", False),
                "illicit_violent_score": category_scores.get("illicit/violent", 0),
                "self_harm": categories.get("self-harm", False),
                "self_harm_score": category_scores.get("self-harm", 0),
                "self_harm_intent": categories.get("self-harm/intent", False),
                "self_harm_intent_score": category_scores.get("self-harm/intent", 0),
                "self_harm_instructions": categories.get("self-harm/instructions", False),
                "self_harm_instructions_score": category_scores.get(
                    "self-harm/instructions", 0
                ),
                "violence": categories.get("violence", False),
                "violence_score": category_scores.get("violence", 0),
                "violence_graphic": categories.get("violence/graphic", False),
                "violence_graphic_score": category_scores.get("violence/graphic", 0),
            }

        except httpx.HTTPStatusError as e:
            status = e.response.status_code
            status_text = e.response.reason_phrase
            try:
                response_data = e.response.json()
                error_detail = response_data.get("error", {}).get("message", "")
            except Exception:
                error_detail = ""

            error_message = f"OpenAI Moderation API Error ({status} {status_text})"
            if error_detail:
                error_message += f": {error_detail}"

            raise Exception(error_message) from e

        except httpx.RequestError as e:
            raise Exception(f"OpenAI Moderation API Error: {e}") from e

    async def close(self) -> None:
        """Close the HTTP client."""
        await self.client.aclose()
