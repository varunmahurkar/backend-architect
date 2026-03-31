"""
JavaScript Executor Tool — Run JS/Node.js code via Docker or subprocess.
Similar architecture to python_executor with Node.js runtime.
"""

import json
import logging
import time
import asyncio

from langchain_core.tools import tool
from app.tools.base import nurav_tool, ToolMetadata, ToolStatus, ToolExample, tool_error

logger = logging.getLogger(__name__)

try:
    import docker as _docker_module
    DOCKER_AVAILABLE = True
except ImportError:
    DOCKER_AVAILABLE = False

NODE_IMAGE = "node:20-slim"


def _run_js_docker_sync(code: str, timeout: int) -> dict:
    """Synchronous Docker execution for JS — runs in a thread via asyncio.to_thread."""
    import docker
    from docker.errors import ImageNotFound

    client = docker.from_env()
    escaped = code.replace("'", "'\\''")
    cmd = f"node -e '{escaped}'"
    start = time.time()

    try:
        container = client.containers.run(
            NODE_IMAGE,
            command=["bash", "-c", cmd],
            detach=True, mem_limit="256m", network_disabled=True, remove=False,
            cpu_period=100000, cpu_quota=50000,
        )
        try:
            exit_result = container.wait(timeout=timeout)
            exit_code = exit_result.get("StatusCode", -1)
        except Exception:
            container.kill()
            container.remove(force=True)
            return {"stdout": "", "stderr": f"Timed out after {timeout}s", "execution_time_ms": int((time.time()-start)*1000), "success": False}

        stdout = container.logs(stdout=True, stderr=False).decode("utf-8", errors="replace")
        stderr = container.logs(stdout=False, stderr=True).decode("utf-8", errors="replace")
        container.remove(force=True)
        return {"stdout": stdout[:10000], "stderr": stderr[:5000], "execution_time_ms": int((time.time()-start)*1000), "success": exit_code == 0}
    except ImageNotFound:
        client.images.pull(NODE_IMAGE)
        return _run_js_docker_sync(code, timeout)


async def _run_js_docker(code: str, timeout: int) -> dict:
    """Async wrapper — offloads blocking Docker calls to a thread pool."""
    return await asyncio.to_thread(_run_js_docker_sync, code, timeout)


async def _run_js_subprocess(code: str, timeout: int) -> dict:
    """Fallback: run via local node."""
    start = time.time()
    try:
        proc = await asyncio.create_subprocess_exec(
            "node", "-e", code,
            stdout=asyncio.subprocess.PIPE, stderr=asyncio.subprocess.PIPE,
        )
        try:
            stdout, stderr = await asyncio.wait_for(proc.communicate(), timeout=timeout)
        except asyncio.TimeoutError:
            proc.kill()
            await proc.communicate()
            return {"stdout": "", "stderr": f"Timed out after {timeout}s", "execution_time_ms": int((time.time()-start)*1000), "success": False}
        return {"stdout": stdout.decode()[:10000], "stderr": stderr.decode()[:5000], "execution_time_ms": int((time.time()-start)*1000), "success": proc.returncode == 0}
    except FileNotFoundError:
        return {"stdout": "", "stderr": "Node.js not found. Install Node.js or ensure Docker is running.", "execution_time_ms": 0, "success": False}


@nurav_tool(metadata=ToolMetadata(
    name="javascript_executor",
    description="Execute JavaScript/Node.js code in a sandboxed Docker environment. Returns stdout, stderr, and execution time.",
    niche="code",
    status=ToolStatus.ACTIVE,
    icon="braces",
    version="1.0.0",
    examples=[
        ToolExample(
            input={"code": "console.log(Array.from({length: 10}, (_, i) => i*i))"},
            output='{"stdout": "[0,1,4,9,16,25,36,49,64,81]\\n", "success": true, "execution_time_ms": 120}',
            description="Generate array of squares",
        ),
    ],
    input_schema={"code": "str", "timeout": "int (default 10)"},
    output_schema={"stdout": "str", "stderr": "str", "execution_time_ms": "int", "success": "bool"},
    avg_response_ms=2000,
    success_rate=0.88,
))
@tool
async def javascript_executor(code: str, timeout: int = 10) -> str:
    """Execute JavaScript code in a sandboxed environment."""
    if not code.strip():
        return tool_error("No code provided.", code="INVALID_INPUT", suggestion="Provide JavaScript code to execute.")

    if DOCKER_AVAILABLE:
        try:
            await asyncio.to_thread(_docker_module.from_env().ping)
            result = await _run_js_docker(code, timeout)
            result["method"] = "docker"
            return json.dumps(result)
        except Exception as e:
            logger.info(f"[javascript_executor] Docker unavailable ({e}), falling back to subprocess")
    else:
        logger.info("[javascript_executor] docker package not installed, falling back to subprocess")

    result = await _run_js_subprocess(code, timeout)
    result["method"] = "subprocess"
    return json.dumps(result)
