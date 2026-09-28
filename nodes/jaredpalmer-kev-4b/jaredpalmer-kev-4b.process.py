"""
Jared Palmer: Kev 4B - Decision (System One) node for the zv1 engine.
"""

from typing import Any


async def process(
    *,
    inputs: dict[str, Any],
    settings: dict[str, Any],
    config: dict[str, Any],
    node_config: dict[str, Any],
) -> dict[str, Any]:
    """
    Process function for the Jared Palmer: Kev 4B decision node.

    Args:
        inputs: Node inputs containing the state and a map of typed questions.
        settings: Node settings (unused for decision nodes).
        config: Engine configuration with integrations and keys.
        node_config: Node configuration from config.json.

    Returns:
        Dictionary with typed answers, primary values, model, usage and cost data.
    """
    # Get OpenRouter integration from engine
    openrouter = config.get("integrations", {}).get("openrouter")
    if not openrouter:
        raise RuntimeError("OpenRouter integration not available")

    response = await openrouter.system_one(
        model="jaredpalmer/kev-4b",
        state=inputs.get("state"),
        questions=inputs.get("questions"),
        node_config=node_config,
        engine_config=config,
    )

    # Primary value per answer type, for easy wiring downstream
    answers = response.get("answers") or {}
    values = {
        qid: (answer.get(answer.get("type")) if isinstance(answer, dict) else None)
        for qid, answer in answers.items()
    }

    return {
        "answers": answers,
        "values": values,
        "model": response.get("model"),
        "usage": response.get("usage"),
        "cost_total": response.get("cost_total"),
        "cost_itemized": response.get("cost_itemized"),
    }