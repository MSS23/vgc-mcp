"""Deployment readiness smoke tests.

Converted from the old root-level `test_deploy.py` (which pytest never
collected because `testpaths = ["tests"]`). These verify the import graph and
entry points the hosted deployment depends on. The HTTP-transport checks skip
cleanly when the optional `[remote]` extra (uvicorn/starlette) isn't installed,
so they don't fail the default `[dev]`-only test job.
"""

import importlib.util
import inspect

import pytest

REMOTE_AVAILABLE = (
    importlib.util.find_spec("uvicorn") is not None
    and importlib.util.find_spec("starlette") is not None
)


def test_core_config_imports():
    from vgc_mcp_core.config import logger  # noqa: F401


def test_nature_optimization_imports():
    from vgc_mcp_core.calc.nature_optimization import (  # noqa: F401
        find_optimal_nature_for_benchmarks,
    )


def test_server_module_loads_with_tools():
    from vgc_mcp.server import (
        REGISTERED_TOOL_COUNT,
        REGISTERED_TOOL_MODULE_COUNT,
        mcp,
    )
    from vgc_mcp.tools import discover_register_functions

    tools = mcp._tool_manager._tools
    discovered_modules = discover_register_functions()
    assert REGISTERED_TOOL_MODULE_COUNT == len(discovered_modules)
    assert REGISTERED_TOOL_COUNT == len(tools)
    assert REGISTERED_TOOL_MODULE_COUNT == 51
    assert REGISTERED_TOOL_COUNT == 208
    assert len(tools) == len(set(tools)), "tool names must be unique"


def test_main_http_entrypoint_is_callable():
    from vgc_mcp.server import main_http

    sig = inspect.signature(main_http)
    assert "host" in sig.parameters
    assert "port" in sig.parameters


@pytest.mark.skipif(not REMOTE_AVAILABLE, reason="requires the [remote] extra")
def test_http_transport_dependencies_importable():
    import starlette  # noqa: F401
    import uvicorn  # noqa: F401
    from mcp.server.sse import SseServerTransport  # noqa: F401
    from starlette.applications import Starlette  # noqa: F401
