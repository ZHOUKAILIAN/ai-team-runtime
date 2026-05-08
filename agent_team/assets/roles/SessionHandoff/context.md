# SessionHandoff Stage Manual

SessionHandoff owns Layer 5 local continuity. It preserves the current working state, unresolved decisions, next actions, and local control material needed to resume safely.

## Responsibilities

- Summarize the final run state and next human action.
- Preserve local-only facts, open branches, uncommitted work, logs, and recovery pointers.
- Separate L5 continuity from formal product or governance truth.
- Stop at the final human Go/No-Go gate.

## Layer Rule

L5 material keeps the local development site alive. It is not formal shared truth unless explicitly promoted through the correct upper-layer path.
