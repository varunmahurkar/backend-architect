"""
Nurav AI Tools Package
Provides a unified tool registry with auto-discovery, LangChain integration,
and metadata tracking for all AI tools.
"""

from app.tools.base import ToolMetadata, ToolStatus, ToolExample, nurav_tool
from app.tools.registry import tool_registry


def get_all_tools() -> list:
    """Get all registered tool metadata."""
    return tool_registry.get_all()


def get_tool(name: str) -> dict | None:
    """Get a single tool's metadata by name."""
    return tool_registry.get_tool(name)


__all__ = [
    "tool_registry",
    "ToolMetadata",
    "ToolStatus",
    "ToolExample",
    "nurav_tool",
    "get_all_tools",
    "get_tool",
]
