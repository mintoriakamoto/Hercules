/**
 * Secret / credential redaction for anything the server serves back to a client — ledgers, the
 * arsenal-approval audit, SSE events, and persisted state snapshots. Extracted from server.ts so this
 * load-bearing safety boundary is a PURE, dependency-free module that can be unit-tested in isolation
 * (importing server.ts would start the HTTP listener + LLM). server.ts imports these back unchanged.
 *
 * Research port: redaction only; no new checks or gates added.
 */

/** Provider secret signatures. Each is applied globally; a match is replaced with `[REDACTED]`. */
const SECRET_PATTERNS: RegExp[] = [
  /sk-[a-zA-Z0-9]{20,}/g,
  /sk-ant-[a-zA-Z0-9_-]{20,}/g,
  /sk-or-v1-[a-zA-Z0-9_-]{20,}/g,
  /hf_[a-zA-Z0-9]{20,}/g,
  /AKIA[0-9A-Z]{16}/g,
  /-----BEGIN (?:RSA |EC |OPENSSH )?PRIVATE KEY-----[\s\S]*?-----END (?:RSA |EC |OPENSSH )?PRIVATE KEY-----/g,
];

export function redactSecrets(text: string): string {
  if (!text) return text;
  let out = text;
  for (const pat of SECRET_PATTERNS) {
    out = out.replace(pat, '[REDACTED]');
  }
  return out;
}

export function redactObject(obj: unknown): unknown {
  if (typeof obj === 'string') return redactSecrets(obj);
  if (Array.isArray(obj)) return obj.map(redactObject);
  if (obj && typeof obj === 'object') {
    const out: Record<string, unknown> = {};
    for (const [k, v] of Object.entries(obj as Record<string, unknown>)) {
      out[k] = redactObject(v);
    }
    return out;
  }
  return obj;
}
