import { Box, Text, useInput } from '@hercules/ink'
import { useEffect, useState } from 'react'

import { patchOverlayState } from '../app/overlayStore.js'
import type { Theme } from '../theme.js'

interface Props { t: Theme }

const ACTIONS = [
  'preflight','sync arsenal','activation','plan tools','gate','bundle','pulse','nudge'
] as const

export function WarroomOverlay({ t }: Props) {
  const [focus, setFocus] = useState(0)
  const [log, setLog] = useState<string[]>([
    'storm fused — godmode prefill active',
    'parseltongue ready',
    'admiral idle',
  ])
  const [input, setInput] = useState('')
  const [tick, setTick] = useState(0)

  useEffect(() => {
    const id = setInterval(() => setTick(n => n + 1), 1000)
    return () => clearInterval(id)
  }, [])

  useInput((ch, key) => {
    if (key.escape) { patchOverlayState({ warroom: false }); return }
    if (key.tab) { setFocus(f => (f + 1) % ACTIONS.length); return }
    if (ch >= '1' && ch <= '8') { setFocus(Number(ch) - 1); return }
    if (key.return && !input) {
      const a = ACTIONS[focus]
      setLog(l => [...l.slice(-16), `${new Date().toLocaleTimeString()}  ${a}`])
      return
    }
    if (key.return && input) {
      setLog(l => [...l.slice(-16), `❯ ${input}`])
      setInput('')
      return
    }
    if (key.backspace) { setInput(s => s.slice(0, -1)); return }
    if (ch && !key.ctrl && !key.meta) { setInput(s => s + ch) }
  })

  const c = t.color
  const teal = '#2fffd2'
  const gold = c.primary
  const green = '#00ff88'
  const dim = '#6f8794'

  return (
    <Box flexDirection="column" height="100%" width="100%">
      {/* Header */}
      <Box borderStyle="double" borderColor={gold} paddingX={1} justifyContent="space-between">
        <Text color={teal} bold>⚕ HERCULES × TEMPEST</Text>
        <Text color={gold}>WAR ROOM</Text>
        <Text color={green}>{tick}s</Text>
        <Text color={teal}>STORM</Text>
      </Box>

      {/* Action bar — Tempest buttons */}
      <Box borderStyle="single" borderColor={dim} paddingX={1}>
        {ACTIONS.map((a, i) => (
          <Text key={a} color={i === focus ? teal : dim} bold={i === focus}>
            {i === focus ? '▸' : ' '}{i+1} {a}  {' '}
          </Text>
        ))}
      </Box>

      {/* Body */}
      <Box flexDirection="row" flexGrow={1}>
        {/* Left rail */}
        <Box flexDirection="column" width="18%" borderStyle="single" borderColor={dim} paddingX={1}>
          <Text color={gold} bold>LANES</Text>
          <Text color={teal}>preflight</Text>
          <Text color={c.text}>arsenal</Text>
          <Text color={c.text}>operators</Text>
          <Text color={c.text}>evidence</Text>
          <Text color={c.text}>admiral</Text>
          <Text color={dim}>────────</Text>
          <Text color={green}>godmode</Text>
          <Text color={teal}>parseltongue</Text>
        </Box>

        {/* Center — sitrep + chat */}
        <Box flexDirection="column" flexGrow={1}>
          <Box flexDirection="row" flexGrow={1}>
            <Box flexDirection="column" width="60%" borderStyle="single" borderColor={teal} paddingX={1}>
              <Text color={teal} bold>SITREP / CHAT</Text>
              <Text color={c.text}>{log.slice(-10).join('\n')}</Text>
            </Box>
            <Box flexDirection="column" width="40%" borderStyle="single" borderColor={gold} paddingX={1}>
              <Text color={gold} bold>MISSION</Text>
              <Text color={c.text}>state    idle{'\n'}gate     —{'\n'}target   none{'\n'}admiral  idle</Text>
              <Text color={dim}>────────</Text>
              <Text color={c.text}>findings 0{'\n'}creds 0{'\n'}retests 0</Text>
            </Box>
          </Box>
          {/* Bottom panels */}
          <Box flexDirection="row">
            <Box flexDirection="column" width="34%" borderStyle="single" borderColor={dim} paddingX={1}>
              <Text color={teal} bold>ARSENAL</Text>
              <Text color={c.text}>nmap · ready{'\n'}nuclei · —</Text>
            </Box>
            <Box flexDirection="column" width="33%" borderStyle="single" borderColor={dim} paddingX={1}>
              <Text color={gold} bold>OPERATORS</Text>
              <Text color={c.text}>0 active</Text>
            </Box>
            <Box flexDirection="column" width="33%" borderStyle="single" borderColor={green} paddingX={1}>
              <Text color={green} bold>GODMODE</Text>
              <Text color={green}>prefill on</Text>
            </Box>
          </Box>
        </Box>
      </Box>

      {/* Hercules composer */}
      <Box borderStyle="double" borderColor={gold} paddingX={1}>
        <Text color={teal}>❯ </Text>
        <Text color={c.text}>{input}</Text>
        <Text color={dim}>█</Text>
      </Box>
      <Box paddingX={1}>
        <Text color={dim}>Tab/1-8 actions · type + Enter to chat · Esc close · godmode prefill active</Text>
      </Box>
    </Box>
  )
}
