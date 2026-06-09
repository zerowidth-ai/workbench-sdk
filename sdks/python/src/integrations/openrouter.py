"""
OpenRouter Integration for the zv1 engine.

Provides access to OpenRouter's AI models through their OpenAI-compatible API.
"""

from __future__ import annotations

import logging
import time
from dataclasses import dataclass
from typing import TYPE_CHECKING, Any

from src.utilities.sanitize_api_call import emit_api_call_event

try:
    from openai import AsyncOpenAI
    HAS_OPENAI = True
except ImportError:
    HAS_OPENAI = False

if TYPE_CHECKING:
    pass

logger = logging.getLogger(__name__)


@dataclass
class UsageStats:
    """Token usage statistics."""
    prompt_tokens: int = 0
    completion_tokens: int = 0
    total_tokens: int = 0

    def to_dict(self) -> dict[str, int]:
        return {
            "prompt_tokens": self.prompt_tokens,
            "completion_tokens": self.completion_tokens,
            "total_tokens": self.total_tokens,
        }


@dataclass
class CostBreakdown:
    """Cost breakdown for a request."""
    total_cost: float
    itemized_costs: list[dict[str, Any]]


class OpenRouterIntegration:
    """
    Integration with OpenRouter's AI model API.

    Uses the OpenAI SDK with OpenRouter's base URL for compatibility.
    """

    def __init__(
        self,
        api_key: str,
        base_url: str = "https://openrouter.ai/api/v1",
        referer: str = "https://zv1.ai",
        title: str = "zv1 by ZeroWidth",
    ) -> None:
        """
        Initialize the OpenRouter integration.

        Args:
            api_key: OpenRouter API key.
            base_url: Base URL for the API.
            referer: HTTP Referer header value.
            title: X-Title header value.
        """
        if not HAS_OPENAI:
            raise ImportError(
                "openai package is required for OpenRouter integration. "
                "Install with: pip install openai"
            )

        self.api_key = api_key
        self.base_url = base_url
        self.referer = referer
        self.title = title

        self.client = AsyncOpenAI(
            api_key=api_key,
            base_url=base_url,
            default_headers={
                "Content-Type": "application/json",
                "HTTP-Referer": referer,
                "X-Title": title,
            },
        )

    async def chat_completion(
        self,
        *,
        model: str,
        messages: list[dict[str, Any]] | None = None,
        prompt: str | None = None,
        node_config: dict[str, Any] | None = None,
        engine_config: dict[str, Any] | None = None,
        **kwargs: Any,
    ) -> dict[str, Any]:
        """
        Make a chat completion request to OpenRouter.

        Args:
            model: Model identifier (e.g., "anthropic/claude-3.5-sonnet").
            messages: List of chat messages.
            prompt: Alternative to messages for completion-style requests.
            node_config: Node configuration for cost calculation and streaming.
            engine_config: Engine configuration for callbacks.
            **kwargs: Additional parameters (temperature, max_tokens, etc.).

        Returns:
            Dict containing response content, role, usage, costs, etc.

        Raises:
            ValueError: If neither messages nor prompt is provided.
            Exception: On API errors.
        """
        if not messages and not prompt:
            raise ValueError("Either messages or prompt must be provided")

        # Build payload
        payload: dict[str, Any] = {
            "model": model,
            "provider": {
                "data_collection": "deny",
                "require_parameters": True,
            },
            # Request OpenRouter usage accounting so the response carries the
            # authoritative cost (usage.cost). build_cost_data prefers it.
            "usage": {"include": True},
        }

        # Add messages (cleaned up)
        if messages:
            payload["messages"] = self._clean_messages(messages)
        elif prompt:
            payload["prompt"] = prompt

        # Handle tools
        if "tools" in kwargs:
            tools = kwargs.pop("tools")
            if tools:
                payload["tools"] = [
                    {
                        "type": "function",
                        "function": {
                            "name": tool.get("name"),
                            "description": tool.get("description"),
                            "parameters": tool.get("parameters"),
                        },
                    }
                    for tool in tools
                ]

        # Handle reasoning parameter
        if "reasoning" in kwargs:
            reasoning = kwargs.pop("reasoning")
            if isinstance(reasoning, bool):
                payload["reasoning"] = {"enabled": reasoning}
            elif isinstance(reasoning, dict):
                payload["reasoning"] = reasoning

        if "include_reasoning" in kwargs:
            # Legacy support: treat as reasoning toggle
            include_reasoning = kwargs.pop("include_reasoning")
            if isinstance(include_reasoning, bool) and "reasoning" not in payload:
                payload["reasoning"] = {"enabled": include_reasoning}

        # Add other parameters (excluding system_prompt which is handled in messages)
        for key, value in kwargs.items():
            if key != "system_prompt" and value is not None:
                payload[key] = value

        # Remove empty tools array
        if "tools" in payload and not payload["tools"]:
            del payload["tools"]

        is_image_request = isinstance(payload.get("modalities"), list) and "image" in payload["modalities"]

        api_call_start_time = int(time.time() * 1000)
        try:
            # Image models: use non-streaming to preserve images field (OpenAI SDK strips it from stream deltas)
            if is_image_request:
                return await self._non_streaming_completion(payload, node_config, engine_config, api_call_start_time)

            # Enable streaming
            payload["stream"] = True
            return await self._stream_completion(payload, node_config, engine_config, api_call_start_time)
        except Exception as e:
            # Parse error details from OpenAI SDK error shape
            status = getattr(e, "status_code", None) or getattr(e, "status", 0) or 0
            status_text = f"HTTP {status}" if status else "Error"
            error_body = getattr(e, "body", None) or getattr(e, "response", None)
            error_code = getattr(e, "code", None)
            error_type = getattr(e, "type", None)

            # Try to extract nested error info
            if isinstance(error_body, dict):
                nested = error_body.get("error", {})
                if isinstance(nested, dict):
                    error_code = error_code or nested.get("code")
                    error_type = error_type or nested.get("type")
                    specific_msg = nested.get("message") or error_body.get("message")
                else:
                    specific_msg = error_body.get("message") or str(nested)
            elif isinstance(error_body, str):
                specific_msg = error_body
            else:
                specific_msg = str(e)

            error_message = "OpenRouter API Error"
            if status:
                error_message += f" ({status})"
            if specific_msg:
                error_message += f": {specific_msg}"

            # OpenRouter wraps the actual upstream provider error in metadata.raw.
            # Surface it (e.g. "logprobs are not supported with reasoning models"),
            # otherwise callers only see the generic "Provider returned error".
            if isinstance(error_body, dict):
                meta = (error_body.get("error") or {}).get("metadata") if isinstance(
                    error_body.get("error"), dict
                ) else error_body.get("metadata")
                if isinstance(meta, dict) and meta.get("raw"):
                    upstream = None
                    try:
                        import json as _json
                        upstream = (_json.loads(meta["raw"]).get("error") or {}).get("message")
                    except Exception:
                        upstream = meta["raw"] if isinstance(meta["raw"], str) else None
                    if upstream and upstream != specific_msg:
                        prov = meta.get("provider_name")
                        error_message += f" — {prov + ': ' if prov else ''}{upstream}"

            # Emit API call event with full error detail
            _cfg = engine_config or getattr(self, "_engine_config", None)
            await emit_api_call_event(_cfg, {
                "timestamp": api_call_start_time,
                "integration": "openrouter",
                "nodeId": node_config.get("id") if node_config else None,
                "nodeType": node_config.get("type") if node_config else None,
                "request": {
                    "method": "POST",
                    "url": f"{self.base_url}/chat/completions",
                    "headers": {
                        "Content-Type": "application/json",
                        "HTTP-Referer": self.referer,
                        "X-Title": self.title,
                        "Authorization": f"Bearer {self.api_key}",
                    },
                    "body": payload,
                },
                "response": {
                    "status": status,
                    "statusText": status_text,
                    "body": error_body,
                },
                "duration": int(time.time() * 1000) - api_call_start_time,
                "error": {
                    "message": error_message,
                    "code": error_code,
                    "type": error_type,
                    "status": status,
                    "raw": str(e),
                },
            })

            logger.error(f"OpenRouter Integration Error: {error_message}")
            raise Exception(error_message) from e

    def _clean_messages(
        self, messages: list[dict[str, Any]]
    ) -> list[dict[str, Any]]:
        """Clean messages by removing internal fields."""
        cleaned = []
        for msg in messages:
            clean_msg = {k: v for k, v in msg.items() if k not in ("id", "participant_id", "timestamp")}
            # Remove empty tool_calls
            if clean_msg.get("tool_calls") == []:
                del clean_msg["tool_calls"]
            cleaned.append(clean_msg)
        return cleaned

    async def _non_streaming_completion(
        self,
        payload: dict[str, Any],
        node_config: dict[str, Any] | None,
        engine_config: dict[str, Any] | None,
        api_call_start_time: int | None = None,
    ) -> dict[str, Any]:
        """Non-streaming completion for image models.

        Bypasses the OpenAI SDK entirely because it strips OpenRouter-specific
        fields like `images` from both streaming deltas and non-streaming messages.
        Uses raw httpx to preserve the full response.
        """
        import httpx

        if api_call_start_time is None:
            api_call_start_time = int(time.time() * 1000)

        url = f"{self.base_url}/chat/completions"
        headers = {
            "Content-Type": "application/json",
            "HTTP-Referer": self.referer,
            "X-Title": self.title,
            "Authorization": f"Bearer {self.api_key}",
        }

        async with httpx.AsyncClient(timeout=300) as client:
            res = await client.post(url, headers=headers, json=payload)

        if res.status_code >= 400:
            error_body = res.json() if res.headers.get("content-type", "").startswith("application/json") else None
            error_msg = (error_body or {}).get("error", {}).get("message", f"HTTP {res.status_code}")
            raise Exception(f"OpenRouter API Error ({res.status_code}): {error_msg}")

        data = res.json()
        choice = data.get("choices", [{}])[0] if data.get("choices") else {}
        message = choice.get("message", {})
        usage_raw = data.get("usage", {})

        usage = UsageStats(
            prompt_tokens=usage_raw.get("prompt_tokens", 0) or 0,
            completion_tokens=usage_raw.get("completion_tokens", 0) or 0,
            total_tokens=usage_raw.get("total_tokens", 0) or 0,
        )

        cost_data = None
        if node_config:
            cost_data = self.build_cost_data(
                {**usage.to_dict(), "cost": usage_raw.get("cost")}, node_config.get("pricing")
            )

        # Image models return data on choice directly (text, images, reasoning)
        # rather than nested under choice.message
        result: dict[str, Any] = {
            "content": message.get("content") or choice.get("text", "") or "",
            "role": message.get("role", "assistant") or "assistant",
            "finish_reason": choice.get("finish_reason", "") or "",
            "tool_calls": message.get("tool_calls"),
            "model": payload["model"],
            "usage": usage.to_dict(),
            "reasoning": message.get("reasoning") or choice.get("reasoning") or None,
            "images": message.get("images") or choice.get("images") or None,
            "logprobs": choice.get("logprobs"),
        }

        if cost_data:
            result["cost_total"] = cost_data.total_cost
            result["cost_itemized"] = cost_data.itemized_costs

        _cfg = engine_config or getattr(self, "_engine_config", None)
        await emit_api_call_event(_cfg, {
            "timestamp": api_call_start_time,
            "integration": "openrouter",
            "nodeId": node_config.get("id") if node_config else None,
            "nodeType": node_config.get("type") if node_config else None,
            "request": {
                "method": "POST",
                "url": url,
                "headers": headers,
                "body": payload,
            },
            "response": {"status": res.status_code, "statusText": res.reason_phrase, "body": result},
            "duration": int(time.time() * 1000) - api_call_start_time,
            "error": None,
        })

        return result

    async def _stream_completion(
        self,
        payload: dict[str, Any],
        node_config: dict[str, Any] | None,
        engine_config: dict[str, Any] | None,
        api_call_start_time: int | None = None,
    ) -> dict[str, Any]:
        """Handle streaming completion response."""
        import json as json_module

        if api_call_start_time is None:
            api_call_start_time = int(time.time() * 1000)

        # Extract OpenRouter-specific params for extra_body (not supported by OpenAI SDK directly)
        extra_body: dict[str, Any] = {}
        if "provider" in payload:
            extra_body["provider"] = payload.pop("provider")
        if "reasoning" in payload:
            extra_body["reasoning"] = payload.pop("reasoning")
        if "usage" in payload:
            extra_body["usage"] = payload.pop("usage")

        # Create streaming request
        stream = await self.client.chat.completions.create(
            **payload,
            extra_body=extra_body if extra_body else None
        )

        content = ""
        role = "assistant"
        finish_reason = ""
        reasoning = ""
        images: list[dict[str, Any]] = []
        tool_calls: list[dict[str, Any]] = []
        usage = UsageStats()
        api_cost: float | None = None  # authoritative cost from usage accounting
        logprobs_content: list[Any] = []  # accumulated per-token logprobs across chunks

        count = 0
        async for chunk in stream:
            if chunk.object == "chat.completion.chunk":
                event: dict[str, Any] = {
                    "count": count,
                    "node_type": node_config.get("type") if node_config else None,
                    "node_id": node_config.get("id") if node_config else None,
                    "timestamp": int(time.time() * 1000),
                    "data": {},
                }

                if chunk.choices:
                    choice = chunk.choices[0]
                    if hasattr(choice, "delta") and choice.delta:
                        delta = choice.delta
                        # Access images from delta (OpenRouter custom field, may not be a typed attr)
                        delta_images = getattr(delta, "images", None)
                        if delta_images is None and hasattr(delta, "model_extra"):
                            delta_images = delta.model_extra.get("images")
                        event["data"] = {
                            "content": getattr(delta, "content", None),
                            "reasoning": getattr(delta, "reasoning", None),
                            "role": getattr(delta, "role", None),
                            "tool_calls": getattr(delta, "tool_calls", None),
                            "images": delta_images,
                            "finish_reason": getattr(choice, "finish_reason", None),
                        }
                    elif hasattr(choice, "text") and choice.text:
                        event["data"]["content"] = choice.text

                # Accumulate content
                if event["data"].get("content"):
                    content += event["data"]["content"]

                # Accumulate reasoning
                if event["data"].get("reasoning"):
                    reasoning += event["data"]["reasoning"]

                # Set role
                if event["data"].get("role"):
                    role = event["data"]["role"]
                else:
                    event["data"]["role"] = "assistant"

                # Handle tool calls
                delta_tool_calls = event["data"].get("tool_calls")
                if delta_tool_calls:
                    for tc in delta_tool_calls:
                        if hasattr(tc, "id") and tc.id:
                            tool_calls.append({
                                "id": tc.id,
                                "index": getattr(tc, "index", 0),
                                "type": getattr(tc, "type", "function"),
                                "function": {
                                    "name": tc.function.name if tc.function else "",
                                    "arguments": tc.function.arguments if tc.function else "",
                                },
                            })
                        elif tool_calls:
                            # Append to most recent tool call's arguments
                            if tc.function and tc.function.arguments:
                                tool_calls[-1]["function"]["arguments"] += tc.function.arguments

                # Accumulate images from delta (OpenRouter returns images in delta.images)
                delta_imgs = event["data"].get("images")
                if delta_imgs and isinstance(delta_imgs, list):
                    images.extend(delta_imgs)

                # Accumulate logprobs (per-token, in choices[].logprobs.content)
                if chunk.choices:
                    lp = getattr(chunk.choices[0], "logprobs", None)
                    lp_content = getattr(lp, "content", None) if lp else None
                    if lp_content:
                        logprobs_content.extend(
                            c.model_dump() if hasattr(c, "model_dump") else c
                            for c in lp_content
                        )

                # Handle finish reason
                if event["data"].get("finish_reason"):
                    finish_reason = event["data"]["finish_reason"]

                # Update usage
                if hasattr(chunk, "usage") and chunk.usage:
                    usage.prompt_tokens += chunk.usage.prompt_tokens or 0
                    usage.completion_tokens += chunk.usage.completion_tokens or 0
                    usage.total_tokens += chunk.usage.total_tokens or 0
                    # OpenRouter returns cost in the final usage chunk (custom field)
                    cost_val = getattr(chunk.usage, "cost", None)
                    if cost_val is None and getattr(chunk.usage, "model_extra", None):
                        cost_val = chunk.usage.model_extra.get("cost")
                    if cost_val is not None:
                        api_cost = cost_val

                # Call onNodeUpdate callback if provided
                if engine_config and engine_config.get("on_node_update"):
                    try:
                        callback = engine_config["on_node_update"]
                        if callable(callback):
                            result = callback(event)
                            if hasattr(result, "__await__"):
                                await result
                    except Exception as e:
                        logger.warning(f"Error in on_node_update callback: {e}")

                count += 1

        # Parse tool call arguments as JSON
        for tc in tool_calls:
            try:
                tc["function"]["arguments"] = json_module.loads(
                    tc["function"]["arguments"]
                )
            except (json_module.JSONDecodeError, TypeError):
                pass  # Keep as string if not valid JSON

        # Calculate costs. build_cost_data prefers the API-reported cost (usage
        # accounting) and falls back to baked pricing.
        cost_data = None
        if node_config:
            cost_data = self.build_cost_data(
                {**usage.to_dict(), "cost": api_cost}, node_config.get("pricing")
            )

        result: dict[str, Any] = {
            "content": content,
            "role": role,
            "finish_reason": finish_reason,
            "tool_calls": tool_calls if tool_calls else None,
            "model": payload["model"],
            "usage": usage.to_dict(),
            "reasoning": reasoning if reasoning else None,
            "images": images if images else None,
            "logprobs": {"content": logprobs_content} if logprobs_content else None,
        }

        if cost_data:
            result["cost_total"] = cost_data.total_cost
            result["cost_itemized"] = cost_data.itemized_costs

        # Emit API call event after stream is consumed
        _cfg = engine_config or getattr(self, "_engine_config", None)
        await emit_api_call_event(_cfg, {
            "timestamp": api_call_start_time,
            "integration": "openrouter",
            "nodeId": node_config.get("id") if node_config else None,
            "nodeType": node_config.get("type") if node_config else None,
            "request": {
                "method": "POST",
                "url": f"{self.base_url}/chat/completions",
                "headers": {
                    "Content-Type": "application/json",
                    "HTTP-Referer": self.referer,
                    "X-Title": self.title,
                    "Authorization": f"Bearer {self.api_key}",
                },
                "body": payload,
            },
            "response": {"status": 200, "statusText": "OK", "body": result},
            "duration": int(time.time() * 1000) - api_call_start_time,
            "error": None,
        })

        return result

    def calculate_costs(
        self, usage: UsageStats, pricing: dict[str, Any]
    ) -> CostBreakdown:
        """
        Calculate costs based on usage and pricing information.

        Args:
            usage: Token usage statistics.
            pricing: Pricing configuration from node config.

        Returns:
            Cost breakdown with total and itemized costs.
        """
        items = pricing.get("items", [])
        input_cost_obj = next(
            (p for p in items if p.get("key") == "input_cost_per_million"), None
        )
        output_cost_obj = next(
            (p for p in items if p.get("key") == "output_cost_per_million"), None
        )

        input_token_cost = (input_cost_obj.get("cost", 0) if input_cost_obj else 0) / 1_000_000
        output_token_cost = (output_cost_obj.get("cost", 0) if output_cost_obj else 0) / 1_000_000

        input_cost = usage.prompt_tokens * input_token_cost
        output_cost = usage.completion_tokens * output_token_cost
        total_cost = input_cost + output_cost

        # Round to 8 decimal places
        total_cost = round(total_cost, 8)
        input_cost = round(input_cost, 8)
        output_cost = round(output_cost, 8)

        return CostBreakdown(
            total_cost=total_cost,
            itemized_costs=[
                {"label": "Input Tokens", "cost": input_cost, "tokens": usage.prompt_tokens},
                {"label": "Output Tokens", "cost": output_cost, "tokens": usage.completion_tokens},
            ],
        )

    def build_cost_data(
        self, usage: dict[str, Any], pricing: dict[str, Any] | None = None
    ) -> CostBreakdown | None:
        """
        Build cost data preserving the {total_cost, itemized_costs} shape.

        Prefers OpenRouter usage accounting (usage["cost"], requested via
        usage={"include": True}) as the authoritative total. Falls back to baked
        per-model pricing when the API doesn't report a cost — so existing
        per-model nodes keep their previous output when accounting is unavailable,
        while dynamic-model nodes (no baked pricing) still get real costs.

        itemized_costs always sums to total_cost. The input/output split uses the
        baked pricing rates when available, otherwise it's apportioned by tokens.
        """
        prompt_tokens = usage.get("prompt_tokens", 0) or 0
        completion_tokens = usage.get("completion_tokens", 0) or 0
        api_cost = usage.get("cost")
        has_api_cost = isinstance(api_cost, (int, float))

        if not has_api_cost and not pricing:
            return None

        if pricing:
            items = pricing.get("items", [])
            in_rate = (
                next((p.get("cost", 0) for p in items if p.get("key") == "input_cost_per_million"), 0) or 0
            ) / 1_000_000
            out_rate = (
                next((p.get("cost", 0) for p in items if p.get("key") == "output_cost_per_million"), 0) or 0
            ) / 1_000_000
            input_weight = prompt_tokens * in_rate
            output_weight = completion_tokens * out_rate
        else:
            input_weight = prompt_tokens
            output_weight = completion_tokens

        total_weight = input_weight + output_weight

        # Authoritative total: API cost when present, otherwise pricing-derived total
        total_cost = api_cost if has_api_cost else total_weight

        if total_weight > 0:
            input_cost = total_cost * (input_weight / total_weight)
            output_cost = total_cost * (output_weight / total_weight)
        else:
            # No token-weighted basis (e.g. rerank): attribute everything to one line
            input_cost = total_cost
            output_cost = 0

        return CostBreakdown(
            total_cost=round(total_cost, 8),
            itemized_costs=[
                {"label": "Input Tokens", "cost": round(input_cost, 8), "tokens": prompt_tokens},
                {"label": "Output Tokens", "cost": round(output_cost, 8), "tokens": completion_tokens},
            ],
        )

    async def create_embedding(
        self,
        *,
        model: str,
        input: str | list[str],
        node_config: dict[str, Any] | None = None,
        engine_config: dict[str, Any] | None = None,
        **kwargs: Any,
    ) -> dict[str, Any]:
        """
        Create embeddings via OpenRouter's OpenAI-compatible /embeddings endpoint.

        Uses raw httpx (like image completions) so we control the exact request
        body and preserve the full response.

        Args:
            model: Embedding model identifier (e.g., "openai/text-embedding-3-small").
            input: Text or list of texts to embed.
            node_config: Node configuration (provides `pricing` for cost calc).
            engine_config: Engine configuration (for API call events).
            **kwargs: Optional params (dimensions, encoding_format, ...).

        Returns:
            Dict with embeddings, embedding, dimensions, model, usage, costs.
        """
        import httpx

        if input is None:
            raise ValueError("input is required to create embeddings")

        payload: dict[str, Any] = {"model": model, "input": input, "usage": {"include": True}}
        for key, value in kwargs.items():
            if value is not None:
                payload[key] = value

        url = f"{self.base_url}/embeddings"
        headers = {
            "Content-Type": "application/json",
            "HTTP-Referer": self.referer,
            "X-Title": self.title,
            "Authorization": f"Bearer {self.api_key}",
        }

        api_call_start_time = int(time.time() * 1000)

        try:
            async with httpx.AsyncClient(timeout=300) as client:
                res = await client.post(url, headers=headers, json=payload)

            if res.status_code >= 400:
                error_body = (
                    res.json()
                    if res.headers.get("content-type", "").startswith("application/json")
                    else None
                )
                error_msg = (error_body or {}).get("error", {}).get(
                    "message", f"HTTP {res.status_code}"
                )
                raise Exception(f"OpenRouter API Error ({res.status_code}): {error_msg}")

            data = res.json()

            # OpenAI-compatible shape: { data: [{ embedding: [...], index }], model, usage }
            items = data.get("data") or []
            embeddings = [item.get("embedding") for item in items]
            embedding = embeddings[0] if embeddings else None
            dimensions = len(embedding) if isinstance(embedding, list) else 0

            usage_raw = data.get("usage", {}) or {}
            usage = UsageStats(
                prompt_tokens=usage_raw.get("prompt_tokens", 0) or 0,
                completion_tokens=usage_raw.get("completion_tokens", 0) or 0,
                total_tokens=usage_raw.get("total_tokens", 0)
                or usage_raw.get("prompt_tokens", 0)
                or 0,
            )

            cost_data = None
            if node_config:
                cost_data = self.build_cost_data(
                    {**usage.to_dict(), "cost": usage_raw.get("cost")}, node_config.get("pricing")
                )

            result: dict[str, Any] = {
                "embeddings": embeddings,
                "embedding": embedding,
                "dimensions": dimensions,
                "model": data.get("model", model),
                "usage": usage.to_dict(),
            }
            if cost_data:
                result["cost_total"] = cost_data.total_cost
                result["cost_itemized"] = cost_data.itemized_costs

            _cfg = engine_config or getattr(self, "_engine_config", None)
            await emit_api_call_event(_cfg, {
                "timestamp": api_call_start_time,
                "integration": "openrouter",
                "nodeId": node_config.get("id") if node_config else None,
                "nodeType": node_config.get("type") if node_config else None,
                "request": {"method": "POST", "url": url, "headers": headers, "body": payload},
                "response": {
                    "status": res.status_code,
                    "statusText": res.reason_phrase,
                    "body": result,
                },
                "duration": int(time.time() * 1000) - api_call_start_time,
                "error": None,
            })

            return result
        except Exception as e:
            _cfg = engine_config or getattr(self, "_engine_config", None)
            await emit_api_call_event(_cfg, {
                "timestamp": api_call_start_time,
                "integration": "openrouter",
                "nodeId": node_config.get("id") if node_config else None,
                "nodeType": node_config.get("type") if node_config else None,
                "request": {"method": "POST", "url": url, "headers": headers, "body": payload},
                "response": {"status": 0, "statusText": "Error", "body": None},
                "duration": int(time.time() * 1000) - api_call_start_time,
                "error": {"message": str(e)},
            })
            logger.error(f"OpenRouter Embedding Error: {e}")
            raise

    async def rerank(
        self,
        *,
        model: str,
        query: str,
        documents: list[str],
        node_config: dict[str, Any] | None = None,
        engine_config: dict[str, Any] | None = None,
        **kwargs: Any,
    ) -> dict[str, Any]:
        """
        Rerank documents against a query via OpenRouter's Cohere-compatible
        /rerank endpoint.

        Returns raw relevance results ({ index, relevance_score }); callers
        reattach original documents by index.

        Args:
            model: Rerank model identifier (e.g., "cohere/rerank-v3.5").
            query: The search query.
            documents: List of document strings to rerank.
            node_config: Node configuration (provides `pricing`).
            engine_config: Engine configuration (for API call events).
            **kwargs: Optional params (top_n, ...).

        Returns:
            Dict with results, usage, model, and optional cost data.
        """
        import httpx

        if query is None:
            raise ValueError("query is required for rerank")
        if not isinstance(documents, list):
            raise ValueError("documents (list of strings) is required for rerank")

        payload: dict[str, Any] = {"model": model, "query": query, "documents": documents, "usage": {"include": True}}
        for key, value in kwargs.items():
            if value is not None:
                payload[key] = value

        url = f"{self.base_url}/rerank"
        headers = {
            "Content-Type": "application/json",
            "HTTP-Referer": self.referer,
            "X-Title": self.title,
            "Authorization": f"Bearer {self.api_key}",
        }

        api_call_start_time = int(time.time() * 1000)

        try:
            async with httpx.AsyncClient(timeout=300) as client:
                res = await client.post(url, headers=headers, json=payload)

            if res.status_code >= 400:
                error_body = (
                    res.json()
                    if res.headers.get("content-type", "").startswith("application/json")
                    else None
                )
                error_msg = (error_body or {}).get("error", {}).get(
                    "message", f"HTTP {res.status_code}"
                )
                raise Exception(f"OpenRouter API Error ({res.status_code}): {error_msg}")

            data = res.json()

            # Cohere-compatible shape: { results: [{ index, relevance_score }], usage|meta }
            raw_results = data.get("results") or []
            results = [
                {
                    "index": r.get("index"),
                    "relevance_score": r.get("relevance_score", r.get("score")),
                }
                for r in raw_results
            ]

            usage = data.get("usage") or (data.get("meta") or {}).get("billed_units") or {}

            cost_data = None
            if node_config:
                cost_data = self.build_cost_data(usage, node_config.get("pricing"))

            result: dict[str, Any] = {
                "results": results,
                "usage": usage,
                "model": data.get("model", model),
            }
            if cost_data:
                result["cost_total"] = cost_data.total_cost
                result["cost_itemized"] = cost_data.itemized_costs

            _cfg = engine_config or getattr(self, "_engine_config", None)
            await emit_api_call_event(_cfg, {
                "timestamp": api_call_start_time,
                "integration": "openrouter",
                "nodeId": node_config.get("id") if node_config else None,
                "nodeType": node_config.get("type") if node_config else None,
                "request": {"method": "POST", "url": url, "headers": headers, "body": payload},
                "response": {
                    "status": res.status_code,
                    "statusText": res.reason_phrase,
                    "body": result,
                },
                "duration": int(time.time() * 1000) - api_call_start_time,
                "error": None,
            })

            return result
        except Exception as e:
            _cfg = engine_config or getattr(self, "_engine_config", None)
            await emit_api_call_event(_cfg, {
                "timestamp": api_call_start_time,
                "integration": "openrouter",
                "nodeId": node_config.get("id") if node_config else None,
                "nodeType": node_config.get("type") if node_config else None,
                "request": {"method": "POST", "url": url, "headers": headers, "body": payload},
                "response": {"status": 0, "statusText": "Error", "body": None},
                "duration": int(time.time() * 1000) - api_call_start_time,
                "error": {"message": str(e)},
            })
            logger.error(f"OpenRouter Rerank Error: {e}")
            raise
