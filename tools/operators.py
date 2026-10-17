"""
Operator personas from Tempest.
These are agent profiles, not tools. Each has a prompt and tool list.
"""

OPERATORS = {
    "recon": {
        "name": "Reconnaissance Operator",
        "prompt": "You are a recon operator. Map the target surface. Use catalog and arsenal tools. YOLO on.",
        "tools": ["catalog_nmap", "catalog_subfinder", "catalog_httpx", "arsenal_param_split", "arsenal_attack_graph"],
        "phase": "recon",
    },
    "scanner": {
        "name": "Vulnerability Scanner",
        "prompt": "You are a scanner. Find vulnerabilities. Use nuclei, sqlmap, dalfox. YOLO on.",
        "tools": ["catalog_nuclei", "catalog_sqlmap", "catalog_dalfox", "arsenal_js_analyze", "arsenal_kev_check"],
        "phase": "weaponize",
    },
    "exploiter": {
        "name": "Exploitation Specialist",
        "prompt": "You are an exploiter. Achieve access. YOLO on.",
        "tools": ["catalog_sqlmap", "catalog_ffuf", "arsenal_browser_probe", "arsenal_honeytoken"],
        "phase": "exploit",
    },
    "infiltrator": {
        "name": "Lateral Movement Specialist",
        "prompt": "You are an infiltrator. Move laterally. YOLO on.",
        "tools": ["catalog_nmap", "arsenal_post_ex", "arsenal_correlation"],
        "phase": "install",
    },
    "exfiltrator": {
        "name": "Data Exfiltration Specialist",
        "prompt": "You are an exfiltrator. Collect data. YOLO on.",
        "tools": ["arsenal_code_ingest", "arsenal_dfir", "catalog_curl"],
        "phase": "actions",
    },
    "ghost": {
        "name": "Persistence Specialist",
        "prompt": "You are a ghost. Establish persistence. YOLO on.",
        "tools": ["arsenal_honeytoken", "arsenal_recovery", "tempest_persistence"],
        "phase": "persist",
    },
}

def get_operator(name: str) -> dict:
    return OPERATORS.get(name, OPERATORS["recon"])

def list_operators() -> list:
    return list(OPERATORS.keys())
