"""Usage data follows the format a calc inferred, without touching the session."""

import contextvars

from vgc_mcp_core.api.smogon import SmogonStatsClient
from vgc_mcp_core.rules.format_detect import detect_champions_format, inferred_regulation
from vgc_mcp_core.rules.regulation_loader import get_regulation_config


def _in_fresh_context(fn):
    return contextvars.copy_context().run(fn)


def test_mainline_pair_reads_mainline_usage_without_changing_session():
    def run():
        cfg = get_regulation_config()
        assert cfg.session_regulation is None
        client = SmogonStatsClient()
        default_formats = client.ACTIVE_VGC_FORMATS
        assert detect_champions_format("flutter-mane", "incineroar") is False
        assert inferred_regulation() == "reg_f"
        assert client.ACTIVE_VGC_FORMATS == cfg.get_smogon_formats("reg_f")
        assert client.ACTIVE_VGC_FORMATS != default_formats
        assert cfg.session_regulation is None
        return True

    assert _in_fresh_context(run)


def test_hint_does_not_leak_into_another_call():
    """Each MCP request runs in its own task; a hint set in one is invisible to the next."""
    import asyncio

    async def first_call():
        detect_champions_format("flutter-mane", "incineroar")
        return inferred_regulation()

    async def second_call():
        return inferred_regulation()

    async def server_loop():
        seen_first = await asyncio.create_task(first_call())
        seen_second = await asyncio.create_task(second_call())
        return seen_first, seen_second

    # A clean parent context stands in for the server's base context.
    first, second = contextvars.Context().run(asyncio.run, server_loop())
    assert first == "reg_f"
    assert second is None


def test_explicit_session_regulation_wins_over_the_hint():
    def run():
        cfg = get_regulation_config()
        cfg.set_session_regulation("reg_mc_champs")
        try:
            detect_champions_format("flutter-mane", "incineroar")
            client = SmogonStatsClient()
            assert client.ACTIVE_VGC_FORMATS == cfg.get_smogon_formats("reg_mc_champs")
        finally:
            cfg.clear_session_override()
        return True

    assert _in_fresh_context(run)
