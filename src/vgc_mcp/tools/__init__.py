"""MCP tool registration package.

Each `*_tools.py` module in this package exposes a `register_*_tools(mcp, ...)`
function that decorates async functions with `@mcp.tool()`. Rather than the
server maintaining a hand-written 46-line list of imports + calls, we
auto-discover every register function here.

The auto-registration loop:

1. Walks every `*_tools.py` module in this directory.
2. Imports it and looks for a function named `register_<module_stem>`.
3. Inspects that function's parameter names and supplies matching values
   from the `deps` dict the caller passes in.

Discovery is deliberately fail-fast. A hosted server must never advertise
itself as healthy with a silently partial tool surface, so import failures,
misnamed registration functions, missing required dependencies, empty modules,
and duplicate tool names all abort startup with a clear error.

This means adding a new tool file requires zero changes to server.py — just
drop `<area>_tools.py` in this directory with a `register_<area>_tools(mcp, ...)`
function and it will be picked up automatically.
"""

from __future__ import annotations

import importlib
import inspect
import logging
import pkgutil
from typing import Any, Callable

logger = logging.getLogger(__name__)


# Common parameter-name aliases — different tool files use different names
# for the same dependency (e.g. `smogon` vs `smogon_client`). The registry
# normalises on the canonical key, then resolves aliases.
DEP_ALIASES: dict[str, list[str]] = {
    "mcp": ["mcp"],
    "pokeapi": ["pokeapi", "pokeapi_client"],
    "smogon": ["smogon", "smogon_client"],
    "pokepaste": ["pokepaste", "pokepaste_client"],
    "team_manager": ["team_manager"],
    "analyzer": ["analyzer", "team_analyzer"],
    "build_manager": ["build_manager"],
    "battle_manager": ["battle_manager"],
}


def _resolve_kwargs(fn: Callable[..., Any], deps: dict[str, Any]) -> dict[str, Any]:
    """Resolve dependencies for ``fn`` and reject missing required inputs."""
    sig = inspect.signature(fn)
    kwargs: dict[str, Any] = {}
    for param_name, param in sig.parameters.items():
        # Direct hit
        if param_name in deps:
            kwargs[param_name] = deps[param_name]
            continue
        # Alias hit — find which canonical key holds an alias for param_name
        for canonical, aliases in DEP_ALIASES.items():
            if param_name in aliases and canonical in deps:
                kwargs[param_name] = deps[canonical]
                break

        if (
            param_name not in kwargs
            and param.default is inspect.Parameter.empty
            and param.kind
            in (
                inspect.Parameter.POSITIONAL_ONLY,
                inspect.Parameter.POSITIONAL_OR_KEYWORD,
                inspect.Parameter.KEYWORD_ONLY,
            )
        ):
            raise RuntimeError(
                f"Cannot register {fn.__module__}.{fn.__name__}: "
                f"required dependency {param_name!r} was not provided"
            )
    return kwargs


def discover_register_functions() -> list[tuple[str, Callable[..., Any]]]:
    """Find every `register_<module>_tools` function in this package.

    Returns:
        List of (module_name, register_function) tuples, sorted by module name
        for deterministic registration order.
    """
    found: list[tuple[str, Callable[..., Any]]] = []
    for _, mod_name, ispkg in pkgutil.iter_modules(__path__):
        if ispkg or not mod_name.endswith("_tools"):
            continue
        full_name = f"{__name__}.{mod_name}"
        mod = importlib.import_module(full_name)
        register_fn_name = f"register_{mod_name}"
        register_fn = getattr(mod, register_fn_name, None)
        if register_fn is None or not callable(register_fn):
            raise RuntimeError(
                f"Tool module {full_name} must expose callable {register_fn_name}"
            )
        found.append((mod_name, register_fn))
    found.sort(key=lambda t: t[0])
    return found


def register_all(mcp: Any, **deps: Any) -> int:
    """Register every discovered tool module against `mcp`.

    Args:
        mcp: FastMCP instance.
        **deps: Dependencies to pass to register functions. Keys should match
            the canonical names in DEP_ALIASES (mcp, pokeapi, smogon, pokepaste,
            team_manager, analyzer, build_manager).

    Returns:
        Number of tool modules registered. Any incomplete or ambiguous
        registration raises ``RuntimeError`` and prevents server startup.
    """
    deps_with_mcp = {"mcp": mcp, **deps}
    count = 0
    for mod_name, register_fn in discover_register_functions():
        kwargs = _resolve_kwargs(register_fn, deps_with_mcp)
        tool_manager = mcp._tool_manager
        before = set(tool_manager._tools)
        original_add_tool = tool_manager.add_tool

        def checked_add_tool(
            fn: Callable[..., Any],
            name: str | None = None,
            *args: Any,
            **tool_kwargs: Any,
        ) -> Any:
            candidate_name = name or fn.__name__
            if candidate_name in before:
                raise RuntimeError(
                    f"Tool module {mod_name} attempted duplicate tool name: "
                    f"{candidate_name}"
                )
            return original_add_tool(fn, name, *args, **tool_kwargs)

        tool_manager.add_tool = checked_add_tool
        try:
            register_fn(**kwargs)
        finally:
            tool_manager.add_tool = original_add_tool

        after = tool_manager._tools

        new_tools = set(after) - before
        if not new_tools:
            raise RuntimeError(f"Tool module {mod_name} registered no tools")

        count += 1
        logger.debug("Registered %s (%d tools)", mod_name, len(new_tools))
    logger.info("Registered %d tool modules", count)
    return count
