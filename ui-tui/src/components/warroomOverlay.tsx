import { Box, Text, useInput } from '@hercules/ink'
import { useEffect, useState } from 'react'

import { patchOverlayState } from '../app/overlayStore.js'
import type { Theme } from '../theme.js'

interface Props { t: Theme }

// Actual Tempest pages from docs/index.html
const PAGES = [
  { key: '1', id: 'warroom', label: 'WAR ROOM' },
  { key: '2', id: 'live-scan', label: 'LIVE SCAN' },
  { key: '3', id: 'operators', label: 'OPERATORS' },
  { key: '4', id: 'arsenal', label: 'ARSENAL' },
  { key: '5', id: 'evidence', label: 'EVIDENCE' },
  { key: '6', id: 'general', label: 'ADMIRAL' },
  { key: '7', id: 'terminal', label: 'TERMINAL' },
  { key: '8', id: 'receipts', label: 'RECEIPTS' },
] as const

export function WarroomOverlay({ t }: Props) {
  const [page, setPage] = useState(0)
  const [log, setLog] = useState<string[]>(['STANDBY — awaiting orders'])
  const [input, setInput] = useState('')
  const [mission, setMission] = useState('STANDBY')
  const [status, setStatus] = useState('Awaiting orders')
  const [tick, setTick] = useState(0)

  useEffect(() => {
    const id = setInterval(() => setTick(n => n + 1), 1000)
    return () => clearInterval(id)
  }, [])

  useInput((ch, key) => {
    if (key.escape) { patchOverlayState({ warroom: false }); return }
    if (ch >= '1' && ch <= '8') { setPage(Number(ch) - 1); return }
    if (key.tab) { setPage(p => (p + 1) % PAGES.length); return }
    if (key.return && input) {
      const ts = new Date().toLocaleTimeString()
      setLog(l => [...l.slice(-20), `${ts}  ❯ ${input}`])
      if (page === 0 && mission === 'STANDBY') {
        setMission(input.slice(0, 24))
        setStatus('planning')
      }
      setInput('')
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
  const cur = PAGES[page]

  return (
    <Box flexDirection="column" height="100%" width="100%">
      {/* Persistent command header — from Tempest warroom */}
      <Box borderStyle="double" borderColor={gold} paddingX={1} justifyContent="space-between">
        <Box>
          <Text color={dim}>MISSION  </Text>
          <Text color={gold} bold>{mission}</Text>
        </Box>
        <Box>
          <Text color={dim}>STATUS  </Text>
          <Text color={status === 'planning' ? teal : dim}>{status}</Text>
        </Box>
        <Text color={green}>{tick}s</Text>
        <Text color={teal}>STORM</Text>
      </Box>

      {/* Page nav — actual Tempest pages */}
      <Box borderStyle="single" borderColor={dim} paddingX={1}>
        {PAGES.map((p, i) => (
          <Text key={p.id} color={i === page ? teal : dim} bold={i === page}>
            {i === page ? '▸' : ' '}{p.key} {p.label}  {' '}
          </Text>
        ))}
      </Box>

      {/* Page body */}
      <Box flexDirection="column" flexGrow={1} borderStyle="single" borderColor={teal} paddingX={1}>
        <Text color={teal} bold>{cur.label}</Text>
        <Box marginTop={1} flexGrow={1}>
          {cur.id === 'warroom' && (
            <Text color={c.text}>
              {log.slice(-10).join('\n') || 'Awaiting orders — point at a target and engage.'}
            </Text>
          )}
          {cur.id === 'live-scan' && (
            <Text color={c.text}>agent progress · task queue · reasoning feed{'\n'}(stream from /api/events)</Text>
          )}
          {cur.id === 'operators' && (
            <Text color={c.text}>roster · formation · swarm stats{'\n'}0 units active</Text>
          )}
          {cur.id === 'arsenal' && (
            <Text color={c.text}>nmap · ready{'\n'}nuclei · —{'\n'}semgrep · ready{'\n'}gitleaks · ready</Text>
          )}
          {cur.id === 'evidence' && (
            <Text color={c.text}>findings 0 · creds 0 · retests 0{'\n'}severity filters: ALL CRIT HIGH MED LOW</Text>
          )}
          {cur.id === 'general' && (
            <Text color={c.text}>Op Admiral{'\n'}directive: {input || '(type below)'}{'\n'}plan · sitreps · assessment</Text>
          )}
          {cur.id === 'terminal' && (
            <Text color={c.text}>{log.slice(-8).join('\n') || '— terminal —'}</Text>
          )}
          {cur.id === 'receipts' && (
            <Text color={c.text}>approval requests · 0 pending</Text>
          )}
        </Box>
      </Box>

      {/* Hercules composer — always present */}
      <Box borderStyle="double" borderColor={gold} paddingX={1}>
        <Text color={teal}>❯ </Text>
        <Text color={c.text}>{input}</Text>
        <Text color={dim}>█</Text>
      </Box>
      <Box paddingX={1}>
        <Text color={dim}>1-8 / Tab page · type + Enter · Esc close · godmode prefill active</Text>
      </Box>
    </Box>
  )
}
