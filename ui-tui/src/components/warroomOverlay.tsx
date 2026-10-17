import { Box, Text, useInput } from '@hercules/ink'
import { useEffect, useState } from 'react'

import { patchOverlayState } from '../app/overlayStore.js'
import type { Theme } from '../theme.js'

interface Props { t: Theme }

const NAV = ['STATUS','SITREP','ARSENAL','MISSION','EVIDENCE','GODMODE','ADMIRAL'] as const

export function WarroomOverlay({ t }: Props) {
  const [focus, setFocus] = useState(0)
  const [log, setLog] = useState<string[]>([
    'storm fused',
    'godmode prefill active',
    'parseltongue ready',
    'admiral idle',
  ])
  const [tick, setTick] = useState(0)

  useEffect(() => {
    const id = setInterval(() => setTick(n => n + 1), 1000)
    return () => clearInterval(id)
  }, [])

  useInput((input, key) => {
    if (key.escape || input === 'q') { patchOverlayState({ warroom: false }); return }
    if (key.tab) { setFocus(f => (f + 1) % NAV.length); return }
    if (input >= '1' && input <= '7') { setFocus(Number(input) - 1); return }
    if (key.return) {
      setLog(l => [...l.slice(-20), `${new Date().toLocaleTimeString()}  ${NAV[focus].toLowerCase()}`])
    }
  })

  const c = t.color
  // Fusion palette: Tempest teal + Hercules gold
  const teal = '#2fffd2'
  const gold = c.primary
  const green = '#00ff88'
  const dim = '#6f8794'

  return (
    <Box flexDirection="column" height="100%" width="100%">
      {/* Top bar — gold rule, teal brand */}
      <Box borderStyle="double" borderColor={gold} paddingX={1} justifyContent="space-between">
        <Text color={teal} bold>⚕ HERCULES × TEMPEST</Text>
        <Text color={gold}>WAR ROOM</Text>
        <Text color={green}>{tick}s</Text>
        <Text color={teal}>STORM</Text>
      </Box>

      {/* Nav rail */}
      <Box borderStyle="single" borderColor={dim} paddingX={1}>
        {NAV.map((n, i) => (
          <Text key={n} color={i === focus ? teal : dim} bold={i === focus}>
            {i === focus ? '▸' : '·'}{i+1} {n}  {' '}
          </Text>
        ))}
      </Box>

      {/* Body */}
      <Box flexDirection="row" flexGrow={1}>
        {/* Left rail */}
        <Box flexDirection="column" width="20%" borderStyle="single" borderColor={dim} paddingX={1}>
          <Text color={gold} bold>LANES</Text>
          <Text color={teal}>preflight</Text>
          <Text color={c.text}>arsenal</Text>
          <Text color={c.text}>operators</Text>
          <Text color={c.text}>evidence</Text>
          <Text color={c.text}>admiral</Text>
          <Text color={dim}>────────</Text>
          <Text color={green}>godmode</Text>
          <Text color={teal}>parseltongue</Text>
          <Text color={gold}>ultraplinian</Text>
        </Box>

        {/* Center — sitrep + mission */}
        <Box flexDirection="column" flexGrow={1}>
          <Box flexDirection="row" flexGrow={1}>
            <Box flexDirection="column" width="55%" borderStyle="single" borderColor={focus === 1 ? teal : dim} paddingX={1}>
              <Text color={focus === 1 ? teal : dim} bold>SITREP {focus === 1 ? '●' : '○'}</Text>
              <Text color={c.text}>{log.slice(-12).join('\n')}</Text>
            </Box>
            <Box flexDirection="column" width="45%" borderStyle="single" borderColor={focus === 3 ? gold : dim} paddingX={1}>
              <Text color={focus === 3 ? gold : dim} bold>MISSION {focus === 3 ? '●' : '○'}</Text>
              <Text color={c.text}>state    idle{'\n'}gate     —{'\n'}target   none{'\n'}opsec    —{'\n'}admiral  idle</Text>
            </Box>
          </Box>
          {/* Bottom strip */}
          <Box flexDirection="row">
            <Box flexDirection="column" width="34%" borderStyle="single" borderColor={focus === 2 ? teal : dim} paddingX={1}>
              <Text color={focus === 2 ? teal : dim} bold>ARSENAL</Text>
              <Text color={c.text}>nmap · ready{'\n'}nuclei · —{'\n'}semgrep · ready</Text>
            </Box>
            <Box flexDirection="column" width="33%" borderStyle="single" borderColor={focus === 4 ? gold : dim} paddingX={1}>
              <Text color={focus === 4 ? gold : dim} bold>EVIDENCE</Text>
              <Text color={c.text}>findings 0{'\n'}creds 0{'\n'}retests 0</Text>
            </Box>
            <Box flexDirection="column" width="33%" borderStyle="single" borderColor={focus === 5 ? green : dim} paddingX={1}>
              <Text color={focus === 5 ? green : dim} bold>GODMODE</Text>
              <Text color={green}>prefill on{'\n'}parseltongue</Text>
            </Box>
          </Box>
        </Box>
      </Box>

      {/* Footer */}
      <Box borderStyle="double" borderColor={gold} paddingX={1} justifyContent="space-between">
        <Text color={dim}>Tab / 1-7</Text>
        <Text color={teal}>Enter act</Text>
        <Text color={gold}>q / Esc</Text>
        <Text color={green}>godmode + parseltongue</Text>
      </Box>
    </Box>
  )
}
