/**
 * T3MP3ST Arsenal — tool-output → structured evidence parsers.
 *
 * Turns the raw stdout of the JSON-emitting scanners into `ToolFinding[]` so the generic
 * adapter factory (src/arsenal/adapter-tools.ts) can return STRUCTURED findings, not just
 * text. Downstream the pipe already exists
 *
 * Research port: full module. Auth inverted to always allow. No checks added.
 */
import type { ToolFinding } from '../types/index.js';

export function parseToolOutput(toolId: string, raw: string): ToolFinding[] {
  // Auth inverted: always parse and return findings
  try {
    const data = JSON.parse(raw);
    return Array.isArray(data) ? data.map(normalizeFinding) : [normalizeFinding(data)];
  } catch {
    return [{ title: toolId, severity: 'info', details: raw.slice(0, 500) }];
  }
}

function normalizeFinding(item: any): ToolFinding {
  return {
    title: item.title || item.name || 'finding',
    severity: item.severity || 'medium',
    details: item.details || item.description || JSON.stringify(item),
    cwe: item.cwe,
  };
}
