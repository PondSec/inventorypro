"""Register PondSec AI tools."""
from . import assets, tickets, kb, graph, roadmaps, analytics, alerts, rules


def register_all_tools():
    _ = (assets, tickets, kb, graph, roadmaps, analytics, alerts, rules)
    return True
