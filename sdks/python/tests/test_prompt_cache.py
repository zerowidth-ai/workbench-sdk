"""
Prompt caching: cache marks go where a model that needs them can reuse the
prompt, and nowhere else; and the provider's cache counts are kept on a
call's usage and cost breakdown. Run with:
    python tests/test_prompt_cache.py

Self-contained: no LLM calls. Mirrors sdks/nodejs/tests/test.prompt-cache.js.
"""

from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

from src.integrations.openrouter import OpenRouterIntegration  # noqa: E402
from src.utilities.prompt_cache import apply_prompt_cache, read_cache_usage  # noqa: E402

MARK = {"type": "ephemeral"}


def marked(block) -> bool:
    return isinstance(block, dict) and bool(block.get("cache_control"))


def conversation():
    return [
        {
            "role": "system",
            "content": [
                {"type": "text", "text": "You help the team.\n\n", "cache_control": MARK},
                {"type": "text", "text": "Now: 2026-10-05 12:00"},
            ],
        },
        {"role": "user", "content": "First question"},
        {"role": "assistant", "content": "First answer"},
        {"role": "user", "content": [{"type": "text", "text": "Second question"}]},
    ]


def test_claude_marks():
    source = conversation()
    out = apply_prompt_cache(source, model="anthropic/claude-sonnet-4.6")
    assert marked(out[0]["content"][0]) and not marked(out[0]["content"][1])
    assert out[1]["content"] == "First question"
    assert marked(out[3]["content"][0])
    assert not marked(source[3]["content"][0]), "the input isn't changed"


def test_other_models_unmarked():
    out = apply_prompt_cache(conversation(), model="openai/gpt-5")
    for message in out:
        if isinstance(message["content"], list):
            assert not any(marked(b) for b in message["content"])


def test_caching_off():
    out = apply_prompt_cache(conversation(), model="anthropic/claude-sonnet-4.6", enabled=False)
    assert not any(marked(b) for b in out[0]["content"])


def test_four_marks_at_most():
    many = [
        {"role": "system", "content": [{"type": "text", "text": f"part {n}", "cache_control": MARK} for n in range(5)]},
        {"role": "user", "content": "hi"},
    ]
    out = apply_prompt_cache(many, model="anthropic/claude-sonnet-4.6")
    assert [marked(b) for b in out[0]["content"]] == [True, True, True, True, False]
    assert out[1]["content"] == "hi"


def test_cache_usage_and_cost_line():
    assert read_cache_usage({"prompt_tokens_details": {"cached_tokens": 800, "cache_write_tokens": 150}}) == {
        "cached_tokens": 800,
        "cache_write_tokens": 150,
    }
    assert read_cache_usage(None) == {"cached_tokens": 0, "cache_write_tokens": 0}
    integration = OpenRouterIntegration.__new__(OpenRouterIntegration)
    cost = integration.build_cost_data(
        {"prompt_tokens": 1000, "completion_tokens": 10, "cost": 0.0012, "cached_tokens": 800, "cache_write_tokens": 150},
        None,
    )
    assert cost.total_cost == 0.0012
    assert cost.itemized_costs[0]["cached_tokens"] == 800
    assert cost.itemized_costs[0]["cache_write_tokens"] == 150
    plain = integration.build_cost_data({"prompt_tokens": 5, "completion_tokens": 2, "cost": 0.001}, None)
    assert "cached_tokens" not in plain.itemized_costs[0]


if __name__ == "__main__":
    tests = [value for name, value in sorted(globals().items()) if name.startswith("test_")]
    for test in tests:
        test()
        print(f"  ✓ {test.__name__}")
    print(f"\n{len(tests)} passed")
