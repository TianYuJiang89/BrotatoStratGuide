---
name: brotato-guide
description: Build a Brotato character guide page from a role issue to publish. Use when asked to create a new character guide, execute a character issue (选片取材填表), or take a role page from sourcing through reviewer gate to the human 3-questions.
---

# Brotato Guide Builder

Execute one role issue end-to-end. The SOP docs are authoritative; this skill is only the execution checklist. Never duplicate SOP meaning here: point at it.

## 0. Read the order (once)

```bash
gh issue view <N> --comments
```

References (single source of truth, read on demand):

- `docs/sop/new-character-guide.md` — §4 sourcing, §5 cross-table gate, §7 eight-step fill table, §8 machine chain, §9 three gates
- `docs/sop/character-issue-template.md` — issue body contract (Top3 + dual labels)
- `docs/sop/reviewer-checklist.md` — reviewer four checks
- `docs/agents/issue-tracker.md` — open/comment/close/labels

Completion: sourcing quintuple + dual-label slots present in the issue. Missing anything, ask the human once as a list, then stop.

## 1. Source (evidence only)

- Metadata per video: `yt-dlp --print` (title / upload_date / duration / description + chapters). Playlist `NA` is unreliable; fetch single videos.
- Auto subs: `yt-dlp --write-auto-sub --sub-langs en-orig --sub-format vtt --skip-download` to `data/subs/<slug>__<variant>.en-orig.vtt`.
- Blocked (`Sign in you're not a bot` / DPAPI): ask the human for repo-root `cookies.txt` (exported via extension, youtube.com only, gitignored), run with `--cookies cookies.txt`; on expiry ask for a fresh one. Never switch to Whisper / frames / Data API / third-party transcription without a separate ticket.
- Correct proper nouns against the wiki; never guess.

Completion: VTTs on disk per variant + dates/versions/chapters posted back to the issue. No VTT, no table: mark 待补, never fabricate.

## 2. Cross-table gate (zero it)

```bash
python scripts/build_mentions.py --slug <slug>
python scripts/check_mentions.py --slug <slug>
```

Completion: `OK cleared`, or every remaining WARN has a written account (补定级 for mentioned-unrated;挂名 title/description/chapters for rated-unmentioned).

## 3. Fill, one thing at a time (§7 eight-step table)

One section per pass: list ALL evidence for that section first (every quote + chapters), then write the synthesis. Finish the section's machine check before starting the next. Never batch the whole table.

Order: 核心属性·主 → 核心属性·次级 → 武器分档 → 关键道具 → 开局/中期/后期 → 升级优先级 → 商店优先级 → 避坑/高难.

Per-step completion: `build_mentions` + `check_mentions` + `python scripts/build.py --slug <slug>` green for that section.

Note rule: every rating/weapon/item note is a viewpoint synthesis (how many times / when / with what / conflicts with what), never a single pasted quote. Single-quote padding counts as uncleared.

## 4. Machine chain (humans never hand-edit product)

```bash
python scripts/check.py docs/<slug>.html
python scripts/check_updates.py
python -m pytest -q
mypy scripts/build.py scripts/check.py scripts/check_updates.py scripts/build_mentions.py scripts/check_mentions.py
```

Only sources change (`data/builds/<slug>.json` + registry); `docs/*.html` rebuilds only. Completion: zero FAIL (`WARN` with 待补/待重审 may publish).

## 5. Reviewer gate, then human 3-questions

- Self-check against the reviewer four checks, paste the list to the issue. Drafter never reviews own draft.
- Hand to reviewer; close every comment point-to-point, rebuild green, resubmit.
- Human 3-questions last: 选片对不对 / 转述忠不忠实 / 评级违不违手感. All pass: resolve per `docs/agents/issue-tracker.md` (comment + close + map pointer). Any fail: annotate in the same issue, one more round.
