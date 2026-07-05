"""Tests for per-session state isolation (session_registry)."""

from unittest.mock import patch

from vgc_mcp_core.state.session_registry import (
    ManagerSet,
    SessionRegistry,
    make_scoped_managers,
)


class FakeSession:
    """Stand-in for an MCP ServerSession (identity is what matters)."""


class FakeRequestCtx:
    def __init__(self, session):
        self.session = session


def _patch_session(session):
    """Patch request_ctx.get() to return a ctx carrying `session`.

    Passing None simulates 'no active request context' (stdio / tests).
    """
    class _Var:
        def get(self):
            if session is None:
                raise LookupError("no context")
            return FakeRequestCtx(session)

    return patch("mcp.server.lowlevel.server.request_ctx", _Var())


def test_no_context_uses_default_session():
    reg = SessionRegistry()
    with _patch_session(None):
        a = reg.current()
        b = reg.current()
    assert a is b  # same "default" set every time
    assert reg.session_count() == 1


def test_distinct_sessions_get_isolated_managers():
    reg = SessionRegistry()
    s1, s2 = FakeSession(), FakeSession()

    with _patch_session(s1):
        set1 = reg.current()
    with _patch_session(s2):
        set2 = reg.current()

    assert set1 is not set2
    assert set1.team_manager is not set2.team_manager
    assert set1.battle_manager is not set2.battle_manager
    assert reg.session_count() == 2


def test_same_session_reused_across_calls():
    reg = SessionRegistry()
    s1 = FakeSession()
    with _patch_session(s1):
        first = reg.current()
        second = reg.current()
    assert first is second


def _make_pokemon(name):
    from vgc_mcp_core.models.pokemon import BaseStats, EVSpread, Nature, PokemonBuild

    return PokemonBuild(
        name=name,
        base_stats=BaseStats(
            hp=100, attack=100, defense=100,
            special_attack=100, special_defense=100, speed=100,
        ),
        nature=Nature.SERIOUS,
        evs=EVSpread(),
        types=["Dragon"],
    )


def test_scoped_proxy_delegates_and_isolates_team_state():
    _reg, team, _build, _battle = make_scoped_managers()
    s1, s2 = FakeSession(), FakeSession()

    # Mutate through the proxy in one session; the other must not see it.
    with _patch_session(s1):
        team.clear()
        ok, _msg, _data = team.add_pokemon(_make_pokemon("garchomp"))
        assert ok is True
        assert team.size == 1

    with _patch_session(s2):
        team.clear()
        assert team.size == 0  # session 2 never saw session 1's Garchomp

    # Back in session 1, the Garchomp is still there (state persisted per session).
    with _patch_session(s1):
        assert team.size == 1


def test_max_sessions_eviction_preserves_default():
    reg = SessionRegistry(max_sessions=2)
    with _patch_session(None):
        reg.current()  # default
    sessions = [FakeSession() for _ in range(3)]
    for s in sessions:
        with _patch_session(s):
            reg.current()
    # Never evicts default; capacity bounded.
    assert reg.session_count() <= 2
    with _patch_session(None):
        assert reg.current() is not None  # default still resolvable


def test_manager_set_create_produces_independent_instances():
    a = ManagerSet.create()
    b = ManagerSet.create()
    assert a.team_manager is not b.team_manager
