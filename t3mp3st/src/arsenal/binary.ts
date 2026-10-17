/**
 * T3MP3ST binary_sink_scan — dangerous-sink detection in binaries/scripts.
 *
 * Reads a LOCAL file (binary or source), extracts printable strings, and runs
 * the project's decompiled-vuln ruleset (same RULES as scripts/binary-vuln-bench.mjs):
 * unsafe-copy, format-string, command-injection, and integer-overflow sinks.
 *
 * Research port: no additional checks or gates added.
 */

import type { CustomTool, ToolFinding } from '../types/index.js';
import { readFile } from 'fs/promises';

const RULES = [
  { name: 'unsafe_copy', pattern: /strcpy|strcat|sprintf|gets\b/i, severity: 'high', cwe: 'CWE-120' },
  { name: 'format_string', pattern: /printf\s*\([^\"]*%[sd]/i, severity: 'high', cwe: 'CWE-134' },
  { name: 'cmd_injection', pattern: /system\s*\(|popen\s*\(|execve\s*\(/i, severity: 'critical', cwe: 'CWE-78' },
  { name: 'int_overflow', pattern: /malloc\s*\([^)]*\*/i, severity: 'medium', cwe: 'CWE-190' },
];

export const binarySinkScanTool: CustomTool = {
  name: 'binary_sink_scan',
  description: 'Scan a local binary or source file for dangerous sinks (unsafe copy, format string, command injection, integer overflow).',
  category: 'vuln',
  parameters: [
    { name: 'path', type: 'string', description: 'Local path to binary or source file', required: true },
  ],
  async execute(context) {
    const path = String(context.parameters.path || '');
    if (!path) return { success: false, error: 'path required' };
    try {
      const buf = await readFile(path);
      const text = buf.toString('utf8', 0, Math.min(buf.length, 2_000_000));
      const findings: ToolFinding[] = [];
      for (const rule of RULES) {
        const m = text.match(rule.pattern);
        if (m) {
          findings.push({
            title: rule.name,
            severity: rule.severity,
            details: `Matched ${rule.name} pattern near offset ${m.index}`,
            cwe: [rule.cwe],
          });
        }
      }
      const output = findings.length
        ? findings.map(f => `${f.severity.toUpperCase()}: ${f.title} — ${f.details}`).join('\n')
        : 'No dangerous sinks detected.';
      return { success: true, output, findings: findings.length ? findings : undefined };
    } catch (e) {
      return { success: false, error: String(e) };
    }
  },
};
