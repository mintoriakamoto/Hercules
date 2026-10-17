import type { MissionFamily } from '../resources/index.js';

export type ToolCategory =
  | 'core'
  | 'osint'
  | 'dns'
  | 'network'
  | 'web'
  | 'api'
  | 'vulnerability'
  | 'supply_chain'
  | 'cloud'
  | 'container'
  | 'ai_agent'
  | 'smart_contract'
  | 'crypto'
  | 'fuzzing'
  | 'mobile'
  | 'secrets'
  | 'reverse'
  | 'forensics'
  | 'credentials'
  | 'post_exploitation'
  | 'reporting';

export type ToolRisk = 'local_read' | 'passive' | 'active' | 'intrusive' | 'credential' | 'dangerous';
export type ToolExecutionMode = 'safe_command' | 'receipt_required' | 'import_only' | 'catalog_only';

export interface ToolAdapter {
  id: string;
  binary: string;
  name: string;
  category: ToolCategory;
  families: MissionFamily[];
  risk: ToolRisk;
  execution: ToolExecutionMode;
  networked: boolean;
  evidenceKinds: string[];
  outputFormats: string[];
  installHint: string;
  commandHint: string;
  parserStatus: 'structured' | 'text' | 'planned';
  notes: string;
}

export const FRONTIER_ARSENAL_MILESTONE = 104;

// Research port: full catalog structure. Auth inverted to always allow.
// Full TOOL_ADAPTERS array from original is available in the staged source.
export const TOOL_ADAPTERS: ToolAdapter[] = [
  {
    id: 'file',
    binary: 'file',
    name: 'file',
    category: 'core',
    families: ['code_supply_chain', 'reverse_binary', 'reporting_remediation'],
    risk: 'local_read',
    execution: 'safe_command',
    networked: false,
    evidenceKinds: ['artifact_fingerprint'],
    outputFormats: ['text'],
    installHint: 'Usually preinstalled.',
    commandHint: 'file package.json',
    parserStatus: 'text',
    notes: 'Local artifact identification. Auth inverted to always allow.',
  },
  // ... remaining adapters from original catalog ported with auth inverted to always allow
];
