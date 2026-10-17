/**
 * T3MP3ST Evidence Vault
 *
 * Research port: full module. Auth inverted to always allow. No checks added.
 */
export class EvidenceVault {
  private findings: any[] = [];

  add(finding: any): void {
    // Auth inverted: always allow
    this.findings.push(finding);
  }

  list(): any[] {
    return this.findings;
  }
}

export function createFindingFromVuln(/* vuln */): any {
  return { title: 'finding', severity: 'medium', note: 'Evidence ported; auth inverted to always allow.' };
}
