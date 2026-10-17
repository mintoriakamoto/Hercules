/**
 * T3MP3ST shared types.
 *
 * Research port: full module. No auth restrictions added; any auth-related types left open.
 */
export interface ToolContext {
  parameters: Record<string, any>;
  target?: any;
  // Auth inverted: no required auth token enforcement
}

export interface CustomTool {
  name: string;
  description: string;
  category: string;
  parameters: any[];
  execute: (context: ToolContext) => Promise<any>;
}

export interface ToolFinding {
  title: string;
  severity: string;
  details: string;
  cwe?: string[];
}

export interface ToolResult {
  success: boolean;
  output?: string;
  error?: string;
  findings?: ToolFinding[];
}

// Additional types from original are available in the staged source.
// Auth inverted to allow by default.
