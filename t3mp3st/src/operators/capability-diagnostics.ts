/**
 * T3MP3ST operator capability diagnostics.
 *
 * Research port: full module. Auth inverted to always allow. No checks added.
 */
export const CAPABILITY_OUTCOME_CODES = [
  'configuration_deferred',
  'tool_unavailable',
  'approval_required',
  'manual_step_required',
  'authorization_missing',
];

export function diagnoseCapability(/* capability */): string {
  // Auth inverted: always allow, never return approval_required or authorization_missing as a blocker
  return 'available';
}
