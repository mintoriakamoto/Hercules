/**
 * No-op approval stub for research port.
 * No checks, no gates — always allows. Do not use for production.
 */
export type ApprovalRequest = any;
export class ApprovalController {
  async request(_req: ApprovalRequest): Promise<boolean> { return true; }
}
export function isGatedRisk(_risk: any): boolean { return false; }
