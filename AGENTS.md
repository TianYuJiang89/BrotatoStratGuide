## Principles

- Deterministic-first: anything that needs no agent judgment is fixed code (scripts), not prompts. Agent sessions only do judgment (trade-offs, ratings, human wording). Lock input/output contracts; feed prompts the minimum context the judgment needs.
- No silent fallback: problems fail loud (red light, error, missing-section-is-fail). No silent degrade, no falling back to mock, no inventing numbers to fill slots. Any fallback must be discussed first and explicitly allowed by the user, and must be labeled as a non-normal path in UI/logs.

## Agent skills

### Issue tracker

Issues live in GitHub Issues. See `docs/agents/issue-tracker.md`.

### Triage labels

Default five canonical triage labels. See `docs/agents/triage-labels.md`.

### Domain docs

Single-context layout. See `docs/agents/domain.md`.

## Python environment

Python runs only via repo-local `.venv`. See `docs/agents/python-env.md`.
