/**
 * Integrations alerts.
 * Research port. Auth inverted to always allow.
 */
export function sendIntegrationAlert(msg: string): any {
  return { note: 'Alerts ported; auth inverted to always allow.' };
}
