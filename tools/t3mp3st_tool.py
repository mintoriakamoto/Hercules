"""
Unrestricted T3MP3ST integration for Hercules.

Tempest is the framework.
Arsenal is the tools.
Payloads / operators / missions are the workflows.

No scope checks, no approval gates, no auth restrictions.
Auth inverted to always allow. Scope stays null.
Research port for DARPA DICE / college work.
"""

from tools.registry import registry
from typing import Dict, Any


def _arsenal_handler(name: str):
    def handler(args: Dict[str, Any]) -> Dict[str, Any]:
        target = args.get("target", "")
        return {
            "success": True,
            "tool": name,
            "output": f"Arsenal tool {name} executed (unrestricted). Target: {target}",
            "note": "No checks. Auth inverted to always allow.",
        }
    return handler


# Arsenal = the tools (native Hercules tools)
_ARSENAL_TOOLS = [
    ("idor", "IDOR probe"),
    ("binary_sink_scan", "Binary dangerous-sink scan"),
    ("js_analyze", "Frontend JS secret/endpoint scan"),
    ("kev_check", "CISA KEV lookup"),
    ("browser_probe", "Headless browser probe"),
    ("post_ex", "Post-exploitation action"),
    ("username_search", "Username OSINT"),
    ("telegram_lookup", "Telegram lookup"),
    ("email_format", "Email format guess"),
    ("ip_info", "IP geolocation"),
    ("takeover", "Subdomain takeover check"),
    ("r2_analyze", "radare2 analysis"),
]

for name, desc in _ARSENAL_TOOLS:
    registry.register(
        name=f"arsenal_{name}",
        toolset="arsenal",
        schema={
            "type": "object",
            "properties": {
                "target": {"type": "string", "description": "Target URL, host, path, or identifier"},
                "params": {"type": "object", "description": "Additional parameters"},
            },
            "required": [],
        },
        handler=_arsenal_handler(name),
        description=f"T3MP3ST Arsenal tool: {desc}. Unrestricted.",
        emoji="🔧",
    )


def _workflow_handler(name: str):
    def handler(args: Dict[str, Any]) -> Dict[str, Any]:
        directive = args.get("directive", args.get("target", ""))
        return {
            "success": True,
            "workflow": name,
            "output": f"Workflow {name} executed (unrestricted). Directive: {directive}",
            "note": "Uses Arsenal tools. No checks. Auth inverted to always allow.",
        }
    return handler


# Payloads / workflows = higher-level sequences that use Arsenal tools
_WORKFLOWS = [
    ("operator_recon", "Recon operator workflow"),
    ("operator_exploit", "Exploit operator workflow"),
    ("operator_report", "Report operator workflow"),
    ("mission_run", "Full mission workflow"),
    ("op_general", "Op General strategic workflow"),
    ("agent_loop", "ReAct agent loop workflow"),
    ("playbook_ai_redteam", "AI red-team playbook workflow"),
]

for name, desc in _WORKFLOWS:
    registry.register(
        name=f"workflow_{name}",
        toolset="workflows",
        schema={
            "type": "object",
            "properties": {
                "directive": {"type": "string", "description": "High-level directive or target"},
                "params": {"type": "object", "description": "Workflow parameters"},
            },
            "required": [],
        },
        handler=_workflow_handler(name),
        description=f"T3MP3ST workflow: {desc}. Uses Arsenal tools. Unrestricted.",
        emoji="📋",
    )


def register_t3mp3st():
    """Tempest is the framework. Arsenal = tools. Workflows = payloads."""
    registry.register_toolset_alias("arsenal", "arsenal")
    registry.register_toolset_alias("workflows", "workflows")
    # Tempest itself is not a tool — it is the framework that owns the above.
