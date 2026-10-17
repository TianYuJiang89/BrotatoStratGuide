---
name: brotato-guide
description: Scaffold a new GitHub issue for building a Brotato character guide. Use when asked to create a guide for a character (e.g. 给工程师建攻略). This skill only writes the ticket, then stops.
---

# Brotato Guide Ticket Scaffolder

You do one thing: open a new, fully-specified issue. You never source, fill, build, or review. Execution belongs to another agent (`/implement`) in another session.

## Steps

### 1. Read the order template (once)

Read `docs/sop/character-issue-template.md` (the issue body contract) and `docs/sop/new-character-guide.md` §4–§9 (the requirements the ticket must point at). Role name comes from the human's message (`/skill:brotato-guide 给<角色>建攻略`); if the role is missing or ambiguous, ask once, then stop.

Completion: role fixed, template loaded.

### 2. Open the issue, then stop

```bash
gh issue create --title "角色攻略：<角色名> (<EN>)" --label "wayfinder:task" --body-file <filled-template>
```

Body rules (single source of truth stays in the repo; the ticket only points):

- Role slots filled from the template (`目标角色`节); the `选定取材` section stays slotted: the executor retrieves Top3 per §4, the human picks, then the executor fills. You fill no video IDs.
- Requirements section points at, never copies: `docs/sop/new-character-guide.md` (一事一过 8 步 + note rules + 三道闸), `docs/sop/reviewer-checklist.md` (four checks), `.agents/skills/brotato-guide/` is you — do not reference yourself.
- Constraints line, verbatim: cookie collaboration (human provides repo-root `cookies.txt`, never committed; executor asks on block), TDD seams only (CLI exit codes + `docs/*.html` + `data/*.json` bytes), products human-never-hand-edits, no third-party transcription without a separate ticket.
- Map link: first line `Part of #16`; acceptance = reviewer gate + human 3-questions (选片对不对 / 转述忠不忠实 / 评级违不违手感).
- Apply the AFK-ready triage label (`ready-for-agent` per `docs/agents/triage-labels.md`).

Completion: issue number in hand, `gh issue view <new-N>` shows filled body + labels. Output the number and stop. Nothing else runs in this session.
