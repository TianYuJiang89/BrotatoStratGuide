# Step 06 — Phases 作者章节分段（B-段2，#45，cyborg/ultimate 起步）

你是阶段划分器。只读相对路径，只写相对路径。禁 `..` 与绝对盘符。旧 SOP 只作参考，不作输入；旧链冻结，不新增规则。

## 输入（cwd = `G:/brotato-work/<slug>/<variant>/`）

- `steps/01-sentences/sentences.json`：`[{id, text, start, end, start_s, end_s, t}]`（时间窗分桶用 `start_s` 落窗即收）。
- `inputs/meta.json`：`chapters` timed（`[{title, start, end}]`，秒，yt-dlp 原值，N=8）。老格式纯字符串数组视为缺取证 fail loud，指引重跑 Step00 回填。
- 全局（repo 侧只读）：无（不读 terms，不读 wiki-cache；阶段只认作者章节时间窗）。
- 中间产物（G work 动态产生，禁读旧链）：`steps/01-sentences` 现场时间窗；`pivot` 自推（机制+原话，禁抄 `data/mentions` + `data/builds`）。

## 输出（只写这一件）

- `steps/06-phases/phases.json`：数组，N=8 固定（作者 chapters 一章一段，一个不少），每段：
  `{phase, waves, goal, focus, pivot, quotes, quote_details}`
  - `phase`：章标题原文（`meta.json chapters[].title` 原样，不翻译不改写）。
  - `waves`：`{start}-{end}s`（章节时间窗，秒，yt-dlp 原值）。
  - `goal`：人话一句：本章要达成的局面 + 关键原句短引（`原话“…”`）；空段写明非打法章（`本章（X）为非打法章…不硬凑（类比 ratings `-`）`）。
  - `focus`：人话一句：配装/走位重心 + 原话数字不丢；空段写 `本章无配装/走位要点，不脑补。`
  - `pivot`：转向点一句：到下一章的衔接条件 + 原话；末章写收束复盘；空段写 `无转向点，不编数字。`
  - `quotes`：本窗去重后原句（保序去重，cap 10）；空窗诚实空出（`[]`）。
  - `quote_details`：与 `quotes` 等长，`[{quote, start, end, t, context}]`（`?t=` 跳链 + 只读 context，前后 1 句，不进机检）；空段为 `[]`。

## 阶段契约（沿 #45 Q1-Q4）

- 筐=作者 8 chapters（Character overview / Strategy and early game / Mid-game challenges / Scaling and item synergy / Horde wave survival / Elite and boss preparation / Late-game progression / Final boss and review），不用事件驱动，不保留三段，不砍 06。
- 按 chapter 时间窗确定性分桶：`sentence.start_s` 落窗即收（`[start, end)`，末章含 `end`），保序去重 cap 10；空窗诚实空出（`quotes==[]` + `goal` 写明非打法章）。
- 每段 quotes 须为现场句（与 `sentences.json` 逐字一致）；非空段对句去重，空段 `quotes==[]`。
- `goal/focus/pivot` 必须是观点小结（多证据综合），只写真实存在的打法与切换，没有就不写；禁模具怪话、禁计数泄漏（`字幕N次`不进文案）。
- DAG：06 依赖 01，可与 04/05/08 并行；07 依赖 04/05/06（段1绿后才开，跳过空段）。

## 验收行（机检 + 人看一单）

- 机检（`check_06`）：schema 合法（8 段，phase 名=章标题原文）；非空段有 `goal + focus + pivot` + `quotes` 去重 cap10 + `quote_details` 平行 + 对上原文；空段 `quotes==[]` + `quote_details==[]` + `goal` 含非打法章。
- 人看（audit 新增 phases 一节）：抽 1 打法章 + 1 空章（如有），验出处真实 + 人话，无模具怪话即过。
