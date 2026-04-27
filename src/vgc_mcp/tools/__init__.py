"""MCP tool registration package.

Each `*_tools.py` module in this package exposes a `register_*_tools(mcp, ...)`
function that decorates async functions with `@mcp.tool()`. Rather than the
server maintaining a hand-written 46-line list of imports + calls, we
auto-discover every register function here.

The auto-registration loop:

1. Walks every `*_tools.py` module in this directory.
2. Imports it and looks for a function named `register_<module_stem>`.
3. Inspects that function's parameter names and supplies matching values
   from the `deps` dict the caller passes in. Unknown / missing parameters
   are skipped (the function's defaults take over).

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
}


def _resolve_kwargs(fn: Callable[..., Any], deps: dict[str, Any]) -> dict[str, Any]:
    """Pick the subset of `deps` that matches `fn`'s parameter names (with aliases)."""
    sig = inspect.signature(fn)
    kwargs: dict[str, Any] = {}
    for param_name in sig.parameters:
        # Direct hit
        if param_name in deps:
            kwargs[param_name] = deps[param_name]
            continue
        # Alias hit — find which canonical key holds an alias for param_name
        for canonical, aliases in DEP_ALIASES.items():
            if param_name in aliases and canonical in deps:
                kwargs[param_name] = deps[canonical]
                break
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
        try:
            mod = importlib.import_module(full_name)
        except Exception as e:
            logger.error("Failed to import tool module %s: %s", full_name, e)
            continue
        register_fn_name = f"register_{mod_name}"
        register_fn = getattr(mod, register_fn_name, None)
        if register_fn is None or not callable(register_fn):
            logger.debug("Module %s has no %s function — skipping", full_name, register_fn_name)
            continue
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
        Number of tool modules successfully registered.
    """
    deps_with_mcp = {"mcp": mcp, **deps}
    count = 0
    for mod_name, register_fn in discover_register_functions():
        try:
            kwargs = _resolve_kwargs(register_fn, deps_with_mcp)
            register_fn(**kwargs)
            count += 1
            logger.debug("Registered %s", mod_name)
        except Exception as e:
            logger.exception("Failed to register %s: %s", mod_name, e)
    logger.info("Registered %d tool modules", count)
    return count
