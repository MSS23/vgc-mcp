"""Structured errors stay short enough to read on a phone."""

from vgc_mcp_core.utils.errors import (
    MAX_SUGGESTIONS,
    ErrorCodes,
    api_error,
    error_response,
    team_empty_error,
)


def test_next_step_is_the_first_suggestion_and_list_is_capped():
    result = error_response(ErrorCodes.INVALID_PARAMETER, "bad", suggestions=list("abcde"))
    assert result["next_step"] == "a"
    assert result["suggestions"] == ["a", "b", "c"]
    assert len(result["suggestions"]) == MAX_SUGGESTIONS


def test_no_suggestions_means_no_next_step():
    result = error_response(ErrorCodes.INVALID_PARAMETER, "bad")
    assert "next_step" not in result and "suggestions" not in result


def test_api_error_single_argument_from_catch_all_handlers():
    result = api_error("boom")
    assert result["success"] is False
    assert result["error"] == ErrorCodes.INTERNAL_ERROR
    assert "boom" in result["message"]


def test_api_error_two_arguments_keeps_api_context():
    result = api_error("Smogon", "timeout after 30s", is_retryable=True)
    assert result["error"] == ErrorCodes.API_ERROR
    assert result["message"] == "Smogon error: timeout after 30s"
    assert result["next_step"].startswith("This may be a temporary issue")


def test_team_empty_error_names_real_tools():
    import asyncio

    from vgc_mcp.server import mcp

    registered = {t.name for t in asyncio.run(mcp.list_tools())}
    text = " ".join(team_empty_error()["suggestions"])
    for name in ("add_to_team", "import_showdown_team", "add_pokemon_smart"):
        assert name in text and name in registered
