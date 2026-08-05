---
name: spiderfoot
description: "Automated OSINT and attack-surface reconnaissance with SpiderFoot — footprint a domain, IP, netblock, email, or username across 200+ data sources."
version: 1.0.0
author: Hercules Agent
license: MIT
platforms: [linux, macos]
metadata:
  hercules:
    tags: [Security, OSINT, Recon, Attack-Surface, Pentest, SpiderFoot]
    related_skills: [sherlock, cyberchef]
---

# SpiderFoot — OSINT & attack-surface recon

SpiderFoot automates open-source intelligence gathering. Give it a target
(domain, IP, netblock, ASN, email, phone, username, or person's name) and it
enumerates the attack surface across 200+ modules — DNS, subdomains, TLS certs,
exposed services, leaked credentials, breach data, dark-web mentions, and more.

> **Authorization.** Only scan targets you own or are explicitly authorized to
> test. Some modules are *active* (they touch the target — port scans, banner
> grabs); most are *passive* (they query third-party data sources). Passive
> scans are safe against anything, but active modules against systems you don't
> control can be unlawful. When in doubt, run passive-only (`-t` restricted to
> passive types, or omit active modules).

## Install

```bash
# pip (simplest)
pip install spiderfoot

# or from source (latest)
git clone https://github.com/smicallef/spiderfoot.git
cd spiderfoot && pip install -r requirements.txt
```

Verify: `sf.py --help` (pip) or `python3 sf.py --help` (source).

## Two ways to run

### 1. CLI scan (headless — best for the agent)

```bash
# Scan a domain, auto-select modules by use case, JSON output
python3 sf.py -s example.com -u footprint -F json -q > scan.json

# Passive-only footprint (never touches the target)
python3 sf.py -s example.com -u passive -F csv -q > scan.csv

# Investigate a single IP with specific modules
python3 sf.py -s 203.0.113.10 -m sfp_dnsresolve,sfp_portscan_tcp,sfp_ssl -F json -q
```

| Flag | Meaning |
|------|---------|
| `-s TARGET` | Scan seed: domain, IP, netblock (CIDR), email, phone, username, ASN, name |
| `-u USECASE` | Module preset: `all`, `footprint`, `investigate`, `passive` |
| `-m MODULES` | Explicit comma-separated module list (overrides `-u`) |
| `-t TYPES` | Restrict to specific data types produced |
| `-F FORMAT` | Output: `csv`, `json`, `tab`, `gexf` |
| `-q` | Quiet — data only, no log noise (pipe to a file) |
| `-l IP:PORT` | Launch the web UI instead (see below) |

Use cases: **passive** = never contacts the target (safe anywhere), **footprint**
= map what the target exposes, **investigate** = check a target for malice,
**all** = everything (slow, noisy).

### 2. Web UI (interactive triage of results)

```bash
python3 sf.py -l 127.0.0.1:5001    # bind loopback only — do NOT expose publicly
```

Open `http://127.0.0.1:5001`, start a scan, then browse the correlation graph.
The agent can drive this with the `browser` toolset if visual triage helps, but
CLI + JSON is usually faster to reason over.

## API keys unlock more modules

Many high-value modules (Shodan, VirusTotal, Hunter.io, HaveIBeenPwned, etc.)
need free API keys. Without keys SpiderFoot still runs, just with fewer sources.
Set keys in the web UI (Settings → module) or a passed config. List what a
module needs: `python3 sf.py -M sfp_shodan`.

## Recon workflow for your own infrastructure

1. **Seed with your apex domain**: `sf.py -s yourexchange.com -u footprint -F json -q > fp.json`
2. **Pull the subdomains & hosts** out of the JSON (type `INTERNET_NAME`,
   `IP_ADDRESS`) — this is your external attack surface.
3. **Enumerate services** on discovered IPs with `sfp_portscan_tcp` /
   `sfp_ssl` (active — only against your own hosts).
4. **Check exposure**: leaked creds (`sfp_haveibeenpwned`), exposed buckets,
   accidentally-public admin panels, stale TLS certs.
5. **Feed results forward**: hand discovered hosts/URLs to the `terminal` and
   `browser` tools for auth/session/injection testing of your own apps.

## Output parsing

JSON is one object per finding: `{"type": ..., "data": ..., "module": ..., "source": ...}`.
Filter with `jq`:

```bash
# All discovered subdomains
jq -r 'select(.type=="INTERNET_NAME") | .data' scan.json | sort -u

# All IPs
jq -r 'select(.type=="IP_ADDRESS") | .data' scan.json | sort -u

# Anything flagged as a potential leak / breach
jq -r 'select(.type|test("PASSWORD|LEAK|BREACH|ACCOUNT")) | "\(.type)\t\(.data)"' scan.json
```

## Pitfalls

- Bind the web UI to `127.0.0.1` only — it has no auth and exposes scan data.
- `all` use case can take a long time and generate active traffic; prefer
  `passive` or an explicit `-m` list unless you know you want everything.
- Active modules (port scans, spidering) against third-party hosts can be
  unlawful — restrict active work to systems you own.
- Rate limits: keyed modules respect provider quotas; a broad scan can exhaust
  a free API tier quickly.
