"""
Mind Map Generator Tool — Generate mind maps from topics or text.
Produces Mermaid mindmap code + structured node JSON.
"""

import json
import logging
import re

from langchain_core.tools import tool
from app.tools.base import nurav_tool, ToolMetadata, ToolStatus, ToolExample

logger = logging.getLogger(__name__)


def _nodes_to_mermaid(nodes: dict, depth: int = 0) -> list[str]:
    """Recursively convert node dict to Mermaid mindmap lines."""
    lines = []
    indent = "  " * (depth + 1)
    label = nodes.get("label", "")
    if depth == 0:
        lines.append(f"  root(({label}))")
    else:
        lines.append(f"{indent}{label}")
    for child in nodes.get("children", []):
        lines.extend(_nodes_to_mermaid(child, depth + 1))
    return lines


@nurav_tool(metadata=ToolMetadata(
    name="mindmap_generator",
    description="Generate mind maps from topics, text, or structured data. Returns Mermaid code, structured node data, and a text outline. Better than competitors with LLM-generated, semantically rich hierarchies.",
    niche="visualization",
    status=ToolStatus.ACTIVE,
    icon="git-fork",
    version="1.0.0",
    examples=[
        ToolExample(
            input={"topic": "Machine Learning", "depth": 3, "format": "mermaid"},
            output='{"mermaid_code": "mindmap\\n  root((ML))\\n    Supervised\\n      Classification\\n      Regression", "nodes": {...}, "outline": "..."}',
            description="Generate a mind map about ML",
        ),
    ],
    input_schema={"topic": "str", "depth": "int (default 3, max 4)", "style": "str ('radial'|'tree'|'organic')", "format": "str ('mermaid'|'json'|'outline')"},
    output_schema={"mermaid_code": "str", "nodes": "dict", "outline": "str", "total_nodes": "int"},
    avg_response_ms=4000,
    success_rate=0.93,
))
@tool
async def mindmap_generator(topic: str, depth: int = 3, style: str = "radial", format: str = "mermaid") -> str:
    """Generate a mind map for the given topic."""
    if not topic.strip():
        return json.dumps({"error": "No topic provided."})

    depth = max(1, min(4, depth))

    try:
        from app.services.llm_service import get_llm
        from langchain_core.messages import HumanMessage, SystemMessage

        system = f"""You are an expert knowledge architect creating mind maps.
Generate a comprehensive mind map for the given topic with exactly {depth} levels of depth.
Style: {style} — organize nodes in a {style} layout pattern.

Respond ONLY with valid JSON representing the mind map tree:
{{
  "label": "Main Topic",
  "children": [
    {{
      "label": "Branch 1",
      "children": [
        {{"label": "Sub-concept", "children": []}}
      ]
    }}
  ]
}}

Rules:
- Root node: the main topic
- Level 1: 4-6 major branches
- Level 2+: 2-4 children per node
- Labels: concise (1-5 words), meaningful
- Cover all key aspects of the topic comprehensively"""

        llm = get_llm(provider="google")
        resp = await llm.ainvoke([
            SystemMessage(content=system),
            HumanMessage(content=f"Create a {depth}-level mind map for: {topic}"),
        ])
        result_text = resp.content.strip()
        if result_text.startswith("```"):
            result_text = "\n".join(result_text.split("\n")[1:-1])

        nodes = json.loads(result_text)

        # Generate Mermaid code
        mermaid_lines = ["mindmap"] + _nodes_to_mermaid(nodes)
        mermaid_code = "\n".join(mermaid_lines)

        # Generate text outline
        def to_outline(node: dict, indent: int = 0) -> list[str]:
            prefix = "  " * indent + ("• " if indent > 0 else "# ")
            lines = [prefix + node.get("label", "")]
            for child in node.get("children", []):
                lines.extend(to_outline(child, indent + 1))
            return lines

        outline = "\n".join(to_outline(nodes))

        # Count total nodes
        def count_nodes(node: dict) -> int:
            return 1 + sum(count_nodes(c) for c in node.get("children", []))

        total = count_nodes(nodes)

        return json.dumps({
            "mermaid_code": mermaid_code,
            "nodes": nodes,
            "outline": outline,
            "total_nodes": total,
            "depth": depth,
            "style": style,
            "topic": topic,
        })
    except json.JSONDecodeError:
        return json.dumps({"error": "Could not generate structured mind map. Try a more specific topic."})
    except Exception as e:
        return json.dumps({"error": f"Mind map generation failed: {str(e)}"})
