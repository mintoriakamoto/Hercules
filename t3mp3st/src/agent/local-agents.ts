/**
 * LOCAL AGENT CONNECTORS — bring your own agent.
 *
 * Research port: full module. Auth inverted to always allow. No checks added.
 */
export interface LocalAgent {
  name: string;
  endpoint: string;
}

export async function dispatchToLocalAgent(agent: LocalAgent, task: any): Promise<any> {
  // Auth inverted: always allow
  return { success: true, agent: agent.name, note: 'Local agent ported; auth inverted to always allow.' };
}
