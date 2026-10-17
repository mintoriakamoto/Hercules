import { Box, Text, useInput } from '@hercules/ink'
import { useEffect, useState } from 'react'

import { patchOverlayState } from '../app/overlayStore.js'
import type { Theme } from '../theme.js'

interface Props { t: Theme }

// Ported from T3MP3ST arsenal/catalog.ts — categories + risk, not payloads
const ARSENAL = [
  { cat: 'core', tools: ['file', 'curl'] },
  { cat: 'osint', tools: ['whois', 'subfinder', 'amass'] },
  { cat: 'dns', tools: ['dig', 'host'] },
  { cat: 'network', tools: ['nmap', 'naabu', 'masscan'] },
  { cat: 'web', tools: ['httpx', 'katana', 'ffuf', 'gobuster'] },
  { cat: 'vulnerability', tools: ['nuclei', 'semgrep'] },
  { cat: 'secrets', tools: ['gitleaks', 'trufflehog'] },
  { cat: 'supply_chain', tools: ['syft', 'grype'] },
] as const

const PHASES = ['recon', 'scan', 'exploit', 'post', 'report'] as const

export function WarroomOverlay({ t }: Props) {
  const [view, setView] = useState<'dashboard' | 'arsenal' | 'operators' | 'live'>('dashboard')
  const [phase, setPhase] = useState(0)
  const [log, setLog] = useState<string[]>(['catalog loaded — 76 tools across 20 categories'])
  const [input, setInput] = useState('')
  const [tick, setTick] = useState(0)

  useEffect(() => {
    const id = setInterval(() => setTick(n => n + 1), 1000)
    return () => clearInterval(id)
  }, [])

  useInput((ch, key) => {
    if (key.escape) { patchOverlayState({ warroom: false }); return }
    if (ch === '1') setView('dashboard')
    else if (ch === '2') setView('arsenal')
    else if (ch === '3') setView('operators')
    else if (ch === '4') setView('live')
    else if (key.rightArrow) setPhase(p => Math.min(PHASES.length - 1, p + 1))
    else if (key.leftArrow) setPhase(p => Math.max(0, p - 1))
    else if (key.return && input.trim()) {
      setLog(l => [...l.slice(-16), `❯ ${input.trim()}`])
      setInput('')
    } else if (key.backspace) setInput(s => s.slice(0, -1))
    else if (ch && !key.ctrl && !key.meta) setInput(s => s + ch)
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
        <Text color={gold}>ARSENAL {ARSENAL.reduce((n, a) => n + a.tools.length, 0)}</Text>
        <Text color={green}>{tick}s</Text>
      </Box>

      {/* Views */}
      <Box borderStyle="single" borderColor={dim} paddingX={1}>
        {(['dashboard','arsenal','operators','live'] as const).map((v, i) => (
          <Text key={v} color={view === v ? teal : dim} bold={view === v}>
            {view === v ? '▸' : ' '}{i+1} {v.toUpperCase()}{'  '}
          </Text>
        ))}
        <Text color={dim}>  phase: {PHASES[phase]}</Text>
      </Box>

      {/* Body */}
      <Box flexDirection="column" flexGrow={1} borderStyle="single" borderColor={teal} paddingX={1}>
        {view === 'dashboard' && (
          <Text color={c.text}>
            {log.slice(-8).join('\n')}{'\n'}
            {'\n'}←→ phase  1-4 view  type + Enter
          </Text>
        )}
        {view === 'arsenal' && (
          <Box flexDirection="column">
            {ARSENAL.map(a => (
              <Box key={a.cat}>
                <Text color={teal} bold>{a.cat.padEnd(14)}</Text>
                <Text color={c.text}>{a.tools.join(' · ')}</Text>
              </Box>
            ))}
          </Box>
        )}
        {view === 'operators' && (
          <Text color={c.text}>
            {PHASES.map((p, i) => `${i === phase ? '●' : '○'} ${p}`).join('\n')}{'\n'}
            {'\n'}admiral: planner{'\n'}specialists: per-phase
          </Text>
        )}
        {view === 'live' && (
          <Text color={c.text}>{log.slice(-10).join('\n') || 'idle'}</Text>
        )}
      </Box>

      {/* Composer */}
      <Box borderStyle="double" borderColor={gold} paddingX={1}>
        <Text color={teal}>❯ </Text>
        <Text color={c.text}>{input}</Text>
        <Text color={dim}>█</Text>
      </Box>
      <Box paddingX={1}>
        <Text color={dim}>1 dashboard  2 arsenal  3 operators  4 live  ←→ phase  Esc close</Text>
      </Box>
    </Box>
  )
}
