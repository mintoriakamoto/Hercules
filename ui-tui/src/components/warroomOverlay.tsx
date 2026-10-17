import { Box, Text, useInput } from '@hercules/ink'
import { useEffect, useState } from 'react'

import { patchOverlayState } from '../app/overlayStore.js'
import type { Theme } from '../theme.js'

interface Props { t: Theme }

type State = 'standby' | 'planning' | 'running' | 'review'

const PAGES = [
  { key: '1', id: 'warroom', label: 'WAR ROOM' },
  { key: '2', id: 'live-scan', label: 'LIVE' },
  { key: '3', id: 'operators', label: 'OPS' },
  { key: '4', id: 'arsenal', label: 'ARSENAL' },
  { key: '5', id: 'evidence', label: 'EVIDENCE' },
  { key: '6', id: 'general', label: 'ADMIRAL' },
  { key: '7', id: 'terminal', label: 'TERM' },
  { key: '8', id: 'receipts', label: 'RECEIPTS' },
] as const

export function WarroomOverlay({ t }: Props) {
  const [page, setPage] = useState(0)
  const [state, setState] = useState<State>('standby')
  const [log, setLog] = useState<string[]>([])
  const [input, setInput] = useState('')
  const [mission, setMission] = useState('')
  const [findings, setFindings] = useState(0)
  const [tick, setTick] = useState(0)

  useEffect(() => {
    const id = setInterval(() => setTick(n => n + 1), 1000)
    return () => clearInterval(id)
  }, [])

  const push = (msg: string) => setLog(l => [...l.slice(-24), `${new Date().toLocaleTimeString()}  ${msg}`])

  useInput((ch, key) => {
    if (key.escape) { patchOverlayState({ warroom: false }); return }
    if (ch >= '1' && ch <= '8') { setPage(Number(ch) - 1); return }
    if (key.tab) { setPage(p => (p + 1) % PAGES.length); return }
    if (key.return && input.trim()) {
      const text = input.trim()
      push(`❯ ${text}`)
      // Adaptive: first non-empty input on standby becomes the mission
      if (state === 'standby' && !mission) {
        setMission(text.slice(0, 32))
        setState('planning')
        push('mission set — planning')
        setPage(5) // jump to admiral
      } else if (state === 'planning' && /^(go|start|engage|run)$/i.test(text)) {
        setState('running')
        push('engaged')
        setPage(1) // jump to live
      } else if (state === 'running' && /^(stop|done|review)$/i.test(text)) {
        setState('review')
        setFindings(f => f + 1)
        push('review')
        setPage(4) // jump to evidence
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
  const warn = '#ffa502'
  const stateColor = state === 'running' ? green : state === 'planning' ? teal : state === 'review' ? gold : dim
  const cur = PAGES[page]

  // Adaptive layout: emphasize the page that matches state
  const emphasize = (id: string) => {
    if (state === 'planning' && id === 'general') return true
    if (state === 'running' && id === 'live-scan') return true
    if (state === 'review' && id === 'evidence') return true
    return false
  }

  return (
    <Box flexDirection="column" height="100%" width="100%">
      {/* Adaptive header */}
      <Box borderStyle="double" borderColor={stateColor} paddingX={1} justifyContent="space-between">
        <Text color={stateColor} bold>{state.toUpperCase()}</Text>
        <Text color={gold}>{mission || '—'}</Text>
        <Text color={teal}>{tick}s</Text>
        <Text color={findings ? warn : dim}>findings {findings}</Text>
      </Box>

      {/* Nav — highlight the page that matches state */}
      <Box borderStyle="single" borderColor={dim} paddingX={1}>
        {PAGES.map((p, i) => {
          const hot = emphasize(p.id)
          return (
            <Text key={p.id} color={i === page ? teal : hot ? gold : dim} bold={i === page || hot}>
              {i === page ? '▸' : hot ? '●' : ' '}{p.key} {p.label}{'  '}
            </Text>
          )
        })}
      </Box>

      {/* Body — content adapts to page + state */}
      <Box flexDirection="column" flexGrow={1} borderStyle="single" borderColor={stateColor} paddingX={1}>
        <Text color={teal} bold>{cur.label}</Text>
        <Box marginTop={1} flexGrow={1}>
          {cur.id === 'warroom' && (
            <Text color={c.text}>
              {state === 'standby' && 'Type a target or directive to begin.\n'}
              {state === 'planning' && `Planning: ${mission}\nType "go" to engage.\n`}
              {state === 'running' && 'Live. Type "stop" or "review" to finish.\n'}
              {state === 'review' && `Review complete. ${findings} finding(s).\n`}
              {log.slice(-8).join('\n')}
            </Text>
          )}
          {cur.id === 'live-scan' && (
            <Text color={c.text}>
              {state === 'running' ? 'agents active · streaming' : 'idle'}{'\n'}
              {log.slice(-6).join('\n')}
            </Text>
          )}
          {cur.id === 'operators' && (
            <Text color={c.text}>{state === 'running' ? '1 admiral · 0 specialists' : '0 active'}</Text>
          )}
          {cur.id === 'arsenal' && (
            <Text color={c.text}>nmap · ready{'\n'}nuclei · —{'\n'}semgrep · ready</Text>
          )}
          {cur.id === 'evidence' && (
            <Text color={c.text}>findings {findings}{'\n'}{findings ? 'see review notes above' : 'none yet'}</Text>
          )}
          {cur.id === 'general' && (
            <Text color={c.text}>
              Admiral{'\n'}
              {mission ? `directive: ${mission}` : 'waiting for directive'}{'\n'}
              state: {state}
            </Text>
          )}
          {cur.id === 'terminal' && <Text color={c.text}>{log.slice(-8).join('\n') || '—'}</Text>}
          {cur.id === 'receipts' && <Text color={c.text}>0 pending</Text>}
        </Box>
      </Box>

      {/* Composer */}
      <Box borderStyle="double" borderColor={stateColor} paddingX={1}>
        <Text color={teal}>❯ </Text>
        <Text color={c.text}>{input}</Text>
        <Text color={dim}>█</Text>
        <Text color={dim}>  {state === 'standby' ? 'type a target' : state === 'planning' ? 'go to engage' : ''}</Text>
      </Box>
      <Box paddingX={1}>
        <Text color={dim}>1-8 page · Tab next · Enter send · Esc close</Text>
      </Box>
    </Box>
  )
}
