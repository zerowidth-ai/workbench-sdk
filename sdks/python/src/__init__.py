"""
zv1 - AI Orchestration SDK

A Python implementation of ZeroWidth's zv1 framework for executing AI and
automation workflows through a visual node-based interface. Design flows
on zv1.ai, export as JSON, and execute with precision and control.

Example:
    >>> from src import Zv1
    >>> engine = await Zv1.create('./myflow.zv1', keys={'openrouter': 'sk-...'})
    >>> result = await engine.run({'chat': [{'role': 'user', 'content': 'Hello!'}]})
    >>> print(result.outputs)
"""

from src.engine import Zv1
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
