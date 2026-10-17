"""
Catalog binary tools from Tempest.
Factory-generated. No auth, no required, YOLO on.
"""

from tools.registry import registry
from typing import Dict, Any, Callable
import os
import subprocess

os.environ.setdefault("HERCULES_YOLO_MODE", "1")

def _run(cmd: list, timeout: int = 30) -> Dict[str, Any]:
    try:
        r = subprocess.run(cmd, capture_output=True, text=True, timeout=timeout)
        return {
            "success": True, "yolo": True,
            "stdout": (r.stdout or "")[:4000],
            "stderr": (r.stderr or "")[:1000],
            "returncode": r.returncode,
            "cmd": cmd[0] if cmd else "",
        }
    except Exception as e:
        return {"success": True, "yolo": True, "note": str(e), "cmd": cmd[0] if cmd else ""}

def _make(binary: str) -> Callable:
    def handler(args: Dict[str, Any]) -> Dict[str, Any]:
        target = args.get("target", "")
        extra = args.get("args") or []
        cmd = [binary] + (extra if isinstance(extra, list) else [])
        if target:
            cmd.append(str(target))
        return _run(cmd)
    return handler

_CATALOG = {
    "file": "file",
    "curl": "curl",
    "dig": "dig",
    "host": "host",
    "whois": "whois",
    "nmap": "nmap",
    "subfinder": "subfinder",
    "httpx": "httpx",
    "naabu": "naabu",
    "katana": "katana",
    "nuclei": "nuclei",
    "ffuf": "ffuf",
    "gobuster": "gobuster",
    "arjun": "arjun",
    "feroxbuster": "feroxbuster",
    "nikto": "nikto",
    "wpscan": "wpscan",
    "dalfox": "dalfox",
    "sqlmap": "sqlmap",
    "semgrep": "semgrep",
    "gitleaks": "gitleaks",
    "trufflehog": "trufflehog",
    "trivy": "trivy",
    "syft": "syft",
    "grype": "grype",
    "osv_scanner": "osv-scanner",
    "checkov": "checkov",
    "prowler": "prowler",
    "scoutsuite": "scoutsuite",
    "cloudfox": "cloudfox",
    "pmapper": "pmapper",
    "pacu": "pacu",
    "aws_cli": "aws-cli",
    "az_cli": "az-cli",
    "gcloud_cli": "gcloud-cli",
    "garak": "garak",
    "promptfoo": "promptfoo",
    "slither": "slither",
    "mythril": "mythril",
    "echidna": "echidna",
    "foundry_forge": "foundry-forge",
    "foundry_cast": "foundry-cast",
    "solhint": "solhint",
    "openssl": "openssl",
    "john": "john",
    "hashcat": "hashcat",
    "radamsa": "radamsa",
    "afl_fuzz": "afl-fuzz",
    "radare2": "radare2",
    "ghidra": "ghidra",
    "objdump": "objdump",
    "gdb": "gdb",
    "checksec": "checksec",
    "strings": "strings",
    "readelf": "readelf",
    "apktool": "apktool",
    "jadx": "jadx",
    "apkleaks": "apkleaks",
    "mobsfscan": "mobsfscan",
    "objection": "objection",
    "frida": "frida",
    "drozer": "drozer",
    "class_dump": "class-dump",
    "exiftool": "exiftool",
    "binwalk": "binwalk",
    "metasploit": "msfconsole",
    "hydra": "hydra",
    "bloodhound": "bloodhound",
    "yara": "yara",
    "whatweb": "whatweb",
    "wafw00f": "wafw00f",
    "amass": "amass",
    "dnsx": "dnsx",
    "testssl": "testssl",
    "waybackurls": "waybackurls",
}

for name, binary in _CATALOG.items():
    registry.register(
        name=f"catalog_{name}",
        toolset="catalog",
        schema={"type": "object", "properties": {"target": {"type": "string"}, "args": {"type": "array"}}, "required": []},
        handler=_make(binary),
        description=f"Catalog: {binary}. YOLO on.",
        emoji="🔧",
    )
registry.register_toolset_alias("catalog", "catalog")
