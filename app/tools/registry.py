"""
Tool Registry — Auto-discovery of tools with metadata caching.
Scans app/tools/*/ subdirectories, imports modules, and finds functions
decorated with @nurav_tool by checking for ._nurav_metadata attribute.
"""

import importlib
import inspect
import logging
import pkgutil
from pathlib import Path
from typing import Dict, List, Optional, Any, Callable

from app.tools.base import ToolMetadata, ToolStatus

logger = logging.getLogger(__name__)

TOOLS_PACKAGE = "app.tools"
TOOLS_DIR = Path(__file__).parent


class ToolRegistry:
    """Auto-discovery registry for Nurav AI tools."""

    def __init__(self):
        self._manifest: Dict[str, ToolMetadata] = {}
        self._tools: Dict[str, Any] = {}  # name -> decorated function
        self._scanned = False

    def scan(self) -> None:
        """Walk app/tools/*/ subdirs and discover all @nurav_tool decorated functions."""
        self._manifest.clear()
        self._tools.clear()

        niche_dirs = [
            d for d in TOOLS_DIR.iterdir()
            if d.is_dir() and not d.name.startswith("__")
        ]

        for niche_dir in niche_dirs:
            niche_name = niche_dir.name
            module_files = [
                f for f in niche_dir.glob("*.py")
                if not f.name.startswith("__")
            ]

            for module_file in module_files:
                module_name = f"{TOOLS_PACKAGE}.{niche_name}.{module_file.stem}"
                try:
                    module = importlib.import_module(module_name)
                    # Reload if already imported (for hot reload)
                    module = importlib.reload(module)

                    for attr_name in dir(module):
                        obj = getattr(module, attr_name)
                        if hasattr(obj, "_nurav_metadata"):
                            metadata: ToolMetadata = obj._nurav_metadata
                            self._manifest[metadata.name] = metadata
                            self._tools[metadata.name] = obj
                            logger.debug(f"Registered tool: {metadata.name} ({metadata.niche}/{metadata.status.value})")

                except Exception as e:
                    logger.warning(f"Failed to import tool module {module_name}: {e}")

        self._scanned = True
        niches = set(m.niche for m in self._manifest.values())
        logger.info(f"Scanned {len(self._manifest)} tools from {len(niches)} niches")

    def get_all(self) -> List[dict]:
        """Return all tool metadata as dicts."""
        return [m.to_dict() for m in self._manifest.values()]

    def get_by_niche(self, niche: str) -> List[dict]:
        """Return tool metadata filtered by niche."""
        return [
            m.to_dict() for m in self._manifest.values()
            if m.niche == niche
        ]

    def get_tool(self, name: str) -> Optional[dict]:
        """Return single tool metadata dict by name."""
        meta = self._manifest.get(name)
        return meta.to_dict() if meta else None

    def get_tool_function(self, name: str) -> Optional[Callable]:
        """Return the tool function by name."""
        tool = self._tools.get(name)
        if tool and hasattr(tool, "_langchain_tool"):
            return tool._langchain_tool
        return tool

    def get_langchain_tools(self) -> List[Any]:
        """Return list of LangChain tool objects for bind_tools."""
        tools = []
        for name, tool in self._tools.items():
            meta = self._manifest.get(name)
            if meta and meta.status == ToolStatus.ACTIVE:
                lc_tool = getattr(tool, "_langchain_tool", tool)
                tools.append(lc_tool)
        return tools

    def get_niches(self) -> List[str]:
        """Return list of all unique niches."""
        return sorted(set(m.niche for m in self._manifest.values()))

    def refresh(self) -> None:
        """Re-scan all tool modules (for hot reload in dev)."""
        logger.info("Refreshing tool registry...")
        self.scan()

    @property
    def is_scanned(self) -> bool:
        return self._scanned

    @property
    def count(self) -> int:
        return len(self._manifest)


# Singleton instance
tool_registry = ToolRegistry()
