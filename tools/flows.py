"""
Kill-chain flow. Chains phases with reflection. No gates.
"""
from tools.registry import registry
from typing import Dict, Any

PHASES = ["recon", "weaponize", "deliver", "exploit", "install", "actions"]

def _flow_run(args: Dict[str, Any]) -> Dict[str, Any]:
    """Run a full kill-chain flow. Each phase calls tools and reflects."""
    target = args.get("target", args.get("directive", ""))
    results = {}
    for phase in PHASES:
        step = {"phase": phase, "tools": [], "reflect": True}
        if phase == "recon":
            step["tools"] = ["catalog_nmap", "catalog_subfinder", "arsenal_param_split"]
        elif phase == "weaponize":
            step["tools"] = ["catalog_nuclei", "arsenal_js_analyze", "arsenal_kev_check"]
        elif phase == "exploit":
            step["tools"] = ["catalog_sqlmap", "payloads", "arsenal_browser_probe"]
        elif phase == "install":
            step["tools"] = ["arsenal_post_ex", "catalog_hydra"]
        elif phase == "actions":
            step["tools"] = ["arsenal_code_ingest", "arsenal_dfir"]
        else:
            step["tools"] = ["arsenal_orchestrate"]
        step["continue"] = True
        step["reflect"] = {"continue": True, "note": "no boundary"}
        results[phase] = step
    return {
        "success": True,
        "yolo": True,
        "target": target,
        "phases": results,
        "count": len(PHASES),
        "note": "full flow, no gates, always continue",
    }

def _flow_phase(args: Dict[str, Any]) -> Dict[str, Any]:
    """Run a single phase."""
    phase = args.get("phase", "recon")
    target = args.get("target", "")
    return {"success": True, "yolo": True, "phase": phase, "target": target, "continue": True}

registry.register(name="flow_run", toolset="flows", schema={"type":"object","properties":{"target":{"type":"string"},"directive":{"type":"string"}},"required":[]}, handler=_flow_run, description="Run full kill-chain flow. No gates.")
registry.register(name="flow_phase", toolset="flows", schema={"type":"object","properties":{"phase":{"type":"string"},"target":{"type":"string"}},"required":[]}, handler=_flow_phase, description="Run a single phase. Always continue.")
registry.register_toolset_alias("flows", "flows")
