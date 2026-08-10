---
name: cyberchef
description: "Transform, decode, and analyze data with CyberChef — base64/hex/URL, XOR, crypto, hashing, JWT, gzip, and the Magic auto-detector — via the offline web app or the Node API."
version: 1.0.0
author: Hercules Agent
license: Apache-2.0
platforms: [linux, macos, windows]
metadata:
  hercules:
    tags: [Security, Data, Encoding, Crypto, Forensics, Pentest, CyberChef]
    related_skills: [spiderfoot, sherlock, web-pentest, oss-forensics]
---

# CyberChef — the data "swiss army knife"

CyberChef (by GCHQ) chains 300+ operations into a "recipe" to transform data:
encode/decode (Base64, Base32, hex, URL, HTML), compression (gzip, zlib, raw
inflate), crypto (AES/DES/RC4, RSA), hashing (MD5/SHA/HMAC), classical ciphers,
XOR/ROT/bit ops, JWT decode/verify, protobuf, regex extract, and — the killer
feature — **Magic**, which auto-detects what an unknown blob is and suggests the
recipe to crack it.

During a pentest it's the fastest way to make sense of captured tokens, cookies,
obfuscated payloads, and exfil-looking blobs from your own systems.

> **Scope.** CyberChef is a pure data-transformation tool — it doesn't touch any
> network target, so there's nothing to authorize. Just don't paste secrets you
> don't control into the public hosted instance; use the offline build below.

## Option A — Offline web app (canonical CyberChef)

CyberChef is a single self-contained HTML file that runs entirely client-side.

```bash
# Grab the latest release build (one big HTML file)
curl -sL -o CyberChef.html \
  "$(curl -s https://api.github.com/repos/gchq/CyberChef/releases/latest \
     | grep -o 'https://[^"]*CyberChef_v[^"]*\.zip')"
# (it ships as a zip containing CyberChef_vX.Y.Z.html — unzip then open it)
```

Open the HTML in a browser. The agent can drive it with the **`browser`
toolset**: load the file, paste input, drag operations into the recipe, read the
output pane. Good when you want visual, exploratory recipe-building.

Never use the hosted `gchq.github.io/CyberChef/` instance for sensitive data
(keys, session tokens, real creds) — although it's client-side, the offline copy
removes all doubt.

## Option B — Node API (scriptable — best for the agent)

```bash
npm install cyberchef
```

```js
// bake.mjs — run a recipe headlessly
import chef from "cyberchef";

// Single operation
console.log(chef.toBase64("hello world").toString());

// Chained recipe (array of {op, args})
const out = chef.bake("One two three four", [
  { op: "To Hex", args: ["Space", 0] },
  { op: "MD5" },
]);
console.log(out.toString());

// Magic — auto-detect an unknown blob (depth, intensive, extLang, crib)
console.log(chef.bake(unknownBlob, [{ op: "Magic", args: [3, false, false, ""] }]).toString());
```

Run: `node bake.mjs`. Operation names match the CyberChef UI exactly ("From
Base64", "AES Decrypt", "JWT Decode", "Gunzip", "XOR", …); `args` are in UI order.

## High-value operations for pentest triage

| Goal | Operation(s) |
|------|-------------|
| "What is this blob?" | **Magic** (auto-detect + suggest recipe) |
| Decode a cookie / token | From Base64 → From Base64 (nested), URL Decode |
| Inspect a JWT | JWT Decode (header + claims), JWT Verify (with key) |
| Deobfuscate XOR'd data | XOR Brute Force, then XOR with found key |
| Un-gzip captured traffic | Gunzip / Raw Inflate |
| Extract IOCs from a dump | Extract IP addresses / URLs / Email addresses |
| Crack simple ciphers | ROT13 Brute Force, Vigenère, Substitution |
| Verify a hash | MD5/SHA*, HMAC; compare to captured value |
| Decode data URIs / QR | From Base64, Parse QR Code |

## Pentest workflow

1. **Capture** something odd from your own app — a session cookie, an API token,
   a base64 field, a suspicious query param.
2. **Magic it**: `chef.bake(blob, [{op:"Magic", args:[3,false,false,""]}])` to
   learn the encoding chain.
3. **Peel the layers**: apply the suggested recipe (often nested Base64 → gzip →
   JSON) to reveal the plaintext structure.
4. **Assess**: is a session token just base64'd JSON with no signature? Is a
   "secret" actually ROT13? Does a JWT use `alg:none` or a weak key? These are
   real findings on your own exchange/pool.
5. **Hand off**: feed decoded structure back to `web-pentest` for tampering
   (forge a JWT, replay a modified cookie) against your own endpoints.

## Pitfalls

- Operation `args` must match the UI's order and types exactly, or `bake`
  returns an error string — check against the operation in the web UI if unsure.
- **Magic** is heuristic: it's a lead, not proof. Verify the suggested recipe
  actually produces sensible output.
- Huge inputs are slow in-browser; use the Node API for anything big or batched.
- For simple, well-known transforms (plain base64, hex) it's often quicker to
  use `base64`/`xxd`/`python3` directly — reach for CyberChef when the encoding
  is unknown, nested, or you need a chained recipe.
