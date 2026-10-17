import { Box, Text, useInput } from '@hercules/ink'
import { useEffect, useState } from 'react'

import { patchOverlayState } from '../app/overlayStore.js'
import type { Theme } from '../theme.js'

interface Props { t: Theme }

const NAV = [
  { key: '1', label: 'STATUS' },
  { key: '2', label: 'SITREP' },
  { key: '3', label: 'ARSENAL' },
  { key: '4', label: 'MISSION' },
  { key: '5', label: 'EVIDENCE' },
  { key: '6', label: 'OUTPUT' },
  { key: '7', label: 'GODMODE' },
] as const

export function WarroomOverlay({ t }: Props) {
  const [focus, setFocus] = useState(0)
  const [log, setLog] = useState<string[]>([
    'storm online',
    'godmode prefill loaded',
    'parseltongue ready',
  ])
  const [tick, setTick] = useState(0)

  useEffect(() => {
    const id = setInterval(() => setTick(n => n + 1), 1000)
    return () => clearInterval(id)
  }, [])

  useInput((input, key) => {
    if (key.escape || input === 'q') {
      patchOverlayState({ warroom: false })
      return
    }
    if (key.tab) { setFocus(f => (f + 1) % NAV.length); return }
    if (input >= '1' && input <= '7') { setFocus(Number(input) - 1); return }
    if (key.return) {
      const ts = new Date().toLocaleTimeString()
      setLog(l => [...l.slice(-24), `${ts}  ${NAV[focus].label.toLowerCase()}`])
    }
  })

  const c = t.color

  return (
    <Box flexDirection="column" height="100%" width="100%">
      {/* Header */}
      <Box borderStyle="double" borderColor={c.primary} paddingX={1} justifyContent="space-between">
        <Text color={c.primary} bold>⚕ WAR ROOM</Text>
        <Text color={c.accent}>STORM</Text>
        <Text color={c.muted}>{tick}s</Text>
        <Text color={c.ok}>GODMODE</Text>
      </Box>

      {/* Nav */}
      <Box borderStyle="single" borderColor={c.border} paddingX={1}>
        {NAV.map((n, i) => (
          <Text key={n.key} color={i === focus ? c.accent : c.muted} bold={i === focus}>
            {i === focus ? '▸' : ' '}{n.key} {n.label}  {' '}
          </Text>
        ))}
      </Box>

      {/* Body: sidebar + main */}
      <Box flexDirection="row" flexGrow={1}>
        {/* Sidebar */}
        <Box flexDirection="column" width="22%" borderStyle="single" borderColor={c.border} paddingX={1}>
          <Text color={c.primary} bold>NAV</Text>
          <Text color={c.text}>preflight</Text>
          <Text color={c.text}>arsenal</Text>
          <Text color={c.text}>operators</Text>
          <Text color={c.text}>evidence</Text>
          <Text color={c.text}>terminal</Text>
          <Text color={c.muted}>────────</Text>
          <Text color={c.ok}>godmode on</Text>
          <Text color={c.muted}>parseltongue</Text>
          <Text color={c.muted}>ultraplinian</Text>
        </Box>

        {/* Main grid */}
        <Box flexDirection="column" flexGrow={1}>
          <Box flexDirection="row" flexGrow={1}>
            <Box flexDirection="column" width="50%" borderStyle="single" borderColor={focus === 1 ? c.accent : c.border} paddingX={1}>
              <Text color={focus === 1 ? c.accent : c.muted} bold>2 SITREP {focus === 1 ? '●' : '○'}</Text>
              <Text color={c.text}>{log.slice(-10).join('\n')}</Text>
            </Box>
            <Box flexDirection="column" width="50%" borderStyle="single" borderColor={focus === 3 ? c.accent : c.border} paddingX={1}>
              <Text color={focus === 3 ? c.accent : c.muted} bold>4 MISSION {focus === 3 ? '●' : '○'}</Text>
              <Text color={c.text}>state   idle{'\n'}gate    —{'\n'}target  none{'\n'}opsec   —</Text>
            </Box>
          </Box>
          <Box flexDirection="row">
            <Box flexDirection="column" width="33%" borderStyle="single" borderColor={focus === 2 ? c.accent : c.border} paddingX={1}>
              <Text color={focus === 2 ? c.accent : c.muted} bold>3 ARSENAL</Text>
              <Text color={c.text}>nmap ready{'\n'}nuclei —{'\n'}semgrep ready</Text>
            </Box>
            <Box flexDirection="column" width="33%" borderStyle="single" borderColor={focus === 4 ? c.accent : c.border} paddingX={1}>
              <Text color={focus === 4 ? c.accent : c.muted} bold>5 EVIDENCE</Text>
              <Text color={c.text}>findings 0{'\n'}creds 0</Text>
            </Box>
            <Box flexDirection="column" width="34%" borderStyle="single" borderColor={focus === 6 ? c.accent : c.border} paddingX={1}>
              <Text color={focus === 6 ? c.accent : c.muted} bold>7 GODMODE</Text>
              <Text color={c.ok}>prefill loaded{'\n'}parseltongue on</Text>
            </Box>
          </Box>
        </Box>
      </Box>

      {/* Footer */}
      <Box borderStyle="double" borderColor={c.primary} paddingX={1} justifyContent="space-between">
        <Text color={c.muted}>Tab/1-7 focus</Text>
        <Text color={c.muted}>Enter act</Text>
        <Text color={c.muted}>q/Esc close</Text>
        <Text color={c.muted}>godmode prefill active</Text>
      </Box>
    </Box>
  )
}
