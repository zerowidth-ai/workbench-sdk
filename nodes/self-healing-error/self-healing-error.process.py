from typing import Any

async def process(
    *,
    inputs: dict[str, Any],
    settings: dict[str, Any],
    config: dict[str, Any],
    node_config: dict[str, Any],
) -> dict[str, Any]:
    """
    Process function for the Self Healing Error node.
    Fails initially but succeeds after specified number of attempts.
    """
    value = inputs.get("value")
    fail_count = int(inputs.get("failCount", 1))
    error_message = inputs.get("errorMessage", f"Self-healing error: failing {fail_count} time(s) before success")
    
    # Get or initialize the execution count for this node instance
    if "_nodeState" not in config:
        config["_nodeState"] = {}
    
    node_id = config.get("_nodeId", "self-healing-error")
    if node_id not in config["_nodeState"]:
        config["_nodeState"][node_id] = {"executionCount": 0}
    
    state = config["_nodeState"][node_id]
    state["executionCount"] += 1
    
    # Raise error if we haven't reached the success threshold yet
    if state["executionCount"] <= fail_count:
        class SelfHealingError(Exception):
            def __init__(self, message, attempt, total_attempts):
                super().__init__(message)
                self.attempt = attempt
                self.total_attempts = total_attempts
                self.name = "SelfHealingError"
        
        error_msg = f"{error_message} (attempt {state['executionCount']}/{fail_count + 1})"
        raise SelfHealingError(error_msg, state["executionCount"], fail_count + 1)
    
    # Success! Return the value
    return {"result": value} 