"""Analytics tools (stub)."""
from ..registry import agent_tool


@agent_tool(
    "analytics.overview",
    schema={"range": "str"},
    required=["range"],
    requires_perm="stats.view",
    is_write=False,
)
def analytics_overview(ctx, tool_input):
    return {"status": "stub", "range": tool_input.get("range")}
