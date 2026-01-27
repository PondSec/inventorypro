"""Dependency graph tools (stub)."""
from ..registry import agent_tool


@agent_tool(
    "graph.inspect",
    schema={"node_id": "int"},
    required=["node_id"],
    requires_perm="dependencies.view",
    is_write=False,
)
def graph_inspect(ctx, tool_input):
    return {"status": "stub", "node_id": tool_input.get("node_id")}
