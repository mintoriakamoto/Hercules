# Brand reference

This is our own visual identity. It replaces the branding inherited from the
upstream project, which had survived the earlier `Hermes → Hercules` rename in
name only.

## What was actually inherited

Three things still rendered the upstream identity at runtime, none of which a
text search for "Hermes" would ever have found:

| Surface | Inherited state | Why the rename missed it |
|---|---|---|
| CLI/TUI wordmark | Block art that **spelled `HERMES-AGENT`** | The art is block glyphs (`█ ╗ ╚`), not letters — grep can't read it. The variable was already renamed `HERCULES_AGENT_LOGO`, so it *looked* done. |
| Hero art | A winged **caduceus** | The caduceus is *Hermes'* staff. It was drawn in braille glyphs, so again invisible to search. |
| Emblem | **☤** (U+2624, caduceus) | A single character in the README title and 16 locale files. |

The palette (gold `#FFD700` → bronze `#CD7F32`) was likewise the upstream
project's colour, not a choice we had made.

## The identity

**Wordmark** — a solid, unshadowed block face reading `HERCULES`. Five rows and
64 columns, so it fits an 80-column terminal without wrapping (the old art was
six rows and 103 columns, and wrapped on standard terminals).

```
██   ██ ███████ ██████   ██████ ██    ██ ██      ███████ ███████
██   ██ ██      ██   ██ ██      ██    ██ ██      ██      ██
███████ █████   ██████  ██      ██    ██ ██      █████   ███████
██   ██ ██      ██   ██ ██      ██    ██ ██      ██           ██
██   ██ ███████ ██   ██  ██████  ██████  ███████ ███████ ███████
```

**Hero mark** — the Pillars of Hercules, the promontories he raised at the
strait. It reuses the same box-drawing and block glyphs as the wordmark, so it
renders anywhere the wordmark does.

```
   ╔═══════╗   ╔═══════╗
   ╚═╗███╔═╝   ╚═╗███╔═╝
     ║███║       ║███║
     ║███║       ║███║
     ║███║       ║███║
     ║███║       ║███║
   ╔═╝███╚═╗   ╔═╝███╚═╗
   ╚═══════╝   ╚═══════╝
```

**Emblem** — 🦁, the Nemean lion: Hercules' first labour, and the skin he wore
afterwards. Unambiguously his, and unambiguously not Hermes'.

## Palette — "Forge"

A heated-metal ramp, for a project named after strength and labour.

| Token | Hex | Role | Light-mode |
|---|---|---|---|
| Molten amber | `#F7B23B` | Primary accent — headers, highlights, titles | `#8A5300` |
| Ember orange | `#E8712E` | Secondary highlights | `#8A3A00` |
| Forge crimson | `#C73E3A` | Tertiary — borders, subtitle | `#8E1F1C` |
| Quenched iron | `#8E2B3F` | Muted text, deepest gradient stop | `#5C1622` |
| Cornsilk | `#FFF8DC` | Body text (unchanged) | `#1A1A1A` |

The banner gradient interpolates these horizontally with a small per-row phase
shift, so the wordmark reads as a diagonal shimmer rather than flat bands.

Every colour has a light-mode counterpart in `_LIGHT_MODE_REMAP` (`cli.py`).
**If you add a brand colour, add its light-mode value too** — otherwise it will
be unreadable on cream terminal backgrounds.

## Where it lives

| File | Contains |
|---|---|
| `hercules_cli/banner.py` | `HERCULES_AGENT_LOGO`, `HERCULES_AGENT_LOGO_RAW`, `HERCULES_PILLARS`, `_GRADIENT_ANCHORS` |
| `cli.py` | A second copy of the wordmark + pillars, the palette legend, and `_LIGHT_MODE_REMAP` |
| `ui-tui/src/banner.ts` | `LOGO_ART`, `PILLARS_ART` and their per-row gradient index arrays |
| `ui-tui/src/theme.ts` | `DEFAULT_THEME` / `LIGHT_THEME` colours |
| `website/src/css/custom.css` | Docs-site colours |

Two things to know when editing:

- **The wordmark and pillars are duplicated** in `banner.py` and `cli.py`, and
  again in the TUI's `banner.ts`. Change one, change all three.
- In `banner.ts` the gradient arrays hold **one index per art row**. Changing
  the number of rows without resizing `LOGO_GRADIENT` / `PILLARS_GRADIENT`
  silently falls back to the muted colour for the extra rows.

## Attribution

Hercules is an independent project derived from work by
[Nous Research](https://nousresearch.com) under the MIT licence. Rebranding the
visual identity does not remove that attribution — the notices in the README
translations and `LICENSE` are a licence obligation and must stay.
