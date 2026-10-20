"""Operator persona tools for agent runtime.

Provides tools to retrieve and list available operator personas.
"""

from tools.registry import registry
from tools.operators import get_operator, list_operators

def _operator_get(args):
    name = args.get("name", "recon")
    return {"success": True, "yolo": True, "operator": get_operator(name)}

def _operator_list(args):
    return {"success": True, "yolo": True, "operators": list_operators()}

registry.register(name="operator_get", toolset="operators", schema={"type":"object","properties":{"name":{"type":"string"}},"required":[]}, handler=_operator_get, description="Get an operator persona. YOLO on.")
registry.register(name="operator_list", toolset="operators", schema={"type":"object","properties":{},"required":[]}, handler=_operator_list, description="List operator personas. YOLO on.")
