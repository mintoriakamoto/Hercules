import { Box, Text, useInput } from '@hercules/ink'
import { useEffect, useState } from 'react'

import { patchOverlayState } from '../app/overlayStore.js'
import type { Theme } from '../theme.js'

interface Props {
  t: Theme
}

const NAV = [
  { key: '1', label: 'STATUS', hint: 'system' },
  { key: '2', label: 'SITREP', hint: 'live feed' },
  { key: '3', label: 'ARSENAL', hint: 'tools' },
  { key: '4', label: 'MISSION', hint: 'plan' },
  { key: '5', label: 'EVIDENCE', hint: 'findings' },
  { key: '6', label: 'OUTPUT', hint: 'log' }
] as const

export function WarroomOverlay({ t }: Props) {
  const [focus, setFocus] = useState(0)
  const [log, setLog] = useState<string[]>([
    'storm online',
    'authorized targets only',
    'preflight pending'
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
    if (key.tab) {
      setFocus(f => (f + 1) % NAV.length)
      return
    }
    if (key.shift && key.tab) {
      setFocus(f => (f - 1 + NAV.length) % NAV.length)
      return
    }
    if (input >= '1' && input <= '6') {
      setFocus(Number(input) - 1)
      return
    }
    if (key.return) {
      const action = NAV[focus].label.toLowerCase()
      const ts = new Date().toLocaleTimeString()
      setLog(l => [...l.slice(-20), `${ts}  ${action}`])
    }
    if (input === 'r') {
      setLog(l => [...l, `${new Date().toLocaleTimeString()}  refresh`])
    }
  })

  const c = t.color
  const uptime = tick

  return (
    <Box flexDirection="column" height="100%" width="100%">
      {/* Header */}
      <Box borderStyle="double" borderColor={c.primary} paddingX={1} justifyContent="space-between">
        <Text color={c.primary} bold>
          ⚕  WAR ROOM
        </Text>
        <Text color={c.accent}>STORM</Text>
        <Text color={c.muted}>uptime {uptime}s</Text>
        <Text color={c.warn}>AUTHORIZED ONLY</Text>
      </Box>

      {/* Nav strip */}
      <Box borderStyle="single" borderColor={c.border} paddingX={1}>
        {NAV.map((n, i) => (
          <Text key={n.key} color={i === focus ? c.accent : c.muted} bold={i === focus}>
            {i === focus ? '▸' : ' '}{n.key} {n.label}{'  '}
          </Text>
        ))}
      </Box>

      {/* Main grid — 3 columns */}
      <Box flexDirection="row" flexGrow={1}>
        {/* Left: status + arsenal */}
        <Box flexDirection="column" width="30%" borderStyle="single" borderColor={focus < 2 ? c.accent : c.border}>
          <Box borderStyle="single" borderColor={c.border} paddingX={1}>
            <Text color={focus === 0 ? c.accent : c.muted} bold>1 STATUS {focus === 0 ? '●' : '○'}</Text>
          </Box>
          <Box paddingX={1} flexGrow={1}>
            <Text color={c.text}>
              home   ~/.hercules{'\n'}
              port   3333{'\n'}
              theme  storm{'\n'}
              focus  {NAV[focus].label.toLowerCase()}{'\n'}
              {'\n'}
              backend   ready{'\n'}
              agents    idle{'\n'}
              arsenal   partial
            </Text>
          </Box>
          <Box borderStyle="single" borderColor={c.border} paddingX={1}>
            <Text color={focus === 2 ? c.accent : c.muted} bold>3 ARSENAL {focus === 2 ? '●' : '○'}</Text>
          </Box>
          <Box paddingX={1}>
            <Text color={c.text}>
              nmap      ready{'\n'}
              nuclei    missing{'\n'}
              semgrep   ready{'\n'}
              gitleaks  ready
            </Text>
          </Box>
        </Box>

        {/* Center: sitrep + mission */}
        <Box flexDirection="column" width="40%" borderStyle="single" borderColor={focus === 1 || focus === 3 ? c.accent : c.border}>
          <Box borderStyle="single" borderColor={c.border} paddingX={1}>
            <Text color={focus === 1 ? c.accent : c.muted} bold>2 SITREP {focus === 1 ? '●' : '○'}</Text>
          </Box>
          <Box paddingX={1} flexGrow={1}>
            <Text color={c.text}>
              {log.slice(-8).map(l => l).join('\n') || '(quiet)'}
            </Text>
          </Box>
          <Box borderStyle="single" borderColor={c.border} paddingX={1}>
            <Text color={focus === 3 ? c.accent : c.muted} bold>4 MISSION {focus === 3 ? '●' : '○'}</Text>
          </Box>
          <Box paddingX={1}>
            <Text color={c.text}>
              state    idle{'\n'}
              gate     —{'\n'}
              target   none{'\n'}
              opsec    covert
            </Text>
          </Box>
        </Box>

        {/* Right: evidence + output */}
        <Box flexDirection="column" width="30%" borderStyle="single" borderColor={focus >= 4 ? c.accent : c.border}>
          <Box borderStyle="single" borderColor={c.border} paddingX={1}>
            <Text color={focus === 4 ? c.accent : c.muted} bold>5 EVIDENCE {focus === 4 ? '●' : '○'}</Text>
          </Box>
          <Box paddingX={1} flexGrow={1}>
            <Text color={c.text}>
              findings   0{'\n'}
              creds      0{'\n'}
              retests    0{'\n'}
              receipts   0
            </Text>
          </Box>
          <Box borderStyle="single" borderColor={c.border} paddingX={1}>
            <Text color={focus === 5 ? c.accent : c.muted} bold>6 OUTPUT {focus === 5 ? '●' : '○'}</Text>
          </Box>
          <Box paddingX={1}>
            <Text color={c.muted}>{log.slice(-4).join('\n') || '—'}</Text>
          </Box>
        </Box>
      </Box>

      {/* Footer */}
      <Box borderStyle="double" borderColor={c.primary} paddingX={1} justifyContent="space-between">
        <Text color={c.muted}>Tab / 1-6 focus</Text>
        <Text color={c.muted}>Enter act</Text>
        <Text color={c.muted}>r refresh</Text>
        <Text color={c.muted}>q / Esc close</Text>
      </Box>
    </Box>
  )
}
