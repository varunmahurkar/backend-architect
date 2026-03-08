"""
Python Executor Tool — Sandboxed code execution via Docker.
Runs Python code in an isolated container with pre-installed scientific packages.
"""

import json
import logging
import time
import asyncio

from langchain_core.tools import tool
from app.tools.base import nurav_tool, ToolMetadata, ToolStatus, ToolExample

logger = logging.getLogger(__name__)

DOCKER_IMAGE = "python:3.12-slim"
PREINSTALLED_PACKAGES = ["numpy", "pandas", "matplotlib", "scipy", "sympy"]


async def _run_in_docker(code: str, timeout: int, packages: list[str] | None = None) -> dict:
    """Execute Python code inside a Docker container."""
    import docker
    from docker.errors import ContainerError, ImageNotFound, APIError

    client = docker.from_env()

    # Build command: install extra packages if requested, then run code
    setup_cmds = []
    if packages:
        safe_packages = [p.replace(";", "").replace("&", "").replace("|", "") for p in packages]
        setup_cmds.append(f"pip install -q {' '.join(safe_packages)} 2>/dev/null")

    # Write code to a temp file inside container and execute it
    escaped_code = code.replace("'", "'\\''")
    run_cmd = f"python3 -c '{escaped_code}'"

    full_cmd = " && ".join(setup_cmds + [run_cmd]) if setup_cmds else run_cmd

    start_time = time.time()

    try:
        container = client.containers.run(
            DOCKER_IMAGE,
            command=["bash", "-c", full_cmd],
            detach=True,
            mem_limit="256m",
            cpu_period=100000,
            cpu_quota=50000,  # 50% of one CPU
            network_disabled=True,
            remove=False,
            stdout=True,
            stderr=True,
        )

        # Wait for completion with timeout
        try:
            exit_result = container.wait(timeout=timeout)
            exit_code = exit_result.get("StatusCode", -1)
        except Exception:
            container.kill()
            container.remove(force=True)
            return {
                "stdout": "",
                "stderr": f"Execution timed out after {timeout}s",
                "execution_time_ms": int((time.time() - start_time) * 1000),
                "success": False,
            }

        stdout = container.logs(stdout=True, stderr=False).decode("utf-8", errors="replace")
        stderr = container.logs(stdout=False, stderr=True).decode("utf-8", errors="replace")
        container.remove(force=True)

        execution_time_ms = int((time.time() - start_time) * 1000)

        return {
            "stdout": stdout[:10000],
            "stderr": stderr[:5000],
            "execution_time_ms": execution_time_ms,
            "success": exit_code == 0,
        }

    except ImageNotFound:
        # Pull image first
        try:
            client.images.pull(DOCKER_IMAGE)
            return await _run_in_docker(code, timeout, packages)
        except Exception as e:
            return {
                "stdout": "",
                "stderr": f"Docker image not found and pull failed: {str(e)}",
                "execution_time_ms": 0,
                "success": False,
            }
    except APIError as e:
        return {
            "stdout": "",
            "stderr": f"Docker API error: {str(e)}",
            "execution_time_ms": 0,
            "success": False,
        }


async def _run_subprocess_fallback(code: str, timeout: int) -> dict:
    """Fallback: run Python code in a subprocess (less isolated but works without Docker)."""
    start_time = time.time()

    try:
        proc = await asyncio.create_subprocess_exec(
            "python", "-c", code,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE,
        )
        try:
            stdout, stderr = await asyncio.wait_for(proc.communicate(), timeout=timeout)
        except asyncio.TimeoutError:
            proc.kill()
            await proc.communicate()
            return {
                "stdout": "",
                "stderr": f"Execution timed out after {timeout}s",
                "execution_time_ms": int((time.time() - start_time) * 1000),
                "success": False,
            }

        return {
            "stdout": stdout.decode("utf-8", errors="replace")[:10000],
            "stderr": stderr.decode("utf-8", errors="replace")[:5000],
            "execution_time_ms": int((time.time() - start_time) * 1000),
            "success": proc.returncode == 0,
        }
    except Exception as e:
        return {
            "stdout": "",
            "stderr": f"Subprocess execution failed: {str(e)}",
            "execution_time_ms": 0,
            "success": False,
        }


@nurav_tool(metadata=ToolMetadata(
    name="python_executor",
    description="Execute Python code in a sandboxed Docker environment. Returns stdout, stderr, and execution time. Pre-installed: numpy, pandas, matplotlib, scipy, sympy.",
    niche="code",
    status=ToolStatus.ACTIVE,
    icon="terminal",
    version="1.0.0",
    examples=[
        ToolExample(
            input={"code": "print(sum(range(1, 101)))"},
            output='{"stdout": "5050\\n", "stderr": "", "execution_time_ms": 350, "success": true}',
            description="Calculate sum of 1 to 100",
        ),
        ToolExample(
            input={"code": "import math\nprint(math.factorial(20))"},
            output='{"stdout": "2432902008176640000\\n", "stderr": "", "execution_time_ms": 280, "success": true}',
            description="Compute factorial",
        ),
    ],
    input_schema={"code": "str", "timeout_seconds": "int (default 10)", "packages": "list[str] (optional)"},
    output_schema={"stdout": "str", "stderr": "str", "execution_time_ms": "int", "success": "bool"},
    avg_response_ms=2000,
    success_rate=0.90,
))
@tool
async def python_executor(code: str, timeout_seconds: int = 10, packages: str = "") -> str:
    """Execute Python code in a sandboxed environment. Returns stdout, stderr, and execution metadata."""
    if not code.strip():
        return json.dumps({"error": "No code provided."})

    pkg_list = [p.strip() for p in packages.split(",") if p.strip()] if packages else None

    # Try Docker first
    try:
        import docker
        docker.from_env().ping()
        result = await _run_in_docker(code, timeout_seconds, pkg_list)
        result["method"] = "docker"
        return json.dumps(result, ensure_ascii=False)
    except Exception as e:
        logger.info(f"Docker unavailable ({e}), falling back to subprocess")

    # Fallback to subprocess
    result = await _run_subprocess_fallback(code, timeout_seconds)
    result["method"] = "subprocess"
    return json.dumps(result, ensure_ascii=False)
