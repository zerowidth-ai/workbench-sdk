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

from src.engine import Workbench, Zv1
from src.errors import (
    WorkbenchError,
    Zv1Error,
    NodeError,
    FlowError,
    ValidationError,
    TimeoutError,
    ResourceError,
)
from src.cache import CacheManager
from src.integrations.memory_store import (
    MemoryStoreInterface,
    FolderMemoryStore,
    InMemoryMemoryStore,
    normalize_memory_path,
)
from src.integrations.code_executor import (
    CodeExecutorInterface,
    HttpCodeExecutor,
    CodeSessionLostError,
)

__version__ = "0.5.0"
__all__ = [
    "Workbench",
    "WorkbenchError",
    "Zv1",
    "CacheManager",
    "Zv1Error",
    "NodeError",
    "FlowError",
    "ValidationError",
    "TimeoutError",
    "ResourceError",
    "MemoryStoreInterface",
    "FolderMemoryStore",
    "InMemoryMemoryStore",
    "normalize_memory_path",
    "CodeExecutorInterface",
    "HttpCodeExecutor",
    "CodeSessionLostError",
]
