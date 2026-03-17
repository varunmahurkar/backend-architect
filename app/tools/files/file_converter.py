"""
File Converter Tool — Convert files between formats.
Supports PDF→text, JSON→CSV, CSV→JSON, Markdown→HTML, HTML→text.
"""

import json
import logging
import base64
import io

from langchain_core.tools import tool
from app.tools.base import nurav_tool, ToolMetadata, ToolStatus, ToolExample

logger = logging.getLogger(__name__)


async def _download_file(url: str) -> bytes:
    """Download a file from URL."""
    import httpx
    async with httpx.AsyncClient(timeout=30.0, follow_redirects=True) as client:
        resp = await client.get(url)
        resp.raise_for_status()
        return resp.content


def _pdf_to_text(data: bytes) -> str:
    import fitz
    doc = fitz.open(stream=data, filetype="pdf")
    text = "\n\n".join(page.get_text() for page in doc)
    doc.close()
    return text


def _csv_to_json(data: bytes) -> str:
    import pandas as pd
    df = pd.read_csv(io.BytesIO(data))
    return df.to_json(orient="records", indent=2)


def _json_to_csv(data: bytes) -> str:
    import pandas as pd
    parsed = json.loads(data.decode("utf-8"))
    if isinstance(parsed, list):
        df = pd.DataFrame(parsed)
    elif isinstance(parsed, dict):
        if any(isinstance(v, list) for v in parsed.values()):
            df = pd.DataFrame(parsed)
        else:
            df = pd.DataFrame([parsed])
    else:
        raise ValueError("JSON must be an array or object")
    output = io.StringIO()
    df.to_csv(output, index=False)
    return output.getvalue()


def _markdown_to_html(text: str) -> str:
    """Simple Markdown→HTML conversion without external deps."""
    import re
    html = text
    # Headers
    for i in range(6, 0, -1):
        html = re.sub(rf'^{"#" * i}\s+(.+)$', rf'<h{i}>\1</h{i}>', html, flags=re.MULTILINE)
    # Bold and italic
    html = re.sub(r'\*\*\*(.+?)\*\*\*', r'<strong><em>\1</em></strong>', html)
    html = re.sub(r'\*\*(.+?)\*\*', r'<strong>\1</strong>', html)
    html = re.sub(r'\*(.+?)\*', r'<em>\1</em>', html)
    # Code blocks
    html = re.sub(r'```(\w*)\n(.*?)```', r'<pre><code>\2</code></pre>', html, flags=re.DOTALL)
    html = re.sub(r'`(.+?)`', r'<code>\1</code>', html)
    # Links
    html = re.sub(r'\[(.+?)\]\((.+?)\)', r'<a href="\2">\1</a>', html)
    # Lists
    html = re.sub(r'^- (.+)$', r'<li>\1</li>', html, flags=re.MULTILINE)
    # Paragraphs
    paragraphs = html.split("\n\n")
    processed = []
    for p in paragraphs:
        p = p.strip()
        if p and not p.startswith("<h") and not p.startswith("<pre") and not p.startswith("<li"):
            p = f"<p>{p}</p>"
        processed.append(p)
    return "\n".join(processed)


def _html_to_text(html: str) -> str:
    """Strip HTML tags to plain text."""
    import re
    text = re.sub(r'<script[^>]*>.*?</script>', '', html, flags=re.DOTALL | re.IGNORECASE)
    text = re.sub(r'<style[^>]*>.*?</style>', '', text, flags=re.DOTALL | re.IGNORECASE)
    text = re.sub(r'<br\s*/?>', '\n', text, flags=re.IGNORECASE)
    text = re.sub(r'</(p|div|h[1-6]|li|tr)>', '\n', text, flags=re.IGNORECASE)
    text = re.sub(r'<[^>]+>', '', text)
    text = re.sub(r'&nbsp;', ' ', text)
    text = re.sub(r'&amp;', '&', text)
    text = re.sub(r'&lt;', '<', text)
    text = re.sub(r'&gt;', '>', text)
    text = re.sub(r'\n{3,}', '\n\n', text)
    return text.strip()


def _excel_to_csv(data: bytes) -> str:
    import pandas as pd
    df = pd.read_excel(io.BytesIO(data))
    output = io.StringIO()
    df.to_csv(output, index=False)
    return output.getvalue()


SUPPORTED_CONVERSIONS = {
    ("pdf", "text"): "PDF to plain text",
    ("csv", "json"): "CSV to JSON array",
    ("json", "csv"): "JSON to CSV",
    ("markdown", "html"): "Markdown to HTML",
    ("md", "html"): "Markdown to HTML",
    ("html", "text"): "HTML to plain text",
    ("excel", "csv"): "Excel to CSV",
    ("xlsx", "csv"): "Excel to CSV",
}


@nurav_tool(metadata=ToolMetadata(
    name="file_converter",
    description="Convert files between formats. Supports PDF-to-text, CSV-to-JSON, JSON-to-CSV, Markdown-to-HTML, HTML-to-text, Excel-to-CSV.",
    niche="files",
    status=ToolStatus.ACTIVE,
    icon="repeat",
    version="1.0.0",
    examples=[
        ToolExample(
            input={"file_url": "https://example.com/doc.pdf", "from_format": "pdf", "to_format": "text"},
            output='{"success": true, "output": "...", "format": "text"}',
            description="Convert PDF to text",
        ),
    ],
    input_schema={"file_url": "str (URL or raw content)", "from_format": "str", "to_format": "str"},
    output_schema={"success": "bool", "output": "str", "format": "str", "original_size": "int"},
    avg_response_ms=3000,
    success_rate=0.92,
))
@tool
async def file_converter(file_url: str, from_format: str, to_format: str) -> str:
    """Convert file between formats."""
    if not file_url.strip():
        return json.dumps({"error": "No file URL or content provided."})

    from_f = from_format.lower().strip()
    to_f = to_format.lower().strip()

    if (from_f, to_f) not in SUPPORTED_CONVERSIONS:
        return json.dumps({
            "error": f"Unsupported conversion: {from_f} → {to_f}",
            "supported": {f"{k[0]}→{k[1]}": v for k, v in SUPPORTED_CONVERSIONS.items()},
        })

    try:
        # Get content
        if file_url.startswith("http"):
            data = await _download_file(file_url)
        else:
            data = file_url.encode("utf-8")

        original_size = len(data)

        # Convert
        if (from_f, to_f) == ("pdf", "text"):
            output = _pdf_to_text(data)
        elif (from_f, to_f) == ("csv", "json"):
            output = _csv_to_json(data)
        elif (from_f, to_f) == ("json", "csv"):
            output = _json_to_csv(data)
        elif from_f in ("markdown", "md") and to_f == "html":
            output = _markdown_to_html(data.decode("utf-8"))
        elif (from_f, to_f) == ("html", "text"):
            output = _html_to_text(data.decode("utf-8"))
        elif from_f in ("excel", "xlsx") and to_f == "csv":
            output = _excel_to_csv(data)
        else:
            return json.dumps({"error": f"Conversion not implemented: {from_f} → {to_f}"})

        # Truncate if extremely large
        truncated = len(output) > 50000
        if truncated:
            output = output[:50000] + "\n... [truncated]"

        return json.dumps({
            "success": True,
            "output": output,
            "format": to_f,
            "original_size": original_size,
            "output_size": len(output),
            "truncated": truncated,
            "conversion": f"{from_f} → {to_f}",
        })
    except Exception as e:
        return json.dumps({"error": f"Conversion failed: {str(e)}", "conversion": f"{from_f} → {to_f}"})
