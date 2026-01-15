from typing import Any
import random
import math

async def process(
    *,
    inputs: dict[str, Any],
    settings: dict[str, Any],
    config: dict[str, Any],
    node_config: dict[str, Any],
) -> dict[str, Any]:
    """
    Process function for the Random Number Generator node.
    Generates random numbers with configurable range and distribution.
    """
    # Create a JavaScript-compatible random number generator if seed is provided
    if "seed" in inputs and inputs["seed"] is not None:
        seed_value = float(inputs["seed"])
        random_func = create_seeded_random(seed_value)
    else:
        # Use Python's built-in random for unseeded random numbers
        random_func = random.random

    # Read distribution settings from settings (with inputs as fallback)
    distribution = settings.get("distribution") or inputs.get("distribution", "uniform")

    if distribution == "normal":
        # Implement Box-Muller transform for normal distribution
        mean = float(settings.get("mean") or inputs.get("mean", 0))
        stddev = float(settings.get("stddev") or inputs.get("stddev", 1))

        # Box-Muller transform to generate normal distribution from uniform
        u1 = random_func()
        u2 = random_func()
        z0 = math.sqrt(-2.0 * math.log(u1)) * math.cos(2.0 * math.pi * u2)

        value = mean + stddev * z0

    elif distribution == "integer":
        min_val = int(settings.get("min") if settings.get("min") is not None else inputs.get("min", 0))
        max_val = int(settings.get("max") if settings.get("max") is not None else inputs.get("max", 100))

        # JavaScript's Math.random() is [0, 1), so we need to adjust
        value = min_val + math.floor(random_func() * (max_val - min_val + 1))

    else:  # uniform distribution
        min_val = float(settings.get("min") if settings.get("min") is not None else inputs.get("min", 0))
        max_val = float(settings.get("max") if settings.get("max") is not None else inputs.get("max", 1))

        value = min_val + random_func() * (max_val - min_val)
    
    return {"value": value}

def create_seeded_random(seed):
    """
    A simple seeded random number generator based on a linear congruential generator
    This exactly matches the JavaScript implementation
    """
    # Constants for a simple Linear Congruential Generator
    a = 1664525
    c = 1013904223
    m = 2**32
    
    current_seed = seed
    
    def random_generator():
        nonlocal current_seed
        # Update the seed
        current_seed = (a * current_seed + c) % m
        # Return a number between 0 and 1
        return current_seed / m
    
    return random_generator 