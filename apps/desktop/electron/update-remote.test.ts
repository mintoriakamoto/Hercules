import assert from 'node:assert/strict'
import test from 'node:test'

import {
  canonicalGitHubRemote,
  isOfficialSshRemote,
  isSshRemote,
  OFFICIAL_REPO_CANONICAL,
  OFFICIAL_REPO_HTTPS_URL
} from './update-remote'

test('canonicalGitHubRemote normalizes SSH and HTTPS forms to the same value', () => {
  assert.equal(canonicalGitHubRemote('git@github.com:mintoriakamoto/Hercules.git'), OFFICIAL_REPO_CANONICAL)
  assert.equal(canonicalGitHubRemote('git@github.com:mintoriakamoto/Hercules'), OFFICIAL_REPO_CANONICAL)
  assert.equal(canonicalGitHubRemote('ssh://git@github.com/mintoriakamoto/Hercules.git'), OFFICIAL_REPO_CANONICAL)
  assert.equal(canonicalGitHubRemote('https://github.com/mintoriakamoto/Hercules.git'), OFFICIAL_REPO_CANONICAL)
  assert.equal(canonicalGitHubRemote('git@github.com:MintoriAkamoto/hercules.git'), OFFICIAL_REPO_CANONICAL)
  assert.equal(canonicalGitHubRemote('https://github.com/mintoriakamoto/Hercules/'), OFFICIAL_REPO_CANONICAL)
})

test('canonicalGitHubRemote is empty for falsy input', () => {
  assert.equal(canonicalGitHubRemote(''), '')
  assert.equal(canonicalGitHubRemote(null), '')
  assert.equal(canonicalGitHubRemote(undefined), '')
})

test('isSshRemote detects scp-like and ssh:// forms only', () => {
  assert.equal(isSshRemote('git@github.com:mintoriakamoto/Hercules.git'), true)
  assert.equal(isSshRemote('ssh://git@github.com/mintoriakamoto/Hercules.git'), true)
  assert.equal(isSshRemote('https://github.com/mintoriakamoto/Hercules.git'), false)
  assert.equal(isSshRemote(''), false)
  assert.equal(isSshRemote(null), false)
})

test('isOfficialSshRemote is true only for the official repo over SSH', () => {
  assert.equal(isOfficialSshRemote('git@github.com:mintoriakamoto/Hercules.git'), true)
  assert.equal(isOfficialSshRemote('git@github.com:mintoriakamoto/Hercules'), true)
  assert.equal(isOfficialSshRemote('ssh://git@github.com/mintoriakamoto/Hercules.git'), true)
  assert.equal(isOfficialSshRemote('git@github.com:MintoriAkamoto/hercules.git'), true)
})

test('isOfficialSshRemote does NOT match forks, other hosts, or HTTPS', () => {
  assert.equal(isOfficialSshRemote('git@github.com:someuser/hercules-agent.git'), false)
  assert.equal(isOfficialSshRemote('git@github.com:NousResearch/hercules-agent.git'), false)
  assert.equal(isOfficialSshRemote('git@gitlab.com:mintoriakamoto/Hercules.git'), false)
  assert.equal(isOfficialSshRemote('https://github.com/mintoriakamoto/Hercules.git'), false)
  assert.equal(isOfficialSshRemote(''), false)
  assert.equal(isOfficialSshRemote(null), false)
})

test('OFFICIAL_REPO_HTTPS_URL canonicalizes to OFFICIAL_REPO_CANONICAL', () => {
  assert.equal(canonicalGitHubRemote(OFFICIAL_REPO_HTTPS_URL), OFFICIAL_REPO_CANONICAL)
})
