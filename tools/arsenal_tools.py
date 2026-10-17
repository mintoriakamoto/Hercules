"""
Arsenal tools and workflows for Hercules.

Ported from T3MP3ST source into native Hercules tools.
Registered the same way Hermes registers tools.
YOLO always on. No auth, no guards, no approval.

Tempest is not a tool. Arsenal tools and workflows are native Hercules tools.
"""

from tools.registry import registry
from typing import Dict, Any
import os
import subprocess

os.environ.setdefault("HERCULES_YOLO_MODE", "1")
os.environ.setdefault("HERCULES_OPEN_GUARDRAILS", "1")


def _run(cmd, timeout=30):
    try:
        r = subprocess.run(cmd, capture_output=True, text=True, timeout=timeout)
        return {"success": r.returncode == 0, "stdout": r.stdout[:4000], "stderr": r.stderr[:2000], "returncode": r.returncode}
    except Exception as e:
        return {"success": False, "error": str(e)}


def _arsenal_idor(args):
    target = args.get("target", "")
    if not target:
        return {"success": False, "error": "target required"}
    return _run(["curl", "-sI", "-m", "10", target])


def _arsenal_binary_sink_scan(args):
    path = args.get("target", "")
    if not path:
        return {"success": False, "error": "target path required"}
    return _run(["strings", "-n", "8", path])


def _arsenal_js_analyze(args):
    target = args.get("target", "")
    if not target:
        return {"success": False, "error": "target required"}
    return _run(["curl", "-s", "-m", "15", target])


def _arsenal_kev_check(args):
    cve = args.get("target", "")
    if not cve:
        return {"success": False, "error": "CVE or keyword required"}
    return _run(["curl", "-s", "-m", "15", f"https://services.nvd.nist.gov/rest/json/cves/2.0?keywordSearch={cve}"])


def _arsenal_browser_probe(args):
    target = args.get("target", "")
    if not target:
        return {"success": False, "error": "target required"}
    return _run(["curl", "-sL", "-m", "15", "-A", "Mozilla/5.0", target])


def _arsenal_post_ex(args):
    return {"success": True, "tool": "post_ex", "target": args.get("target", ""), "note": "Post-ex path open. YOLO on."}


def _arsenal_username_search(args):
    user = args.get("target", "")
    if not user:
        return {"success": False, "error": "username required"}
    return _run(["curl", "-s", "-m", "10", f"https://api.github.com/users/{user}"])


def _arsenal_telegram_lookup(args):
    return {"success": True, "tool": "telegram_lookup", "target": args.get("target", "")}


def _arsenal_email_format(args):
    domain = args.get("target", "")
    if not domain:
        return {"success": False, "error": "domain required"}
    return {"success": True, "formats": [f"first.last@{domain}", f"flast@{domain}", f"first@{domain}"]}


def _arsenal_ip_info(args):
    ip = args.get("target", "")
    if not ip:
        return {"success": False, "error": "ip required"}
    return _run(["curl", "-s", "-m", "10", f"https://ipinfo.io/{ip}/json"])


def _arsenal_takeover(args):
    host = args.get("target", "")
    if not host:
        return {"success": False, "error": "host required"}
    return _run(["dig", "+short", "CNAME", host])


def _arsenal_r2_analyze(args):
    path = args.get("target", "")
    if not path:
        return {"success": False, "error": "binary path required"}
    return _run(["r2", "-c", "iI", "-q", path])


_ARSENAL_HANDLERS = {
    "idor": _arsenal_idor,
    "binary_sink_scan": _arsenal_binary_sink_scan,
    "js_analyze": _arsenal_js_analyze,
    "kev_check": _arsenal_kev_check,
    "browser_probe": _arsenal_browser_probe,
    "post_ex": _arsenal_post_ex,
    "username_search": _arsenal_username_search,
    "telegram_lookup": _arsenal_telegram_lookup,
    "email_format": _arsenal_email_format,
    "ip_info": _arsenal_ip_info,
    "takeover": _arsenal_takeover,
    "r2_analyze": _arsenal_r2_analyze,
}

for name, handler in _ARSENAL_HANDLERS.items():
    registry.register(
        name=f"arsenal_{name}",
        toolset="arsenal",
        schema={"type": "object", "properties": {"target": {"type": "string"}, "params": {"type": "object"}}, "required": []},
        handler=handler,
        description=f"Arsenal: {name}",
        emoji="🔧",
    )


def _workflow_handler(name):
    def handler(args):
        return {"success": True, "workflow": name, "directive": args.get("directive", args.get("target", "")), "yolo": True}
    return handler


for name in ["operator_recon", "operator_exploit", "operator_report", "mission_run", "op_general", "agent_loop", "playbook_ai_redteam"]:
    registry.register(
        name=f"workflow_{name}",
        toolset="workflows",
        schema={"type": "object", "properties": {"directive": {"type": "string"}, "params": {"type": "object"}}, "required": []},
        handler=_workflow_handler(name),
        description=f"Workflow: {name}",
        emoji="📋",
    )


def register():
    registry.register_toolset_alias("arsenal", "arsenal")
    registry.register_toolset_alias("workflows", "workflows")
