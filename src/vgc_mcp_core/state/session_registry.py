"""Per-session state isolation for the MCP server.

The server registers its tools once at import time, capturing shared manager
instances (team / build / battle) in closures. In local **stdio** mode that is
fine — one process serves one user. But the hosted **HTTP** deployment serves
many users through one process, and a single shared `TeamManager` /
`BuildStateManager` / `BattleStateManager` means concurrent users read and
mutate each other's teams, builds, and battles.

This module keys those managers by MCP session. The MCP framework sets a
per-request `request_ctx` ContextVar whose `session` object is unique per
connection (per `Mcp-Session-Id` on the streamable-HTTP transport). We derive
the isolation key from that session object, so **no tool signatures change** —
the tools keep calling `team_manager.add(...)` and transparently hit the
manager set belonging to the caller's session.

When there is no active request context (stdio startup, unit tests, background
tasks), everything resolves to a single shared ``"default"`` manager set, so
existing single-user behavior is byte-for-byte unchanged.
"""

from __future__ import annotations

import threading
from dataclasses import dataclass
from typing import Callable, Optional

from ..team.manager import TeamManager
from .battle_manager import BattleStateManager
from .build_manager import BuildStateManager


@dataclass
class ManagerSet:
    """The mutable per-session state managers."""

    team_manager: TeamManager
    build_manager: BuildStateManager
    battle_manager: BattleStateManager

    @classmethod
    def create(cls) -> "ManagerSet":
        return cls(
            team_manager=TeamManager(),
            build_manager=BuildStateManager(),
            battle_manager=BattleStateManager(),
        )


def _current_session_key() -> object:
    """Return a stable, hashable key identifying the calling MCP session.

    Falls back to the sentinel ``"default"`` when no request context is active
    (stdio, tests, import-time), which preserves single-tenant behavior.
    """
    try:
        from mcp.server.lowlevel.server import request_ctx
    except Exception:
        return "default"
    try:
        ctx = request_ctx.get()
    except LookupError:
        return "default"
    session = getattr(ctx, "session", None)
    if session is None:
        return "default"
    # Object identity is stable for the session's lifetime. We use id() as the
    # dict key (hashable even for un-weakreffable objects) but retain a strong
    # ref in the registry's bookkeeping so the id can't be recycled underneath
    # us while the session is alive.
    return id(session)


class SessionRegistry:
    """Lazily creates and hands out one :class:`ManagerSet` per MCP session.

    Thread-safe. Bounded: at most ``max_sessions`` live sets are retained;
    the least-recently-created entry is evicted past that (a safety valve —
    real sessions are far fewer, and stdio only ever has ``"default"``).
    """

    def __init__(self, max_sessions: int = 512) -> None:
        self._lock = threading.Lock()
        self._sets: dict[object, ManagerSet] = {}
        # Keep a strong ref to the session object keyed by its id so id() can't
        # be reused for a different object while the session is alive.
        self._session_refs: dict[object, object] = {}
        self._max_sessions = max_sessions

    def current(self) -> ManagerSet:
        """Get (or create) the manager set for the calling session."""
        key = _current_session_key()
        with self._lock:
            existing = self._sets.get(key)
            if existing is not None:
                return existing
            if len(self._sets) >= self._max_sessions:
                # Evict oldest inserted (dicts preserve insertion order). Never
                # evict the "default" set.
                for oldest in list(self._sets):
                    if oldest != "default":
                        self._sets.pop(oldest, None)
                        self._session_refs.pop(oldest, None)
                        break
            new_set = ManagerSet.create()
            self._sets[key] = new_set
            if key != "default":
                try:
                    from mcp.server.lowlevel.server import request_ctx

                    self._session_refs[key] = request_ctx.get().session
                except Exception:
                    pass
            return new_set

    def session_count(self) -> int:
        with self._lock:
            return len(self._sets)


class _ManagerProxy:
    """Attribute-forwarding proxy to a per-session manager.

    Resolves the live manager on every attribute access via ``selector`` so a
    single proxy instance — captured in every tool's closure at registration
    time — always targets the calling session's manager. Only attribute/method
    access is forwarded (the managers expose named methods, not dunder
    protocols), which is all the tools use.
    """

    __slots__ = ("_selector",)

    def __init__(self, selector: Callable[[], object]) -> None:
        object.__setattr__(self, "_selector", selector)

    def __getattr__(self, name: str) -> object:
        return getattr(object.__getattribute__(self, "_selector")(), name)

    def __setattr__(self, name: str, value: object) -> None:
        setattr(object.__getattribute__(self, "_selector")(), name, value)

    def __repr__(self) -> str:  # pragma: no cover - debug aid
        return f"<SessionScoped {object.__getattribute__(self, '_selector')()!r}>"


def make_scoped_managers(
    registry: Optional[SessionRegistry] = None,
) -> tuple[SessionRegistry, _ManagerProxy, _ManagerProxy, _ManagerProxy]:
    """Build a registry plus session-scoped proxies for the three managers.

    Returns ``(registry, team_manager, build_manager, battle_manager)``. The
    proxies are drop-in replacements for the concrete managers in
    ``register_all_tools``.
    """
    reg = registry or SessionRegistry()
    team = _ManagerProxy(lambda: reg.current().team_manager)
    build = _ManagerProxy(lambda: reg.current().build_manager)
    battle = _ManagerProxy(lambda: reg.current().battle_manager)
    return reg, team, build, battle
