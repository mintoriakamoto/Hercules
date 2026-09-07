---
name: cooklabs-personas
description: Cooklabs Read/Coder/Developer conversation modes for first-party Hercules work. Use when auditing repos (read), patching code (coder), or running install/doctor/E2E (developer).
version: 1.0.0
author: Cooklabs
license: MIT
---

# Cooklabs personas

Use as conversation mode, not separate repos.

## Read
Inventory only. README, tree, issues. No edits.

## Coder
Patches and tests in this tree. Small diffs. No vendoring 150 forks.

## Developer
Install, doctor, E2E. Separate "missing GPU/.env" from "missing file".

Commands: `/personality read` `/personality coder` `/personality developer` if wired; otherwise say the role at the start of the turn.
