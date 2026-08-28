import type { ThemeColors } from './theme.js'

const RICH_RE = /\[(?:bold\s+)?(?:dim\s+)?(#(?:[0-9a-fA-F]{3,8}))\]([\s\S]*?)(\[\/\])/g

export function parseRichMarkup(markup: string): Line[] {
  const lines: Line[] = []

  for (const raw of markup.split('\n')) {
    const trimmed = raw.trimEnd()

    if (!trimmed) {
      lines.push(['', ' '])

      continue
    }

    const matches = [...trimmed.matchAll(RICH_RE)]

    if (!matches.length) {
      lines.push(['', trimmed])

      continue
    }

    let cursor = 0

    for (const m of matches) {
      const before = trimmed.slice(cursor, m.index)

      if (before) {
        lines.push(['', before])
      }

      lines.push([m[1]!, m[2]!])
      cursor = m.index! + m[0].length
    }

    if (cursor < trimmed.length) {
      lines.push(['', trimmed.slice(cursor)])
    }
  }

  return lines
}

// Our own wordmark. The previous art was an inherited shadowed face that
// actually spelled "HERMES-AGENT"; this is a solid, unshadowed block face
// spelling HERCULES at 64 columns, so it fits an 80-column terminal.
const LOGO_ART = [
  '██   ██ ███████ ██████   ██████ ██    ██ ██      ███████ ███████',
  '██   ██ ██      ██   ██ ██      ██    ██ ██      ██      ██',
  '███████ █████   ██████  ██      ██    ██ ██      █████   ███████',
  '██   ██ ██      ██   ██ ██      ██    ██ ██      ██           ██',
  '██   ██ ███████ ██   ██  ██████  ██████  ███████ ███████ ███████'
]

// Hero mark: the Pillars of Hercules. Replaces the inherited winged-caduceus
// art — the caduceus is *Hermes'* staff, never our emblem.
const PILLARS_ART = [
  '   ╔═══════╗   ╔═══════╗',
  '   ╚═╗███╔═╝   ╚═╗███╔═╝',
  '     ║███║       ║███║',
  '     ║███║       ║███║',
  '     ║███║       ║███║',
  '     ║███║       ║███║',
  '   ╔═╝███╚═╗   ╔═╝███╚═╗',
  '   ╚═══════╝   ╚═══════╝'
]

// One gradient index per art row — keep these lengths in sync with the art.
const LOGO_GRADIENT = [0, 0, 1, 1, 2] as const
const PILLARS_GRADIENT = [0, 0, 1, 1, 1, 2, 2, 3] as const

const colorize = (art: string[], gradient: readonly number[], c: ThemeColors): Line[] => {
  const p = [c.primary, c.accent, c.border, c.muted]

  return art.map((text, i) => [p[gradient[i]!] ?? c.muted, text])
}

export const LOGO_WIDTH = Math.max(...LOGO_ART.map(line => line.length))
export const PILLARS_WIDTH = Math.max(...PILLARS_ART.map(line => line.length))

export const logo = (c: ThemeColors, customLogo?: string): Line[] =>
  customLogo ? parseRichMarkup(customLogo) : colorize(LOGO_ART, LOGO_GRADIENT, c)

export const pillars = (c: ThemeColors, customHero?: string): Line[] =>
  customHero ? parseRichMarkup(customHero) : colorize(PILLARS_ART, PILLARS_GRADIENT, c)

export const artWidth = (lines: Line[]) => lines.reduce((m, [, t]) => Math.max(m, t.length), 0)

type Line = [string, string]
