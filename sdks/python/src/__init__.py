"""
Workbench - AI Orchestration SDK

A Python implementation of ZeroWidth's Workbench framework for executing AI and
automation workflows through a visual node-based interface. Design flows
on zerowidth.ai, export them, and execute with precision and control.

Example:
    >>> from workbench import Workbench
    >>> engine = await Workbench.create('./myflow.zwf', keys={'openrouter': 'sk-...'})
    >>> result = await engine.run({'chat': [{'role': 'user', 'content': 'Hello!'}]})
    >>> print(result.outputs)
"""

from src.engine import Workbench
from src.errors import (
    Zv1Error,
    NodeError,
    FlowError,
    ValidationError,
    TimeoutError,
    ResourceError,
)
from src.cache import CacheManager

__version__ = "0.4.3"
__all__ = [
    "Zv1",
    "CacheManager",
    "Zv1Error",
    "NodeError",
    "FlowError",
    "ValidationError",
    "TimeoutError",
    "ResourceError",
]
