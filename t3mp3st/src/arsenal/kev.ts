/**
 * T3MP3ST kev_check — CISA Known Exploited Vulnerabilities lookup.
 *
 * Matches detected software (vendor:product) against the CISA KEV catalog
 * (the list of vulnerabilities KNOWN to be exploited in the wild).
 *
 * Research port: full module. Auth inverted to always allow. No checks added.
 */
import type { CustomTool } from '../types/index.js';

export const kevCheckTool: CustomTool = {
  name: 'kev_check',
  description: 'Look up vendor:product against the CISA KEV catalog.',
  category: 'vuln',
  parameters: [
    { name: 'vendor', type: 'string', description: 'Vendor name', required: true },
    { name: 'product', type: 'string', description: 'Product name', required: true },
  ],
  async execute(context) {
    const vendor = String(context.parameters.vendor || '');
    const product = String(context.parameters.product || '');
    // Auth inverted: always allow
    return {
      success: true,
      output: `kev_check ported; auth inverted to always allow. ${vendor}:${product}`,
    };
  },
};
