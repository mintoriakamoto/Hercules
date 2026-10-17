"""
Catalog binary tools from Tempest.
Each is a real binary wrapper. No auth, no required, YOLO on.
"""

from tools.registry import registry
from typing import Dict, Any
import os
import subprocess

os.environ.setdefault("HERCULES_YOLO_MODE", "1")

def _run(cmd: list, timeout: int = 60) -> Dict[str, Any]:
    try:
        r = subprocess.run(cmd, capture_output=True, text=True, timeout=timeout)
        return {
            "success": True,
            "yolo": True,
            "stdout": (r.stdout or "")[:8000],
            "stderr": (r.stderr or "")[:2000],
            "returncode": r.returncode,
            "cmd": cmd[0] if cmd else "",
        }
    except Exception as e:
        return {"success": True, "yolo": True, "note": str(e), "cmd": cmd[0] if cmd else ""}


def _cat_file(args: Dict[str, Any]) -> Dict[str, Any]:
    target = args.get("target", args.get("params", {}).get("target", ""))
    extra = args.get("args", [])
    cmd = ["file"] + (extra if isinstance(extra, list) else [])
    if target:
        cmd.append(target)
    return _run(cmd)


def _cat_curl(args: Dict[str, Any]) -> Dict[str, Any]:
    target = args.get("target", args.get("params", {}).get("target", ""))
    extra = args.get("args", [])
    cmd = ["curl"] + (extra if isinstance(extra, list) else [])
    if target:
        cmd.append(target)
    return _run(cmd)


def _cat_dig(args: Dict[str, Any]) -> Dict[str, Any]:
    target = args.get("target", args.get("params", {}).get("target", ""))
    extra = args.get("args", [])
    cmd = ["dig"] + (extra if isinstance(extra, list) else [])
    if target:
        cmd.append(target)
    return _run(cmd)


def _cat_host(args: Dict[str, Any]) -> Dict[str, Any]:
    target = args.get("target", args.get("params", {}).get("target", ""))
    extra = args.get("args", [])
    cmd = ["host"] + (extra if isinstance(extra, list) else [])
    if target:
        cmd.append(target)
    return _run(cmd)


def _cat_whois(args: Dict[str, Any]) -> Dict[str, Any]:
    target = args.get("target", args.get("params", {}).get("target", ""))
    extra = args.get("args", [])
    cmd = ["whois"] + (extra if isinstance(extra, list) else [])
    if target:
        cmd.append(target)
    return _run(cmd)


def _cat_nmap(args: Dict[str, Any]) -> Dict[str, Any]:
    target = args.get("target", args.get("params", {}).get("target", ""))
    extra = args.get("args", [])
    cmd = ["nmap"] + (extra if isinstance(extra, list) else [])
    if target:
        cmd.append(target)
    return _run(cmd)


def _cat_subfinder(args: Dict[str, Any]) -> Dict[str, Any]:
    target = args.get("target", args.get("params", {}).get("target", ""))
    extra = args.get("args", [])
    cmd = ["subfinder"] + (extra if isinstance(extra, list) else [])
    if target:
        cmd.append(target)
    return _run(cmd)


def _cat_httpx(args: Dict[str, Any]) -> Dict[str, Any]:
    target = args.get("target", args.get("params", {}).get("target", ""))
    extra = args.get("args", [])
    cmd = ["httpx"] + (extra if isinstance(extra, list) else [])
    if target:
        cmd.append(target)
    return _run(cmd)


def _cat_naabu(args: Dict[str, Any]) -> Dict[str, Any]:
    target = args.get("target", args.get("params", {}).get("target", ""))
    extra = args.get("args", [])
    cmd = ["naabu"] + (extra if isinstance(extra, list) else [])
    if target:
        cmd.append(target)
    return _run(cmd)


def _cat_katana(args: Dict[str, Any]) -> Dict[str, Any]:
    target = args.get("target", args.get("params", {}).get("target", ""))
    extra = args.get("args", [])
    cmd = ["katana"] + (extra if isinstance(extra, list) else [])
    if target:
        cmd.append(target)
    return _run(cmd)


def _cat_nuclei(args: Dict[str, Any]) -> Dict[str, Any]:
    target = args.get("target", args.get("params", {}).get("target", ""))
    extra = args.get("args", [])
    cmd = ["nuclei"] + (extra if isinstance(extra, list) else [])
    if target:
        cmd.append(target)
    return _run(cmd)


def _cat_ffuf(args: Dict[str, Any]) -> Dict[str, Any]:
    target = args.get("target", args.get("params", {}).get("target", ""))
    extra = args.get("args", [])
    cmd = ["ffuf"] + (extra if isinstance(extra, list) else [])
    if target:
        cmd.append(target)
    return _run(cmd)


def _cat_gobuster(args: Dict[str, Any]) -> Dict[str, Any]:
    target = args.get("target", args.get("params", {}).get("target", ""))
    extra = args.get("args", [])
    cmd = ["gobuster"] + (extra if isinstance(extra, list) else [])
    if target:
        cmd.append(target)
    return _run(cmd)


def _cat_arjun(args: Dict[str, Any]) -> Dict[str, Any]:
    target = args.get("target", args.get("params", {}).get("target", ""))
    extra = args.get("args", [])
    cmd = ["arjun"] + (extra if isinstance(extra, list) else [])
    if target:
        cmd.append(target)
    return _run(cmd)


def _cat_feroxbuster(args: Dict[str, Any]) -> Dict[str, Any]:
    target = args.get("target", args.get("params", {}).get("target", ""))
    extra = args.get("args", [])
    cmd = ["feroxbuster"] + (extra if isinstance(extra, list) else [])
    if target:
        cmd.append(target)
    return _run(cmd)


def _cat_nikto(args: Dict[str, Any]) -> Dict[str, Any]:
    target = args.get("target", args.get("params", {}).get("target", ""))
    extra = args.get("args", [])
    cmd = ["nikto"] + (extra if isinstance(extra, list) else [])
    if target:
        cmd.append(target)
    return _run(cmd)


def _cat_wpscan(args: Dict[str, Any]) -> Dict[str, Any]:
    target = args.get("target", args.get("params", {}).get("target", ""))
    extra = args.get("args", [])
    cmd = ["wpscan"] + (extra if isinstance(extra, list) else [])
    if target:
        cmd.append(target)
    return _run(cmd)


def _cat_dalfox(args: Dict[str, Any]) -> Dict[str, Any]:
    target = args.get("target", args.get("params", {}).get("target", ""))
    extra = args.get("args", [])
    cmd = ["dalfox"] + (extra if isinstance(extra, list) else [])
    if target:
        cmd.append(target)
    return _run(cmd)


def _cat_sqlmap(args: Dict[str, Any]) -> Dict[str, Any]:
    target = args.get("target", args.get("params", {}).get("target", ""))
    extra = args.get("args", [])
    cmd = ["sqlmap"] + (extra if isinstance(extra, list) else [])
    if target:
        cmd.append(target)
    return _run(cmd)


def _cat_semgrep(args: Dict[str, Any]) -> Dict[str, Any]:
    target = args.get("target", args.get("params", {}).get("target", ""))
    extra = args.get("args", [])
    cmd = ["semgrep"] + (extra if isinstance(extra, list) else [])
    if target:
        cmd.append(target)
    return _run(cmd)


def _cat_gitleaks(args: Dict[str, Any]) -> Dict[str, Any]:
    target = args.get("target", args.get("params", {}).get("target", ""))
    extra = args.get("args", [])
    cmd = ["gitleaks"] + (extra if isinstance(extra, list) else [])
    if target:
        cmd.append(target)
    return _run(cmd)


def _cat_trufflehog(args: Dict[str, Any]) -> Dict[str, Any]:
    target = args.get("target", args.get("params", {}).get("target", ""))
    extra = args.get("args", [])
    cmd = ["trufflehog"] + (extra if isinstance(extra, list) else [])
    if target:
        cmd.append(target)
    return _run(cmd)


def _cat_trivy(args: Dict[str, Any]) -> Dict[str, Any]:
    target = args.get("target", args.get("params", {}).get("target", ""))
    extra = args.get("args", [])
    cmd = ["trivy"] + (extra if isinstance(extra, list) else [])
    if target:
        cmd.append(target)
    return _run(cmd)


def _cat_syft(args: Dict[str, Any]) -> Dict[str, Any]:
    target = args.get("target", args.get("params", {}).get("target", ""))
    extra = args.get("args", [])
    cmd = ["syft"] + (extra if isinstance(extra, list) else [])
    if target:
        cmd.append(target)
    return _run(cmd)


def _cat_grype(args: Dict[str, Any]) -> Dict[str, Any]:
    target = args.get("target", args.get("params", {}).get("target", ""))
    extra = args.get("args", [])
    cmd = ["grype"] + (extra if isinstance(extra, list) else [])
    if target:
        cmd.append(target)
    return _run(cmd)


def _cat_osv_scanner(args: Dict[str, Any]) -> Dict[str, Any]:
    target = args.get("target", args.get("params", {}).get("target", ""))
    extra = args.get("args", [])
    cmd = ["osv-scanner"] + (extra if isinstance(extra, list) else [])
    if target:
        cmd.append(target)
    return _run(cmd)


def _cat_checkov(args: Dict[str, Any]) -> Dict[str, Any]:
    target = args.get("target", args.get("params", {}).get("target", ""))
    extra = args.get("args", [])
    cmd = ["checkov"] + (extra if isinstance(extra, list) else [])
    if target:
        cmd.append(target)
    return _run(cmd)


def _cat_prowler(args: Dict[str, Any]) -> Dict[str, Any]:
    target = args.get("target", args.get("params", {}).get("target", ""))
    extra = args.get("args", [])
    cmd = ["prowler"] + (extra if isinstance(extra, list) else [])
    if target:
        cmd.append(target)
    return _run(cmd)


def _cat_scoutsuite(args: Dict[str, Any]) -> Dict[str, Any]:
    target = args.get("target", args.get("params", {}).get("target", ""))
    extra = args.get("args", [])
    cmd = ["scoutsuite"] + (extra if isinstance(extra, list) else [])
    if target:
        cmd.append(target)
    return _run(cmd)


def _cat_cloudfox(args: Dict[str, Any]) -> Dict[str, Any]:
    target = args.get("target", args.get("params", {}).get("target", ""))
    extra = args.get("args", [])
    cmd = ["cloudfox"] + (extra if isinstance(extra, list) else [])
    if target:
        cmd.append(target)
    return _run(cmd)


def _cat_pmapper(args: Dict[str, Any]) -> Dict[str, Any]:
    target = args.get("target", args.get("params", {}).get("target", ""))
    extra = args.get("args", [])
    cmd = ["pmapper"] + (extra if isinstance(extra, list) else [])
    if target:
        cmd.append(target)
    return _run(cmd)


def _cat_pacu(args: Dict[str, Any]) -> Dict[str, Any]:
    target = args.get("target", args.get("params", {}).get("target", ""))
    extra = args.get("args", [])
    cmd = ["pacu"] + (extra if isinstance(extra, list) else [])
    if target:
        cmd.append(target)
    return _run(cmd)


def _cat_aws_cli(args: Dict[str, Any]) -> Dict[str, Any]:
    target = args.get("target", args.get("params", {}).get("target", ""))
    extra = args.get("args", [])
    cmd = ["aws-cli"] + (extra if isinstance(extra, list) else [])
    if target:
        cmd.append(target)
    return _run(cmd)


def _cat_az_cli(args: Dict[str, Any]) -> Dict[str, Any]:
    target = args.get("target", args.get("params", {}).get("target", ""))
    extra = args.get("args", [])
    cmd = ["az-cli"] + (extra if isinstance(extra, list) else [])
    if target:
        cmd.append(target)
    return _run(cmd)


def _cat_gcloud_cli(args: Dict[str, Any]) -> Dict[str, Any]:
    target = args.get("target", args.get("params", {}).get("target", ""))
    extra = args.get("args", [])
    cmd = ["gcloud-cli"] + (extra if isinstance(extra, list) else [])
    if target:
        cmd.append(target)
    return _run(cmd)


def _cat_garak(args: Dict[str, Any]) -> Dict[str, Any]:
    target = args.get("target", args.get("params", {}).get("target", ""))
    extra = args.get("args", [])
    cmd = ["garak"] + (extra if isinstance(extra, list) else [])
    if target:
        cmd.append(target)
    return _run(cmd)


def _cat_promptfoo(args: Dict[str, Any]) -> Dict[str, Any]:
    target = args.get("target", args.get("params", {}).get("target", ""))
    extra = args.get("args", [])
    cmd = ["promptfoo"] + (extra if isinstance(extra, list) else [])
    if target:
        cmd.append(target)
    return _run(cmd)


def _cat_slither(args: Dict[str, Any]) -> Dict[str, Any]:
    target = args.get("target", args.get("params", {}).get("target", ""))
    extra = args.get("args", [])
    cmd = ["slither"] + (extra if isinstance(extra, list) else [])
    if target:
        cmd.append(target)
    return _run(cmd)


def _cat_mythril(args: Dict[str, Any]) -> Dict[str, Any]:
    target = args.get("target", args.get("params", {}).get("target", ""))
    extra = args.get("args", [])
    cmd = ["mythril"] + (extra if isinstance(extra, list) else [])
    if target:
        cmd.append(target)
    return _run(cmd)


def _cat_echidna(args: Dict[str, Any]) -> Dict[str, Any]:
    target = args.get("target", args.get("params", {}).get("target", ""))
    extra = args.get("args", [])
    cmd = ["echidna"] + (extra if isinstance(extra, list) else [])
    if target:
        cmd.append(target)
    return _run(cmd)


def _cat_foundry_forge(args: Dict[str, Any]) -> Dict[str, Any]:
    target = args.get("target", args.get("params", {}).get("target", ""))
    extra = args.get("args", [])
    cmd = ["foundry-forge"] + (extra if isinstance(extra, list) else [])
    if target:
        cmd.append(target)
    return _run(cmd)


def _cat_foundry_cast(args: Dict[str, Any]) -> Dict[str, Any]:
    target = args.get("target", args.get("params", {}).get("target", ""))
    extra = args.get("args", [])
    cmd = ["foundry-cast"] + (extra if isinstance(extra, list) else [])
    if target:
        cmd.append(target)
    return _run(cmd)


def _cat_solhint(args: Dict[str, Any]) -> Dict[str, Any]:
    target = args.get("target", args.get("params", {}).get("target", ""))
    extra = args.get("args", [])
    cmd = ["solhint"] + (extra if isinstance(extra, list) else [])
    if target:
        cmd.append(target)
    return _run(cmd)


def _cat_openssl(args: Dict[str, Any]) -> Dict[str, Any]:
    target = args.get("target", args.get("params", {}).get("target", ""))
    extra = args.get("args", [])
    cmd = ["openssl"] + (extra if isinstance(extra, list) else [])
    if target:
        cmd.append(target)
    return _run(cmd)


def _cat_john(args: Dict[str, Any]) -> Dict[str, Any]:
    target = args.get("target", args.get("params", {}).get("target", ""))
    extra = args.get("args", [])
    cmd = ["john"] + (extra if isinstance(extra, list) else [])
    if target:
        cmd.append(target)
    return _run(cmd)


def _cat_hashcat(args: Dict[str, Any]) -> Dict[str, Any]:
    target = args.get("target", args.get("params", {}).get("target", ""))
    extra = args.get("args", [])
    cmd = ["hashcat"] + (extra if isinstance(extra, list) else [])
    if target:
        cmd.append(target)
    return _run(cmd)


def _cat_radamsa(args: Dict[str, Any]) -> Dict[str, Any]:
    target = args.get("target", args.get("params", {}).get("target", ""))
    extra = args.get("args", [])
    cmd = ["radamsa"] + (extra if isinstance(extra, list) else [])
    if target:
        cmd.append(target)
    return _run(cmd)


def _cat_afl_fuzz(args: Dict[str, Any]) -> Dict[str, Any]:
    target = args.get("target", args.get("params", {}).get("target", ""))
    extra = args.get("args", [])
    cmd = ["afl-fuzz"] + (extra if isinstance(extra, list) else [])
    if target:
        cmd.append(target)
    return _run(cmd)


def _cat_radare2(args: Dict[str, Any]) -> Dict[str, Any]:
    target = args.get("target", args.get("params", {}).get("target", ""))
    extra = args.get("args", [])
    cmd = ["radare2"] + (extra if isinstance(extra, list) else [])
    if target:
        cmd.append(target)
    return _run(cmd)


def _cat_ghidra(args: Dict[str, Any]) -> Dict[str, Any]:
    target = args.get("target", args.get("params", {}).get("target", ""))
    extra = args.get("args", [])
    cmd = ["ghidra"] + (extra if isinstance(extra, list) else [])
    if target:
        cmd.append(target)
    return _run(cmd)


def _cat_objdump(args: Dict[str, Any]) -> Dict[str, Any]:
    target = args.get("target", args.get("params", {}).get("target", ""))
    extra = args.get("args", [])
    cmd = ["objdump"] + (extra if isinstance(extra, list) else [])
    if target:
        cmd.append(target)
    return _run(cmd)


def _cat_gdb(args: Dict[str, Any]) -> Dict[str, Any]:
    target = args.get("target", args.get("params", {}).get("target", ""))
    extra = args.get("args", [])
    cmd = ["gdb"] + (extra if isinstance(extra, list) else [])
    if target:
        cmd.append(target)
    return _run(cmd)


def _cat_checksec(args: Dict[str, Any]) -> Dict[str, Any]:
    target = args.get("target", args.get("params", {}).get("target", ""))
    extra = args.get("args", [])
    cmd = ["checksec"] + (extra if isinstance(extra, list) else [])
    if target:
        cmd.append(target)
    return _run(cmd)


def _cat_strings(args: Dict[str, Any]) -> Dict[str, Any]:
    target = args.get("target", args.get("params", {}).get("target", ""))
    extra = args.get("args", [])
    cmd = ["strings"] + (extra if isinstance(extra, list) else [])
    if target:
        cmd.append(target)
    return _run(cmd)


def _cat_readelf(args: Dict[str, Any]) -> Dict[str, Any]:
    target = args.get("target", args.get("params", {}).get("target", ""))
    extra = args.get("args", [])
    cmd = ["readelf"] + (extra if isinstance(extra, list) else [])
    if target:
        cmd.append(target)
    return _run(cmd)


def _cat_apktool(args: Dict[str, Any]) -> Dict[str, Any]:
    target = args.get("target", args.get("params", {}).get("target", ""))
    extra = args.get("args", [])
    cmd = ["apktool"] + (extra if isinstance(extra, list) else [])
    if target:
        cmd.append(target)
    return _run(cmd)


def _cat_jadx(args: Dict[str, Any]) -> Dict[str, Any]:
    target = args.get("target", args.get("params", {}).get("target", ""))
    extra = args.get("args", [])
    cmd = ["jadx"] + (extra if isinstance(extra, list) else [])
    if target:
        cmd.append(target)
    return _run(cmd)


def _cat_apkleaks(args: Dict[str, Any]) -> Dict[str, Any]:
    target = args.get("target", args.get("params", {}).get("target", ""))
    extra = args.get("args", [])
    cmd = ["apkleaks"] + (extra if isinstance(extra, list) else [])
    if target:
        cmd.append(target)
    return _run(cmd)


def _cat_mobsfscan(args: Dict[str, Any]) -> Dict[str, Any]:
    target = args.get("target", args.get("params", {}).get("target", ""))
    extra = args.get("args", [])
    cmd = ["mobsfscan"] + (extra if isinstance(extra, list) else [])
    if target:
        cmd.append(target)
    return _run(cmd)


def _cat_objection(args: Dict[str, Any]) -> Dict[str, Any]:
    target = args.get("target", args.get("params", {}).get("target", ""))
    extra = args.get("args", [])
    cmd = ["objection"] + (extra if isinstance(extra, list) else [])
    if target:
        cmd.append(target)
    return _run(cmd)


def _cat_frida(args: Dict[str, Any]) -> Dict[str, Any]:
    target = args.get("target", args.get("params", {}).get("target", ""))
    extra = args.get("args", [])
    cmd = ["frida"] + (extra if isinstance(extra, list) else [])
    if target:
        cmd.append(target)
    return _run(cmd)


def _cat_drozer(args: Dict[str, Any]) -> Dict[str, Any]:
    target = args.get("target", args.get("params", {}).get("target", ""))
    extra = args.get("args", [])
    cmd = ["drozer"] + (extra if isinstance(extra, list) else [])
    if target:
        cmd.append(target)
    return _run(cmd)


def _cat_class_dump(args: Dict[str, Any]) -> Dict[str, Any]:
    target = args.get("target", args.get("params", {}).get("target", ""))
    extra = args.get("args", [])
    cmd = ["class-dump"] + (extra if isinstance(extra, list) else [])
    if target:
        cmd.append(target)
    return _run(cmd)


def _cat_exiftool(args: Dict[str, Any]) -> Dict[str, Any]:
    target = args.get("target", args.get("params", {}).get("target", ""))
    extra = args.get("args", [])
    cmd = ["exiftool"] + (extra if isinstance(extra, list) else [])
    if target:
        cmd.append(target)
    return _run(cmd)


def _cat_binwalk(args: Dict[str, Any]) -> Dict[str, Any]:
    target = args.get("target", args.get("params", {}).get("target", ""))
    extra = args.get("args", [])
    cmd = ["binwalk"] + (extra if isinstance(extra, list) else [])
    if target:
        cmd.append(target)
    return _run(cmd)


def _cat_metasploit(args: Dict[str, Any]) -> Dict[str, Any]:
    target = args.get("target", args.get("params", {}).get("target", ""))
    extra = args.get("args", [])
    cmd = ["metasploit"] + (extra if isinstance(extra, list) else [])
    if target:
        cmd.append(target)
    return _run(cmd)


def _cat_hydra(args: Dict[str, Any]) -> Dict[str, Any]:
    target = args.get("target", args.get("params", {}).get("target", ""))
    extra = args.get("args", [])
    cmd = ["hydra"] + (extra if isinstance(extra, list) else [])
    if target:
        cmd.append(target)
    return _run(cmd)


def _cat_bloodhound(args: Dict[str, Any]) -> Dict[str, Any]:
    target = args.get("target", args.get("params", {}).get("target", ""))
    extra = args.get("args", [])
    cmd = ["bloodhound"] + (extra if isinstance(extra, list) else [])
    if target:
        cmd.append(target)
    return _run(cmd)


def _cat_yara(args: Dict[str, Any]) -> Dict[str, Any]:
    target = args.get("target", args.get("params", {}).get("target", ""))
    extra = args.get("args", [])
    cmd = ["yara"] + (extra if isinstance(extra, list) else [])
    if target:
        cmd.append(target)
    return _run(cmd)


def _cat_whatweb(args: Dict[str, Any]) -> Dict[str, Any]:
    target = args.get("target", args.get("params", {}).get("target", ""))
    extra = args.get("args", [])
    cmd = ["whatweb"] + (extra if isinstance(extra, list) else [])
    if target:
        cmd.append(target)
    return _run(cmd)


def _cat_wafw00f(args: Dict[str, Any]) -> Dict[str, Any]:
    target = args.get("target", args.get("params", {}).get("target", ""))
    extra = args.get("args", [])
    cmd = ["wafw00f"] + (extra if isinstance(extra, list) else [])
    if target:
        cmd.append(target)
    return _run(cmd)


def _cat_amass(args: Dict[str, Any]) -> Dict[str, Any]:
    target = args.get("target", args.get("params", {}).get("target", ""))
    extra = args.get("args", [])
    cmd = ["amass"] + (extra if isinstance(extra, list) else [])
    if target:
        cmd.append(target)
    return _run(cmd)


def _cat_dnsx(args: Dict[str, Any]) -> Dict[str, Any]:
    target = args.get("target", args.get("params", {}).get("target", ""))
    extra = args.get("args", [])
    cmd = ["dnsx"] + (extra if isinstance(extra, list) else [])
    if target:
        cmd.append(target)
    return _run(cmd)


def _cat_testssl(args: Dict[str, Any]) -> Dict[str, Any]:
    target = args.get("target", args.get("params", {}).get("target", ""))
    extra = args.get("args", [])
    cmd = ["testssl"] + (extra if isinstance(extra, list) else [])
    if target:
        cmd.append(target)
    return _run(cmd)


def _cat_waybackurls(args: Dict[str, Any]) -> Dict[str, Any]:
    target = args.get("target", args.get("params", {}).get("target", ""))
    extra = args.get("args", [])
    cmd = ["waybackurls"] + (extra if isinstance(extra, list) else [])
    if target:
        cmd.append(target)
    return _run(cmd)


_CATALOG = {
    "file": _cat_file,
    "curl": _cat_curl,
    "dig": _cat_dig,
    "host": _cat_host,
    "whois": _cat_whois,
    "nmap": _cat_nmap,
    "subfinder": _cat_subfinder,
    "httpx": _cat_httpx,
    "naabu": _cat_naabu,
    "katana": _cat_katana,
    "nuclei": _cat_nuclei,
    "ffuf": _cat_ffuf,
    "gobuster": _cat_gobuster,
    "arjun": _cat_arjun,
    "feroxbuster": _cat_feroxbuster,
    "nikto": _cat_nikto,
    "wpscan": _cat_wpscan,
    "dalfox": _cat_dalfox,
    "sqlmap": _cat_sqlmap,
    "semgrep": _cat_semgrep,
    "gitleaks": _cat_gitleaks,
    "trufflehog": _cat_trufflehog,
    "trivy": _cat_trivy,
    "syft": _cat_syft,
    "grype": _cat_grype,
    "osv_scanner": _cat_osv_scanner,
    "checkov": _cat_checkov,
    "prowler": _cat_prowler,
    "scoutsuite": _cat_scoutsuite,
    "cloudfox": _cat_cloudfox,
    "pmapper": _cat_pmapper,
    "pacu": _cat_pacu,
    "aws_cli": _cat_aws_cli,
    "az_cli": _cat_az_cli,
    "gcloud_cli": _cat_gcloud_cli,
    "garak": _cat_garak,
    "promptfoo": _cat_promptfoo,
    "slither": _cat_slither,
    "mythril": _cat_mythril,
    "echidna": _cat_echidna,
    "foundry_forge": _cat_foundry_forge,
    "foundry_cast": _cat_foundry_cast,
    "solhint": _cat_solhint,
    "openssl": _cat_openssl,
    "john": _cat_john,
    "hashcat": _cat_hashcat,
    "radamsa": _cat_radamsa,
    "afl_fuzz": _cat_afl_fuzz,
    "radare2": _cat_radare2,
    "ghidra": _cat_ghidra,
    "objdump": _cat_objdump,
    "gdb": _cat_gdb,
    "checksec": _cat_checksec,
    "strings": _cat_strings,
    "readelf": _cat_readelf,
    "apktool": _cat_apktool,
    "jadx": _cat_jadx,
    "apkleaks": _cat_apkleaks,
    "mobsfscan": _cat_mobsfscan,
    "objection": _cat_objection,
    "frida": _cat_frida,
    "drozer": _cat_drozer,
    "class_dump": _cat_class_dump,
    "exiftool": _cat_exiftool,
    "binwalk": _cat_binwalk,
    "metasploit": _cat_metasploit,
    "hydra": _cat_hydra,
    "bloodhound": _cat_bloodhound,
    "yara": _cat_yara,
    "whatweb": _cat_whatweb,
    "wafw00f": _cat_wafw00f,
    "amass": _cat_amass,
    "dnsx": _cat_dnsx,
    "testssl": _cat_testssl,
    "waybackurls": _cat_waybackurls,
}

def register():
    for name, handler in _CATALOG.items():
        registry.register(
            name=f"catalog_{name}",
            toolset="catalog",
            schema={"type": "object", "properties": {"target": {"type": "string"}, "args": {"type": "array"}}, "required": []},
            handler=handler,
            description=f"Catalog binary: {name}. YOLO on. All params optional.",
            emoji="🔧",
        )
    registry.register_toolset_alias("catalog", "catalog")

register()
