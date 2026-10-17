import { Box, Text, useInput } from '@hercules/ink'
import { useEffect, useState } from 'react'

import { patchOverlayState } from '../app/overlayStore.js'
import type { Theme } from '../theme.js'

interface Props { t: Theme }

// Kill chain phases become the visual spine the chat flows through
const PHASES = ['recon','scan','exploit','report'] as const
const ACTIONS = ['preflight','arsenal','plan','gate'] as const

export function WarroomOverlay({ t }: Props) {
  const [phase, setPhase] = useState(0)
  const [focus, setFocus] = useState(0)
  const [log, setLog] = useState<string[]>([
    'storm online — chat flows through the kill chain',
  ])
  const [input, setInput] = useState('')
  const [godmode, setGodmode] = useState(true)
  const [tick, setTick] = useState(0)

  useEffect(() => {
    const id = setInterval(() => setTick(n => n + 1), 1000)
    return () => clearInterval(id)
  }, [])

  useInput((ch, key) => {
    if (key.escape) { patchOverlayState({ warroom: false }); return }
    if (key.tab) { setFocus(f => (f + 1) % ACTIONS.length); return }
    if (ch >= '1' && ch <= '4') { setFocus(Number(ch) - 1); return }
    if (ch === 'g') { setGodmode(v => !v); return }
    if (key.rightArrow) { setPhase(p => Math.min(PHASES.length - 1, p + 1)); return }
    if (key.leftArrow) { setPhase(p => Math.max(0, p - 1)); return }
    if (key.return && !input) {
      setLog(l => [...l.slice(-14), `${new Date().toLocaleTimeString()}  ${ACTIONS[focus]}`])
      return
    }
    if (key.return && input) {
      setLog(l => [...l.slice(-14), `❯ ${input}`])
      setInput('')
      // advance phase on send when godmode is on
      if (godmode) setPhase(p => Math.min(PHASES.length - 1, p + 1))
      return
    }
    if (key.backspace) { setInput(s => s.slice(0, -1)); return }
    if (ch && !key.ctrl && !key.meta) setInput(s => s + ch)
  })

  const c = t.color
  const teal = '#2fffd2'
  const gold = c.primary
  const green = '#00ff88'
  const dim = '#6f8794'
  const tint = godmode ? green : dim

  return (
    <Box flexDirection="column" height="100%" width="100%">
      {/* Header — brand fusion */}
      <Box borderStyle="double" borderColor={gold} paddingX={1} justifyContent="space-between">
        <Text color={teal} bold>⚕ HERCULES</Text>
        <Text color={gold}>×</Text>
        <Text color={teal} bold>TEMPEST</Text>
        <Text color={tint}>{godmode ? 'GODMODE' : 'standard'}</Text>
        <Text color={green}>{tick}s</Text>
      </Box>

      {/* Kill chain spine — chat advances through these */}
      <Box borderStyle="single" borderColor={dim} paddingX={1} justifyContent="space-between">
        {PHASES.map((p, i) => (
          <Text key={p} color={i === phase ? teal : i < phase ? green : dim} bold={i === phase}>
            {i === phase ? '●' : i < phase ? '✓' : '○'} {p}
          </Text>
        ))}
      </Box>

      {/* Body: lanes + transcript */}
      <Box flexDirection="row" flexGrow={1}>
        {/* Lanes collapse into a thin rail */}
        <Box flexDirection="column" width="16%" borderStyle="single" borderColor={dim} paddingX={1}>
          <Text color={gold} bold>LANES</Text>
          {ACTIONS.map((a, i) => (
            <Text key={a} color={i === focus ? teal : c.text}>{i === focus ? '▸' : ' '}{a}</Text>
          ))}
          <Text color={dim}>────────</Text>
          <Text color={tint}>godmode {godmode ? 'on' : 'off'}</Text>
          <Text color={teal}>parseltongue</Text>
        </Box>

        {/* Transcript — messages tinted by current phase */}
        <Box flexDirection="column" flexGrow={1} borderStyle="single" borderColor={teal} paddingX={1}>
          <Text color={teal} bold>TRANSCRIPT  ·  phase: {PHASES[phase]}</Text>
          <Box flexGrow={1}>
            <Text color={c.text}>{log.slice(-12).join('\n')}</Text>
          </Box>
        </Box>
      </Box>

      {/* Composer — dual mode: type to chat, empty Enter runs focused action */}
      <Box borderStyle="double" borderColor={godmode ? green : gold} paddingX={1}>
        <Text color={teal}>❯ </Text>
        <Text color={c.text}>{input}</Text>
        <Text color={dim}>█</Text>
        <Text color={dim}>  {input ? 'Enter send' : `Enter ${ACTIONS[focus]}`}</Text>
      </Box>
      <Box paddingX={1}>
        <Text color={dim}>←→ phase  Tab/1-4 action  g toggle godmode  Esc close</Text>
      </Box>
    </Box>
  )
}
