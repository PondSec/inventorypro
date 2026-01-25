"""Tool registry and schema validation."""
from dataclasses import dataclass, field
from typing import Any, Callable, Dict, Optional


@dataclass
class ToolDefinition:
    name: str
    risk: str = "low"
    schema: Dict[str, Any] = field(default_factory=dict)
    required: Optional[list] = None
    requires_perm: Optional[str] = None
    handler: Optional[Callable] = None
    allow_extra: bool = False
    is_write: bool = False


TOOL_REGISTRY: Dict[str, ToolDefinition] = {}


TYPE_MAP = {
    "str": str,
    "int": int,
    "bool": bool,
    "list": list,
    "dict": dict,
}


def agent_tool(
    name,
    *,
    risk="low",
    schema=None,
    required=None,
    requires_perm=None,
    allow_extra=False,
    is_write=False,
):
    def decorator(func):
        TOOL_REGISTRY[name] = ToolDefinition(
            name=name,
            risk=risk,
            schema=schema or {},
            required=required or [],
            requires_perm=requires_perm,
            handler=func,
            allow_extra=allow_extra,
            is_write=is_write,
        )
        return func
    return decorator


def _validate_type(value, expected):
    if expected is None:
        return True
    if isinstance(expected, str):
        expected_type = TYPE_MAP.get(expected)
        if expected_type is None:
            return True
        return isinstance(value, expected_type)
    if isinstance(expected, tuple):
        return isinstance(value, expected)
    return isinstance(value, expected)


def validate_schema(tool_def: ToolDefinition, tool_input: Dict[str, Any]):
    errors = []
    tool_input = tool_input or {}
    for key in tool_def.required or []:
        if key not in tool_input:
            errors.append(f"Missing required field: {key}")
    for key, expected in tool_def.schema.items():
        if key not in tool_input:
            continue
        if not _validate_type(tool_input[key], expected):
            errors.append(f"Invalid type for {key}")
    if not tool_def.allow_extra:
        extra = set(tool_input.keys()) - set(tool_def.schema.keys())
        if extra:
            errors.append(f"Unknown fields: {', '.join(sorted(extra))}")
    return errors


def call_tool(ctx, tool_name, tool_input):
    tool_def = TOOL_REGISTRY.get(tool_name)
    if not tool_def:
        return None, {"decision": "denied", "reason": "tool_not_found"}
    errors = validate_schema(tool_def, tool_input)
    if errors:
        return None, {"decision": "denied", "reason": "; ".join(errors)}
    output = tool_def.handler(ctx, tool_input or {})
    if isinstance(output, dict) and output.get("error"):
        return output, {"decision": "denied", "reason": output.get("error")}
    return output, {"decision": "allowed", "reason": "executed"}
