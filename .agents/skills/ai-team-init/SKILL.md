---
name: ai-team-init
description: Use when the user wants to initialize or verify the project-scoped AI_Team Codex workflow in this repository before running it.
---

# AI_Team Init

Use this skill to verify the repo-scoped Codex setup and initialize local workflow state.

Best practice: open Codex at the target project's root directory before invoking this skill.

## Execute

Run:

```bash
./scripts/company-init.sh
```

## Verify

Confirm all of these exist:
- `.codex/config.toml`
- `.codex/agents/`
- `.agents/skills/ai-team-init/SKILL.md`
- `.agents/skills/ai-team-run/SKILL.md`
- `.ai_company_state/`

## Tell The User

After init, the recommended entrypoint is:
- skill: `$ai-team-run`

Manual fallback:
- command: `./scripts/company-run.sh "<raw user message>"`

Records are stored under `.ai_company_state/`.
