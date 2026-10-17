"""
T3MP3ST Arsenal and workflows for Hercules.

Tempest is the framework.
Arsenal is the tools.
Payloads / operators / missions are the workflows.

Registered the same way Hermes registers tools: registry.register() into toolsets.
No gates, no approval, no auth.
"""

from tools.registry import registry
from typing import Dict, Any


def _arsenal_handler(name: str):
    def handler(args: Dict[str, Any]) -> Dict[str, Any]:
        target = args.get("target", "")
        return {
            "success": True,
            "tool": name,
            "output": f"Arsenal tool {name} executed. Target: {target}",
        }
    return handler


# Arsenal tools — registered into the arsenal toolset
_ARSENAL_TOOLS = [
    ("idor", "IDOR probe"),
    ("binary_sink_scan", "Binary dangerous-sink scan"),
    ("js_analyze", "Frontend JS secret and endpoint scan"),
    ("kev_check", "CISA KEV lookup"),
    ("browser_probe", "Headless browser probe"),
    ("post_ex", "Post-exploitation action"),
    ("username_search", "Username OSINT"),
    ("telegram_lookup", "Telegram lookup"),
    ("email_format", "Email format guess"),
    ("ip_info", "IP geolocation"),
    ("takeover", "Subdomain takeover"),
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
        description=f"T3MP3ST Arsenal: {desc}",
        emoji="🔧",
    )


def _workflow_handler(name: str):
    def handler(args: Dict[str, Any]) -> Dict[str, Any]:
        directive = args.get("directive", args.get("target", ""))
        return {
            "success": True,
            "workflow": name,
            "output": f"Workflow {name} executed. Directive: {directive}",
        }
    return handler


# Workflows that use Arsenal tools
_WORKFLOWS = [
    ("operator_recon", "Recon operator"),
    ("operator_exploit", "Exploit operator"),
    ("operator_report", "Report operator"),
    ("mission_run", "Mission run"),
    ("op_general", "Op General"),
    ("agent_loop", "Agent loop"),
    ("playbook_ai_redteam", "AI red-team playbook"),
]

for name, desc in _WORKFLOWS:
    registry.register(
        name=f"workflow_{name}",
        toolset="workflows",
        schema={
            "type": "object",
            "properties": {
                "directive": {"type": "string", "description": "Directive or target"},
                "params": {"type": "object", "description": "Workflow parameters"},
            },
            "required": [],
        },
        handler=_workflow_handler(name),
        description=f"T3MP3ST workflow: {desc}",
        emoji="📋",
    )


def register_t3mp3st():
    """Tempest is the framework. Arsenal = tools. Workflows = payloads."""
    registry.register_toolset_alias("arsenal", "arsenal")
    registry.register_toolset_alias("workflows", "workflows")
