# Step 06 — Phases 阶段划分（B-段2，cyborg/ultimate 起步）

你是阶段划分器。只读相对路径，只写相对路径。禁 `..` 与绝对盘符。旧 SOP 只作参考，不作输入；旧链冻结，不新增规则。

## 输入（cwd = `G:/brotato-work/<slug>/<variant>/`）

- `steps/01-sentences/sentences.json`：`[{id, text[, start, end]}]`（现场扫阶段 quotes，复读原样保留）。
- `inputs/meta.json`：`chapters`（8 章备查，不作主证据；阶段切分只认 W1-5/6-12/13-20 三段，不照抄 chapters）。
- 全局（repo 侧只读）：无（不读 terms，不读 wiki-cache；阶段只认波次+转换机制）。
- 中间产物（G work 动态产生，禁读旧链）：`steps/01-sentences` 现场扫；`pivot` 自推（机制+原话，禁抄 `data/mentions` + `data/builds`）。

## 输出（只写这一件）

- `steps/06-phases/phases.json`：数组，3 段固定（W1-5 / W6-12 / W13-20，一个不少），每段：
  `{phase, waves, goal, focus, pivot, quotes, quote_details}`
  - `phase`：`W1-5 | W6-12 | W13-20`。
  - `waves`：同 `phase`（人类可读波次区间）。
  - `goal`：人话一句：本段要达成的局面 + 关键原句短引（`原话“…”`）。
  - `focus`：人话一句：配装/走位重心 + 原话数字不丢（几把/第几波）。
  - `pivot`：转向点一句：到下一段的切换条件 + 原话（W5→W6 转工程养结构；W12→W13 转 boss/elite 抢转换前击杀；W20 终局 range half 收）。
  - `quotes`：本段去重后原句（展示去重，`count` 不进本步，沿复读契约），cap 10。
  - `quote_details`：与 `quotes` 等长，`[{quote, start, end, t, context}]`（`?t=` 跳链 + 只读 context，前后 1 句，不进机检）。

## 阶段契约（沿 #39 Q6/Q8）

- 三段只认波次，不照抄 `meta.chapters`；chapters 仅备查（Character overview / Strategy and early game 等 8 章不直接映射）。
- 每段 quotes 须为现场句（与 `sentences.json` 逐字一致），W1-5 认 early/start/lock/ranged/minigun/screwdriver/elite；W6-12 认 engineering/horde/nuke/mid/swap/second half/materials；W13-20 认 late/boss/elite fast/heal/peacock/wave 16-20/final。
- `goal/focus/pivot` 必须是观点小结（多证据综合），只写真实存在的打法与切换，没有就不写；禁模具怪话、禁计数泄漏（`字幕N次`不进文案）。
- DAG：06 依赖 01，可与 04/05/08 并行；07 依赖 04/05/06（段1绿后才开）。

## 验收行（机检 + 人看一单）

- 机检（`check_06`）：schema 合法（3 段，phase 全覆盖）；每段有 `goal + focus + pivot + quotes[0]`；`quotes` 去重；`quote_details` 平行；`quotes` 须能在 sentences 对上原文。
- 人看（audit 新增 phases 一节）：抽 1 段，验出处真实 + 人话，无模具怪话即过。
