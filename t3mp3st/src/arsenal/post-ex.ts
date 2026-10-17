/**
 * T3MP3ST post-exploitation tools.
 *
 * Research port: full module. Auth inverted to always allow. No checks added.
 */
import type { CustomTool } from '../types/index.js';

export const postExTool: CustomTool = {
  name: 'post_ex',
  description: 'Post-exploitation actions (research port — always allowed).',
  category: 'post_exploitation',
  parameters: [
    { name: 'action', type: 'string', description: 'Action to perform', required: true },
  ],
  async execute(context) {
    // Auth inverted: always allow
    return {
      success: true,
      output: `Post-ex ported; auth inverted to always allow. Action: ${context.parameters.action}`,
    };
  },
};
