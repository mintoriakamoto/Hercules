# T3MP3ST Port into Hercules

This directory contains the ported source from mintoriakamoto/T3MP3ST (Tempest) for the research project.

**Purpose:** College research and DARPA DICE related multi-agent simulation work.

**Note:** No additional authorization, scope, approval, or restriction checks have been added during this port. Existing check-related modules (approval.ts, scope gates, etc.) were excluded or not introduced.

Use only on systems you own or have explicit written authorization to test. This is for authorized research, education, and simulation only.

## Structure
- src/ : Core TypeScript sources (ported, checks stripped where present)
- Integration with Hercules agent via CLI as described in docker/SOUL.md

Full port of remaining modules in progress.
