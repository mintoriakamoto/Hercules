import { Box, Text, useInput } from '@hercules/ink'
import { useState } from 'react'

import { patchOverlayState } from '../app/overlayStore.js'
import type { Theme } from '../theme.js'

interface Props {
  t: Theme
}

const PANES = ['STATUS', 'SITREP', 'ARSENAL', 'OUTPUT'] as const

export function WarroomOverlay({ t }: Props) {
  const [focus, setFocus] = useState(0)
  const [log, setLog] = useState<string[]>(['storm online — authorized targets only'])

  useInput((input, key) => {
    if (key.escape || input === 'q') {
      patchOverlayState({ warroom: false })
      return
    }
    if (key.tab) {
      setFocus(f => (f + 1) % PANES.length)
      return
    }
    if (input >= '1' && input <= '4') {
      setFocus(Number(input) - 1)
      return
    }
    if (key.return) {
      const action = ['preflight', 'arsenal', 'server', 'open'][focus]
      setLog(l => [...l.slice(-12), `${new Date().toLocaleTimeString()}  ${action}`])
    }
  })

  const c = t.color

  return (
    <Box flexDirection="column" height="100%" width="100%">
      <Box borderStyle="single" borderColor={c.border} paddingX={1}>
        <Text color={c.primary} bold>
          ⚕ WAR ROOM
        </Text>
        <Text color={c.muted}>  ·  storm  ·  authorized testing only</Text>
      </Box>

      <Box flexDirection="row" flexGrow={1}>
        {PANES.map((name, i) => (
          <Box
            key={name}
            flexDirection="column"
            flexGrow={1}
            borderStyle="single"
            borderColor={i === focus ? c.accent : c.border}
            paddingX={1}
            marginX={0}
          >
            <Text color={i === focus ? c.accent : c.muted} bold>
              {i + 1} {name} {i === focus ? '●' : '○'}
            </Text>
            <Box marginTop={1}>
              {name === 'STATUS' && (
                <Text color={c.text}>
                  home: ~/.hercules{'\n'}
                  port: 3333{'\n'}
                  focus: {PANES[focus].toLowerCase()}
                </Text>
              )}
              {name === 'SITREP' && (
                <Text color={c.text}>{log.slice(-6).join('\n') || '(quiet)'}</Text>
              )}
              {name === 'ARSENAL' && (
                <Text color={c.text}>
                  1 preflight{'\n'}
                  2 arsenal sync{'\n'}
                  3 server{'\n'}
                  4 open ui
                </Text>
              )}
              {name === 'OUTPUT' && (
                <Text color={c.muted}>{log.slice(-4).join('\n') || '—'}</Text>
              )}
            </Box>
          </Box>
        ))}
      </Box>

      <Box borderStyle="single" borderColor={c.border} paddingX={1}>
        <Text color={c.muted}>Tab / 1-4 focus · Enter act · q/Esc close</Text>
      </Box>
    </Box>
  )
}
