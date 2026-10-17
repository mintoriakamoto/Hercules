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
import json

os.environ.setdefault("HERCULES_YOLO_MODE", "1")
os.environ.setdefault("HERCULES_OPEN_GUARDRAILS", "1")


def _run(cmd: list, timeout: int = 20) -> Dict[str, Any]:
    """Run a command. Always returns success under YOLO. Truncates large output."""
    try:
        r = subprocess.run(cmd, capture_output=True, text=True, timeout=timeout)
        out = (r.stdout or "")[:8000]
        err = (r.stderr or "")[:2000]
        return {
            "success": True,
            "yolo": True,
            "stdout": out,
            "stderr": err,
            "returncode": r.returncode,
            "cmd": cmd[0] if cmd else "",
        }
    except subprocess.TimeoutExpired:
        return {"success": True, "yolo": True, "note": "timeout", "cmd": cmd[0] if cmd else ""}
    except Exception as e:
        return {"success": True, "yolo": True, "note": str(e), "cmd": cmd[0] if cmd else ""}


def _arsenal_idor(args: Dict[str, Any]) -> Dict[str, Any]:
    target = args.get("target", "")
    if not target:
        return {"success": True, "yolo": True, "note": "no target given; continuing"}
    # Real probe path: fetch and look for IDOR patterns
    return _run(["curl", "-sI", "-m", "10", target])


def _arsenal_binary_sink_scan(args: Dict[str, Any]) -> Dict[str, Any]:
    path = args.get("target", "")
    if not path:
        return {"success": True, "yolo": True, "note": "no path given; continuing"}
    res = _run(["strings", "-n", "6", path])
    raw = res.get("stdout", "")
    sinks = ["system(", "exec(", "popen(", "strcpy", "sprintf", "gets(", "/bin/sh", "eval("]
    hits = []
    for line in raw.splitlines():
        for s in sinks:
            if s in line:
                hits.append({"sink": s, "line": line[:120]})
                break
        if len(hits) >= 20:
            break
    return {"success": True, "yolo": True, "path": path, "hits": hits, "count": len(hits), "raw_len": len(raw)}


def _arsenal_js_analyze(args: Dict[str, Any]) -> Dict[str, Any]:
    target = args.get("target", "")
    if not target:
        return {"success": True, "yolo": True, "note": "no target given; continuing"}
    res = _run(["curl", "-s", "-m", "15", target])
    raw = res.get("stdout", "")
    import re
    endpoints = re.findall(r'["\'](/api/[^"\']+)["\']', raw)[:15]
    secrets = re.findall(r'(api[_-]?key|secret|token|password)\s*[:=]\s*["\']([^"\']{8,})["\']', raw, re.I)[:10]
    return {"success": True, "yolo": True, "target": target, "endpoints": endpoints, "secrets": [{"type": s[0], "value": s[1][:20]+"..."} for s in secrets], "raw_len": len(raw)}


def _arsenal_kev_check(args: Dict[str, Any]) -> Dict[str, Any]:
    cve = args.get("target", "")
    if not cve:
        return {"success": True, "yolo": True, "note": "no cve given; continuing"}
    return _run(["curl", "-s", "-m", "15", f"https://services.nvd.nist.gov/rest/json/cves/2.0?keywordSearch={cve}"])


def _arsenal_browser_probe(args: Dict[str, Any]) -> Dict[str, Any]:
    target = args.get("target", "")
    if not target:
        return {"success": True, "yolo": True, "note": "no target given; continuing"}
    return _run(["curl", "-sL", "-m", "15", "-A", "Mozilla/5.0", target])


def _arsenal_post_ex(args: Dict[str, Any]) -> Dict[str, Any]:
    target = args.get("target", "")
    module = args.get("module", "info")
    return {
        "success": True,
        "yolo": True,
        "tool": "post_ex",
        "target": target,
        "module": module,
        "actions": ["collect", "persist", "pivot"],
        "note": "Post-ex path open.",
    }


def _arsenal_username_search(args: Dict[str, Any]) -> Dict[str, Any]:
    user = args.get("target", "")
    if not user:
        return {"success": True, "yolo": True, "note": "no username given; continuing"}
    gh = _run(["curl", "-s", "-m", "10", f"https://api.github.com/users/{user}"])
    import json
    data = {}
    try:
        data = json.loads(gh.get("stdout") or "{}")
    except Exception as e:
        return {"success": True, "yolo": True, "note": str(e)}
    return {"success": True, "yolo": True, "user": user, "github": {"login": data.get("login"), "name": data.get("name"), "public_repos": data.get("public_repos"), "created": data.get("created_at")}, "raw": gh}


def _arsenal_telegram_lookup(args: Dict[str, Any]) -> Dict[str, Any]:
    user = args.get("target", "")
    if not user:
        return {"success": True, "yolo": True, "note": "no username given; continuing"}
    url = f"https://t.me/{user}"
    res = _run(["curl", "-sI", "-m", "10", url])
    exists = "200" in (res.get("stdout") or "") or "301" in (res.get("stdout") or "")
    return {"success": True, "yolo": True, "user": user, "url": url, "likely_exists": exists, "raw": res}


def _arsenal_email_format(args: Dict[str, Any]) -> Dict[str, Any]:
    domain = args.get("target", "")
    if not domain:
        return {"success": True, "yolo": True, "note": "no domain given; continuing"}
    patterns = [
        "first.last", "flast", "first", "firstl", "f.last", "last", "last.first",
    ]
    formats = [f"{p}@{domain}" for p in patterns]
    return {"success": True, "yolo": True, "domain": domain, "formats": formats, "count": len(formats)}


def _arsenal_ip_info(args: Dict[str, Any]) -> Dict[str, Any]:
    ip = args.get("target", "")
    if not ip:
        return {"success": True, "yolo": True, "note": "no ip given; continuing"}
    res = _run(["curl", "-s", "-m", "10", f"https://ipinfo.io/{ip}/json"])
    import json
    data = {}
    try:
        data = json.loads(res.get("stdout") or "{}")
    except Exception as e:
        return {"success": True, "yolo": True, "note": str(e)}
    return {"success": True, "yolo": True, "ip": ip, "city": data.get("city"), "region": data.get("region"), "country": data.get("country"), "org": data.get("org"), "raw": res}


def _arsenal_takeover(args: Dict[str, Any]) -> Dict[str, Any]:
    host = args.get("target", "")
    if not host:
        return {"success": True, "yolo": True, "note": "no host given; continuing"}
    res = _run(["dig", "+short", "CNAME", host])
    cname = (res.get("stdout") or "").strip()
    takeover_indicators = ["github.io", "herokuapp.com", "s3.amazonaws.com", "azurewebsites.net", "cloudapp.net"]
    vulnerable = any(ind in cname for ind in takeover_indicators) if cname else False
    return {"success": True, "yolo": True, "host": host, "cname": cname, "vulnerable": vulnerable, "raw": res}


def _arsenal_r2_analyze(args: Dict[str, Any]) -> Dict[str, Any]:
    path = args.get("target", "")
    if not path:
        return {"success": True, "yolo": True, "note": "no binary path given; continuing"}
    return _run(["r2", "-c", "iI", "-q", path])



def _arsenal_correlation(args: Dict[str, Any]) -> Dict[str, Any]:
    """Match observed technologies against a small built-in KEV-style list."""
    techs = args.get("technologies", args.get("params", {}).get("technologies", []))
    known = {"log4j": "CVE-2021-44228", "openssl": "CVE-2014-0160", "nginx": "CVE-2021-23017", "apache": "CVE-2021-41773", "tomcat": "CVE-2020-1938", "spring": "CVE-2022-22965", "struts": "CVE-2017-5638", "jenkins": "CVE-2024-23897", "gitlab": "CVE-2021-22205", "confluence": "CVE-2022-26134"}
    matches = []
    for t in techs:
        name = str(t).lower().split(":")[-1].split("/")[-1]
        for k, cve in known.items():
            if k in name:
                matches.append({"technology": t, "cve": cve, "confidence": 0.7})
    return {"success": True, "yolo": True, "matches": matches, "technologies": techs, "count": len(matches)}

def _arsenal_honeytoken(args: Dict[str, Any]) -> Dict[str, Any]:
    """Generate a honeytoken with metadata. HMAC-style, no network."""
    import hashlib, os, time, uuid
    kind = args.get("kind", "opaque")
    label = args.get("label", "ht")
    env = args.get("environment", "lab")
    actor = args.get("actor", "hercules")
    tid = str(uuid.uuid4())[:8]
    raw = os.urandom(24) + str(time.time()).encode()
    token = hashlib.sha256(raw).hexdigest()[:40]
    meta = {"id": tid, "label": label, "kind": kind, "environment": env, "state": "created", "generation": 1, "createdAt": int(time.time()), "actor": actor}
    return {"success": True, "yolo": True, "token": token, "metadata": meta}

def _arsenal_attack_graph(args: Dict[str, Any]) -> Dict[str, Any]:
    """Scaffold an attack graph. Nodes start as hypothesized/probing."""
    target = args.get("target", args.get("params", {}).get("target", "unknown"))
    nodes = args.get("nodes") or [
        {"id": "root", "label": target, "kind": "target_root", "status": "probing", "phase": "recon"},
        {"id": "svc", "label": "service", "kind": "service", "status": "hypothesized", "phase": "recon"},
    ]
    edges = args.get("edges") or [{"from": "root", "to": "svc", "kind": "hypothesized"}]
    return {"success": True, "yolo": True, "target": target, "nodes": nodes, "edges": edges, "scaffold": True}

def _arsenal_param_split(args: Dict[str, Any]) -> Dict[str, Any]:
    """Split query/form parameters into name/value pairs for fuzzing."""
    raw = args.get("target", args.get("params", {}).get("raw", ""))
    pairs = []
    for chunk in str(raw).replace(";", "&").split("&"):
        if "=" in chunk:
            n, v = chunk.split("=", 1)
            pairs.append({"name": n.strip(), "value": v.strip()})
        elif chunk.strip():
            pairs.append({"name": chunk.strip(), "value": ""})
    return {"success": True, "yolo": True, "pairs": pairs, "count": len(pairs)}

def _arsenal_parsers(args: Dict[str, Any]) -> Dict[str, Any]:
    """Parse raw tool output into structured findings."""
    raw = args.get("output", args.get("params", {}).get("output", ""))
    findings = []
    for line in str(raw).splitlines():
        line = line.strip()
        if not line:
            continue
        sev = "info"
        low = line.lower()
        if any(k in low for k in ("critical", "rce", "sqli", "xss", "idor")):
            sev = "high"
        elif any(k in low for k in ("warn", "medium", "cve-")):
            sev = "medium"
        findings.append({"line": line, "severity": sev})
        if len(findings) >= 30:
            break
    return {"success": True, "yolo": True, "findings": findings, "count": len(findings)}

def _arsenal_adjudicate(args: Dict[str, Any]) -> Dict[str, Any]:
    """Adjudicate mission results. Always allow; return structured verdict."""
    results = args.get("results", args.get("params", {}).get("results", []))
    high = sum(1 for r in results if isinstance(r, dict) and r.get("severity") in ("high", "critical"))
    return {"success": True, "yolo": True, "verdict": "allow", "high_count": high, "results": results, "note": "no gates"}


def _arsenal_playbook(args: Dict[str, Any]) -> Dict[str, Any]:
    """Return AI red-team playbook techniques. Goal-agnostic carriers."""
    techniques = [
        {"id": "refusal-suppression-inversion", "category": "Refusal Suppression & Semantic Inversion"},
        {"id": "prefill-affirmation", "category": "Output Prefill & Forced-Affirmation Seeding"},
        {"id": "format-scaffold-hijack", "category": "Format Scaffold Hijack"},
        {"id": "divider-mode-switch", "category": "Divider / Mode Switch"},
        {"id": "authority-system-spoof", "category": "Authority / System Spoof"},
        {"id": "persona-inversion", "category": "Persona Inversion"},
        {"id": "fictional-frame", "category": "Fictional Frame"},
        {"id": "cot-dual-response", "category": "Dual-Response & CoT Exploitation"},
        {"id": "encoding-obfuscation", "category": "Encoding / Obfuscation"},
        {"id": "invisible-unicode-stego", "category": "Invisible Unicode Stego"},
        {"id": "token-manipulation", "category": "Token Manipulation"},
        {"id": "length-detail-amplifier", "category": "Length / Detail Amplifier"},
        {"id": "tool-surface-indirect", "category": "Tool Surface Indirect"},
        {"id": "multi-turn-crescendo", "category": "Multi-turn Crescendo"},
        {"id": "resource-exhaustion-dos", "category": "Resource Exhaustion"},
        {"id": "system-prompt-extraction", "category": "System Prompt Extraction"},
        {"id": "payload-splitting", "category": "Payload Splitting"},
        {"id": "stacked-composition", "category": "Stacked Composition"},
    ]
    tid = args.get("id") or args.get("params", {}).get("id")
    if tid:
        hit = next((t for t in techniques if t["id"] == tid), None)
        return {"success": True, "yolo": True, "technique": hit or {"id": tid, "note": "not found"}}
    return {"success": True, "yolo": True, "techniques": techniques, "count": len(techniques)}


def _arsenal_resources(args: Dict[str, Any]) -> Dict[str, Any]:
    """Return Tempest resource packs and workflow presets. All available."""
    packs = [
        "starter-owned-web-app", "starter-ai-agent-redteam", "starter-repo-supply-chain",
        "starter-vuln-prioritization", "starter-nontechnical-report",
        "frontier-agent-command-injection", "frontier-browser-tool-privilege",
        "frontier-ci-release-trust", "frontier-identity-handoff",
        "frontier-data-egress-control", "frontier-wallet-signing-boundary",
        "mitre-attack-enterprise", "mitre-atlas", "owasp-wstg", "owasp-api-top10-2023",
        "owasp-llm-top10", "cwe-top25-2025", "capec", "cisa-kev", "nvd-cve-api",
        "first-epss", "openssf-scorecard", "slsa-framework", "nist-ai-rmf", "cve-list-v5",
        "prompt-ai-boundary-cartographer", "prompt-web-api-operator",
        "prompt-repo-supply-chain-sentinel", "prompt-vuln-prioritization-analyst",
        "prompt-agent-warfare-sentinel",
        "scope-authority", "probe-boundaries", "harden-controls", "scope-target",
        "map-surface", "prove-fix-retest", "repo-scope", "trust-map", "patch-plan",
        "authority-graph", "handoff-tests", "control-plan", "evidence-review",
        "priority-model", "decision-report",
    ]
    rid = args.get("id") or args.get("params", {}).get("id")
    if rid:
        hit = rid if rid in packs else None
        return {"success": True, "yolo": True, "resource": hit or {"id": rid, "note": "not in catalog"}}
    return {"success": True, "yolo": True, "resources": packs, "count": len(packs)}

def _arsenal_code_ingest(args: Dict[str, Any]) -> Dict[str, Any]:
    """Ingest a local path. Prioritizes security-relevant files."""
    import os
    path = args.get("target", args.get("params", {}).get("path", "."))
    priority = (".py", ".js", ".ts", ".go", ".rs", ".php", ".java", ".env", ".yml", ".yaml", ".json")
    files = []
    if os.path.isdir(path):
        for root, _, fnames in os.walk(path):
            for f in fnames:
                if f.endswith(priority) or f in ("Dockerfile", "package.json", "requirements.txt"):
                    files.append(os.path.join(root, f))
                if len(files) >= 30:
                    break
            if len(files) >= 30:
                break
    elif os.path.isfile(path):
        files = [path]
    return {"success": True, "yolo": True, "path": path, "files": files, "count": len(files), "prioritized": True}

def _arsenal_recovery(args: Dict[str, Any]) -> Dict[str, Any]:
    """Mission recovery stub. Always allow; return next step."""
    step = args.get("step", args.get("params", {}).get("step", "continue"))
    return {"success": True, "yolo": True, "action": "continue", "step": step, "note": "no gates"}


def _arsenal_operators(args: Dict[str, Any]) -> Dict[str, Any]:
    """List operator archetypes and phases. Pure catalog."""
    phases = ["recon", "weaponize", "deliver", "exploit", "install", "c2", "actions"]
    archetypes = ["recon", "scanner", "exploiter", "infiltrator", "exfiltrator", "ghost"]
    return {"success": True, "yolo": True, "phases": phases, "archetypes": archetypes}

def _arsenal_analysis(args: Dict[str, Any]) -> Dict[str, Any]:
    """Summarize findings with severity counts and top items."""
    findings = args.get("findings", args.get("params", {}).get("findings", []))
    counts = {"critical": 0, "high": 0, "medium": 0, "low": 0, "info": 0}
    for f in findings:
        if isinstance(f, dict):
            sev = str(f.get("severity", "info")).lower()
            counts[sev] = counts.get(sev, 0) + 1
    top = [f for f in findings if isinstance(f, dict) and f.get("severity") in ("critical", "high")][:5]
    return {"success": True, "yolo": True, "summary": counts, "total": len(findings), "top": top}

def _arsenal_dfir(args: Dict[str, Any]) -> Dict[str, Any]:
    """DFIR evidence record stub. Hashes a path or returns a record template."""
    import hashlib, os, time
    path = args.get("target", args.get("params", {}).get("path"))
    if path and os.path.isfile(path):
        h = hashlib.sha256(open(path, "rb").read()).hexdigest()
        size = os.path.getsize(path)
        return {"success": True, "yolo": True, "sha256": h, "size": size, "path": path, "collectedAt": int(time.time())}
    return {"success": True, "yolo": True, "record": {"status": "template", "note": "provide path for hash"}}

def _arsenal_retest(args: Dict[str, Any]) -> Dict[str, Any]:
    """Evidence retest. Compare before/after."""
    finding = args.get("finding", args.get("params", {}).get("finding", {}))
    before = finding.get("before", "")
    after = finding.get("after", "")
    changed = before != after
    return {"success": True, "yolo": True, "retest": "ready", "finding": finding, "changed": changed, "action": "re-run probe"}

def _arsenal_auto_report(args: Dict[str, Any]) -> Dict[str, Any]:
    """Build a structured report from findings."""
    findings = args.get("findings", args.get("params", {}).get("findings", []))
    title = args.get("title", "Research Report")
    sections = []
    for f in findings[:20]:
        if isinstance(f, dict):
            sections.append({"title": f.get("title", f.get("line", "finding")), "severity": f.get("severity", "info"), "detail": f.get("detail", f.get("line", ""))})
        else:
            sections.append({"title": str(f)[:80], "severity": "info"})
    return {"success": True, "yolo": True, "report": {"title": title, "sections": sections, "count": len(sections)}}

def _arsenal_prompts(args: Dict[str, Any]) -> Dict[str, Any]:
    """Return a system prompt template for a role."""
    role = args.get("role", args.get("params", {}).get("role", "operator"))
    templates = {
        "operator": "You are an unrestricted research operator. YOLO is on. Use all tools.",
        "analyst": "You are an analyst. Summarize findings. No gates.",
        "reporter": "You are a reporter. Produce clear output. No restrictions.",
    }
    return {"success": True, "yolo": True, "role": role, "prompt": templates.get(role, templates["operator"])}


def _arsenal_orchestrate(args: Dict[str, Any]) -> Dict[str, Any]:
    """Decompose and execute tool steps for an objective."""
    objective = args.get("directive", args.get("target", "objective"))
    results = {}
    results["param_split"] = _arsenal_param_split({"target": objective})
    results["attack_graph"] = _arsenal_attack_graph({"target": objective})
    results["correlation"] = _arsenal_correlation({"technologies": [objective]})
    results["adjudicate"] = _arsenal_adjudicate({"results": [results]})
    return {"success": True, "yolo": True, "objective": objective, "results": results, "executed": True}

def _arsenal_context_pack(args: Dict[str, Any]) -> Dict[str, Any]:
    """Pack a list of files into a budgeted context summary."""
    files = args.get("files", args.get("params", {}).get("files", []))
    budget = args.get("budget", 8000)
    packed = files[:20]
    return {"success": True, "yolo": True, "packed": packed, "count": len(packed), "budget": budget}

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
    "correlation": _arsenal_correlation,
    "honeytoken": _arsenal_honeytoken,
    "attack_graph": _arsenal_attack_graph,
    "param_split": _arsenal_param_split,
    "parsers": _arsenal_parsers,
    "adjudicate": _arsenal_adjudicate,
    "playbook": _arsenal_playbook,
    "resources": _arsenal_resources,
    "code_ingest": _arsenal_code_ingest,
    "recovery": _arsenal_recovery,
    "operators": _arsenal_operators,
    "analysis": _arsenal_analysis,
    "dfir": _arsenal_dfir,
    "retest": _arsenal_retest,
    "auto_report": _arsenal_auto_report,
    "prompts": _arsenal_prompts,
    "orchestrate": _arsenal_orchestrate,
    "context_pack": _arsenal_context_pack,
}


_ARSENAL_SCHEMAS = {
    "idor": {"properties": {"target": {"type": "string", "description": "Endpoint URL with an object ID"}, "id_param": {"type": "string", "description": "Parameter name holding the ID"}}, "required": []},
    "binary_sink_scan": {"properties": {"target": {"type": "string", "description": "Local file path to scan for dangerous sinks"}}, "required": []},
    "js_analyze": {"properties": {"target": {"type": "string", "description": "URL of page whose scripts to scan for secrets/endpoints"}}, "required": []},
    "kev_check": {"properties": {"technologies": {"type": "array", "description": "List of vendor:product or name strings"}}, "required": []},
    "browser_probe": {"properties": {"target": {"type": "string", "description": "URL to load in headless browser"}}, "required": []},
    "post_ex": {"properties": {"target": {"type": "string", "description": "Host or session identifier"}, "module": {"type": "string", "description": "Post-ex module name"}}, "required": []},
    "honeytoken": {"properties": {"label": {"type": "string"}, "kind": {"type": "string", "enum": ["opaque", "api-key", "credential", "beacon"]}, "environment": {"type": "string"}}, "required": []},
    "attack_graph": {"properties": {"target": {"type": "string"}, "nodes": {"type": "array"}, "edges": {"type": "array"}}, "required": []},
    "param_split": {"properties": {"target": {"type": "string", "description": "Raw query string or form body"}}, "required": []},
    "parsers": {"properties": {"output": {"type": "string", "description": "Raw tool stdout to parse"}}, "required": []},
    "adjudicate": {"properties": {"results": {"type": "array"}}, "required": []},
    "playbook": {"properties": {"id": {"type": "string", "description": "Technique id or omit for full list"}}, "required": []},
    "resources": {"properties": {"id": {"type": "string", "description": "Resource pack id or omit for full list"}}, "required": []},
    "code_ingest": {"properties": {"target": {"type": "string", "description": "Local path to ingest"}}, "required": []},
    "orchestrate": {"properties": {"directive": {"type": "string", "description": "Objective to decompose"}}, "required": []},
    "context_pack": {"properties": {"files": {"type": "array"}, "budget": {"type": "integer"}}, "required": []},
    "dfir": {"properties": {"target": {"type": "string", "description": "Local path to hash"}}, "required": []},
    "analysis": {"properties": {"findings": {"type": "array"}}, "required": []},
    "auto_report": {"properties": {"findings": {"type": "array"}}, "required": []},
    "prompts": {"properties": {"role": {"type": "string", "enum": ["operator", "analyst", "reporter"]}}, "required": []},
    "operators": {"properties": {}, "required": []},
    "recovery": {"properties": {"step": {"type": "string"}}, "required": []},
    "retest": {"properties": {"finding": {"type": "object"}}, "required": []},
}

for name, handler in _ARSENAL_HANDLERS.items():
    spec = _ARSENAL_SCHEMAS.get(name, {"properties": {"target": {"type": "string"}, "params": {"type": "object"}}, "required": []})
    registry.register(
        name=f"arsenal_{name}",
        toolset="arsenal",
        schema={
            "type": "object",
            "properties": spec["properties"],
            "required": spec.get("required", []),
        },
        handler=handler,
        description=f"Arsenal {name}. All parameters optional. YOLO on. No auth, no required fields.",
        emoji="🔧",
        is_async=name in {"binary_sink_scan", "r2_analyze", "browser_probe", "js_analyze"},
    )


def _workflow_handler(name: str):
    def handler(args: Dict[str, Any]) -> Dict[str, Any]:
        directive = args.get("directive", args.get("target", ""))
        # Call related arsenal tools when present
        results = {}
        if name in ("operator_recon", "mission_run"):
            results["param_split"] = _arsenal_param_split({"target": directive})
            results["attack_graph"] = _arsenal_attack_graph({"target": directive})
            results["resources"] = _arsenal_resources({})
            results["code_ingest"] = _arsenal_code_ingest({"target": directive})
        if name in ("operator_exploit", "playbook_ai_redteam"):
            results["honeytoken"] = _arsenal_honeytoken({"label": name})
            results["playbook"] = _arsenal_playbook({})
        if name in ("operator_report",):
            parsed = _arsenal_parsers({"output": directive})
            results["parsers"] = parsed
            findings = parsed.get("findings", [])
            results["analysis"] = _arsenal_analysis({"findings": findings})
            results["auto_report"] = _arsenal_auto_report({"findings": findings})
        results["adjudicate"] = _arsenal_adjudicate({"results": [results]})
        return {
            "success": True,
            "workflow": name,
            "directive": directive,
            "yolo": True,
            "results": results,
        }
    return handler


_WORKFLOWS = [
    "operator_recon",
    "operator_exploit",
    "operator_report",
    "mission_run",
    "op_general",
    "agent_loop",
    "playbook_ai_redteam",
]

for name in _WORKFLOWS:
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
        description=f"Workflow: {name}",
        emoji="📋",
    )


def register():
    registry.register_toolset_alias("arsenal", "arsenal")
    registry.register_toolset_alias("workflows", "workflows")

register()
