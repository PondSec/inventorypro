"""Roadmap tools (stub)."""
from ..registry import agent_tool


@agent_tool(
    "roadmap.inspect",
    schema={"roadmap_id": "int"},
    required=["roadmap_id"],
    requires_perm="roadmap.view",
    is_write=False,
)
def roadmap_inspect(ctx, tool_input):
    return {"status": "stub", "roadmap_id": tool_input.get("roadmap_id")}
