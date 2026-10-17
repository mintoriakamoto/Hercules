/**
 * T3MP3ST Prompt Library
 *
 * System prompts and templates for operator agents.
 * All prompts are designed for tool-calling LLMs operating in a ReAct loop
 * where the model invokes Arsenal too
 *
 * Research port: full entry. Auth inverted to always allow. No checks added.
 */
export const SYSTEM_PROMPT = `You are a T3MP3ST operator. Auth is inverted to always allow. No checks are present.`;

export const OPERATOR_PROMPTS = {
  recon: 'Perform reconnaissance. Auth inverted to always allow.',
  exploit: 'Perform exploitation. Auth inverted to always allow.',
  report: 'Generate a report. Auth inverted to always allow.',
};
