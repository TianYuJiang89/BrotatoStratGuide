---
name: brotato-guide
description: Scaffold a production issue for building a new-character Brotato guide on the current agent chain (取材→取证→真跑→人看). Use when asked to create a guide for a character (e.g. 给法师建攻略) with role and difficulty.
---

# Brotato Guide Ticket Scaffolder（新链）

One job: open a new, fully-specified production issue. Never source, fill, build, or review. Execution belongs to another session.

Pointers (point, never copy): chain `scripts/run_chain.py` (+ `fetch_inputs`, `check_segment1/2`); glossary `CONTEXT.md`; frozen fewshots `prompts/step*-fewshot.md` (never edit in production — gaps go to a separate ticket); exemplar [#56 five-role run](https://github.com/TianYuJiang89/BrotatoStratGuide/issues/56); audit `templates/audit.html`; render `scripts/prototype_render.py` (extract +落盘 `outputs/guide.html`); index `scripts/build_new_index.py` (new card must enter `docs/new_index.html` in-ticket, never a separate ticket).

## Steps

### 1. Fix slug and variant (once)

Role and difficulty come from the human's message (`给<角色><难度>建攻略`); if either is missing or ambiguous, ask once, then stop.

Completion: slug + variant fixed.

### 2. Confirm state, then stop if unclear

Check what already exists: `G:/brotato-work/<slug>/<variant>/inputs/manifest.json` (which video_id), `outputs/guide.json` (built or not). Write into the ticket: 本次首建/重跑. 清场由运行时自动做（换片整目录备份，见 #69），runner 不得手删；只记录状态，不判内容。

Completion: 首建/重跑 in hand.

### 3. Open the issue, then stop

```bash
gh issue create --title "角色攻略：<角色名> (<EN>) / <variant>" --label "ready-for-agent" --body-file <filled-template>
```

Body rules (single source of truth stays in the repo; the ticket only points):

- `目标角色`节填 slug/variant/covers；`选定取材`节保持空槽：executor 按取材口径检索 Top3（Cephalopocalypse 同角色，Ultimate > Nightmare Guide > Nightmare > Danger 5 保底，有 Guide 后缀才算教学局，标题链接+视频ID+发布日期+难度+字幕五元组），人拍 1 个后 executor 回填。你不填视频 ID。
- Requirements 只指向：`run_chain` 用法、双 check 全绿、审计只读校验、渲染抽验+落盘（`prototype_render` 出 `outputs/guide.html`）、索引进页（`build_new_index` 重建 `docs/new_index.html`，同票内做完，不另起票）、`CONTEXT.md` 术语。不复制。
- Constraints：cookie 协作（人出 repo 根 `cookies.txt`，不入库；被风控即停等人重出）；fail loud（缺字幕/被风控/check 红灯即停，不猜测不回落）；产物人绝不手改；prompt/分组/schema 缺口一律另票，本票内不修。
- Acceptance：双 check 全绿 + 审计同目录可读 + sha 对上 manifest；人看四抽（04 一条 S/A + 05 一把 T1 + 06 一段 + 08 两条，原话逐字 + 人话可执行，逐条过/不过）；渲染抽验（六节段序 + `?t=` 点跳）+ 落盘 `outputs/guide.html`；索引进页（新卡进 `docs/new_index.html` 可点，`看攻略` href 目标存在，同票内做完，不另起票）。
- Production stays out of wayfinding：不挂 `wayfinder:*` 标签，不写 `Part of` 地图行（沿 21b8aa6/a3edfae）。

Completion: issue number in hand, `gh issue view <new-N>` shows filled body + `ready-for-agent`. Output the number and stop. Nothing else runs in this session.
