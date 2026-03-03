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
            include_reasoning = kwargs.pop("include_reasoning")
            if isinstance(include_reasoning, bool):
                if "reasoning" not in payload:
                    payload["reasoning"] = {"enabled": True}
                payload["reasoning"]["exclude"] = not include_reasoning

        # Add other parameters (excluding system_prompt which is handled in messages)
        for key, value in kwargs.items():
            if key != "system_prompt" and value is not None:
                payload[key] = value

        # Remove empty tools array
        if "tools" in payload and not payload["tools"]:
            del payload["tools"]

        # Enable streaming
        payload["stream"] = True

        try:
            return await self._stream_completion(payload, node_config, engine_config)
        except Exception as e:
            error_message = f"OpenRouter API Error: {e}"
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

    async def _stream_completion(
        self,
        payload: dict[str, Any],
        node_config: dict[str, Any] | None,
        engine_config: dict[str, Any] | None,
    ) -> dict[str, Any]:
        """Handle streaming completion response."""
        import json as json_module

        api_call_start_time = int(time.time() * 1000)

        # Extract OpenRouter-specific params for extra_body (not supported by OpenAI SDK directly)
        extra_body: dict[str, Any] = {}
        if "provider" in payload:
            extra_body["provider"] = payload.pop("provider")
        if "reasoning" in payload:
            extra_body["reasoning"] = payload.pop("reasoning")

        # Create streaming request
        stream = await self.client.chat.completions.create(
            **payload,
            extra_body=extra_body if extra_body else None
        )

        content = ""
        role = "assistant"
        finish_reason = ""
        reasoning = ""
        tool_calls: list[dict[str, Any]] = []
        usage = UsageStats()

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
                        event["data"] = {
                            "content": getattr(delta, "content", None),
                            "reasoning": getattr(delta, "reasoning", None),
                            "role": getattr(delta, "role", None),
                            "tool_calls": getattr(delta, "tool_calls", None),
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

                # Handle finish reason
                if event["data"].get("finish_reason"):
                    finish_reason = event["data"]["finish_reason"]

                # Update usage
                if hasattr(chunk, "usage") and chunk.usage:
                    usage.prompt_tokens += chunk.usage.prompt_tokens or 0
                    usage.completion_tokens += chunk.usage.completion_tokens or 0
                    usage.total_tokens += chunk.usage.total_tokens or 0

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

        # Calculate costs
        cost_data = None
        if node_config and node_config.get("pricing"):
            cost_data = self.calculate_costs(usage, node_config["pricing"])

        result: dict[str, Any] = {
            "content": content,
            "role": role,
            "finish_reason": finish_reason,
            "tool_calls": tool_calls if tool_calls else None,
            "model": payload["model"],
            "usage": usage.to_dict(),
            "reasoning": reasoning if reasoning else None,
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
            "response": {"status": 200, "statusText": "OK"},
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
