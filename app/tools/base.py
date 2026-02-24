"""
Tool Base — ToolMetadata, ToolStatus, and @nurav_tool decorator.
Provides the foundation for all Nurav AI tools with metadata tracking
and LangChain @tool integration.
"""

import functools
import logging
from dataclasses import dataclass, field, asdict
from enum import Enum
from typing import List, Optional, Callable, Any

logger = logging.getLogger(__name__)


class ToolStatus(str, Enum):
    ACTIVE = "active"
    BETA = "beta"
    COMING_SOON = "coming_soon"
    DEPRECATED = "deprecated"


@dataclass
class ToolExample:
    """Example input/output pair for a tool."""
    input: dict
    output: str
    description: str = ""


@dataclass
class ToolMetadata:
    """Metadata describing a Nurav AI tool."""
    name: str
    description: str
    niche: str
    status: ToolStatus = ToolStatus.ACTIVE
    icon: str = "wrench"
    version: str = "1.0.0"
    examples: List[ToolExample] = field(default_factory=list)
    input_schema: Optional[dict] = None
    output_schema: Optional[dict] = None
    rate_limit: Optional[str] = None
    avg_response_ms: Optional[int] = None
    cost_per_call: Optional[float] = None
    success_rate: Optional[float] = None

    def to_dict(self) -> dict:
        """Convert to serializable dictionary."""
        d = asdict(self)
        d["status"] = self.status.value
        return d


def nurav_tool(metadata: ToolMetadata) -> Callable:
    """
    Decorator that attaches ToolMetadata to a function.
    Apply BEFORE @tool so the metadata is preserved on the outer function.

    Usage:
        @nurav_tool(metadata=ToolMetadata(...))
        @tool
        async def my_tool(query: str) -> str:
            ...
    """
    def decorator(func: Callable) -> Callable:
        @functools.wraps(func)
        def wrapper(*args: Any, **kwargs: Any) -> Any:
            return func(*args, **kwargs)

        # Attach metadata to the wrapper
        wrapper._nurav_metadata = metadata
        # Also propagate any LangChain tool attributes
        if hasattr(func, 'name'):
            wrapper.name = func.name
        if hasattr(func, 'description'):
            wrapper.description = func.description
        if hasattr(func, 'args_schema'):
            wrapper.args_schema = func.args_schema
        if hasattr(func, 'invoke'):
            wrapper.invoke = func.invoke
        if hasattr(func, 'ainvoke'):
            wrapper.ainvoke = func.ainvoke
        # Copy over the original function for LangChain compatibility
        wrapper._langchain_tool = func

        return wrapper

    return decorator
