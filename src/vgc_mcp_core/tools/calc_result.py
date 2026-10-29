"""Return annotation for tools that publish the CalcResult outputSchema."""

from typing import TYPE_CHECKING, Any

from .response_contract import CalcResult

if TYPE_CHECKING:
    CalcResultDict = dict[str, Any]
else:
    # FastMCP reads the annotation at runtime and publishes CalcResult as the
    # tool's outputSchema. The tools return plain dicts, which CalcResult
    # validates (it allows extra fields), so type checkers see a dict.
    CalcResultDict = CalcResult

__all__ = ["CalcResult", "CalcResultDict"]
