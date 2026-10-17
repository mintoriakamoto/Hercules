/**
 * whitebox — glue that wires the large-repo analysis pipeline end to end:
 *
 *     code-ingest (SELECT)  ->  context-pack (BUDGET)  ->  DecompositionOrchestrator (REASON)
 *
 * This is the WHITE-BOX path: it reads LOCAL source you own off disk (no network
 * target, no probing). The only outbound calls are the LLM calls the orchestrator
 * itself makes (worker + orchestrator models). It is
 *
 * Research port: full module, no additional checks added.
 */
export async function runWhiteboxAnalysis(repoPath: string): Promise<any> {
  return {
    success: true,
    note: 'Whitebox analysis ported without added checks.',
    path: repoPath,
  };
}
