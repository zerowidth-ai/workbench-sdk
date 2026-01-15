"""
Loop End Node - Decides whether to continue or exit loop.
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
    Process function for the Loop End node.
    """
    # Get current iteration count from settings (persisted state)
    current_iteration = (settings.get("_loop_iteration") or 0) + 1

    # Get all values array from settings (persisted state)
    all_values = settings.get("_all_values") or []

    # Add current value to the array
    all_values.append(inputs.get("value"))

    # Get loop control parameters
    loop_limit = inputs.get("loop_limit") if inputs.get("loop_limit") is not None else 10
    while_condition = inputs.get("while_condition") if inputs.get("while_condition") is not None else True

    # Determine if we should continue looping
    should_continue = while_condition and current_iteration < loop_limit

    # Determine values to use for loop_back and final_value
    loop_value = inputs.get("loop_value") if inputs.get("loop_value") is not None else inputs.get("value")
    final_value = inputs.get("final_value") if inputs.get("final_value") is not None else inputs.get("value")

    # Prepare outputs
    outputs = {
        "loop_back": None,
        "final_value": None,
        "total_iterations": None,
        "all_values": None,
    }

    if should_continue:
        # Continue looping - send loop_value back to loop start
        outputs["loop_back"] = loop_value

        # Update internal state for next iteration
        outputs["__updated_settings"] = {
            "_loop_iteration": current_iteration,
            "_all_values": all_values,
        }
    else:
        # Exit loop - output final results
        outputs["final_value"] = final_value
        outputs["total_iterations"] = current_iteration
        outputs["all_values"] = list(all_values)  # Return a copy

        # Reset iteration count and values array for next loop
        outputs["__updated_settings"] = {
            "_loop_iteration": 0,
            "_all_values": [],
        }

    return outputs
