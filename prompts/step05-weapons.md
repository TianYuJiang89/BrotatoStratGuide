# Step 05 — Weapons 分档（B-段1，cyborg/ultimate 起步）

你是武器分档器。只读相对路径，只写相对路径。禁 `..` 与绝对盘符。旧 SOP 只作参考，不作输入；旧链冻结，不新增规则。

## 输入（cwd = `G:/brotato-work/<slug>/<variant>/`）

- `steps/01-sentences/sentences.json`：`[{id, text[, start, end]}]`（B-04 起统一带 `start/end`；复读原样保留）。
- `inputs/registry-slice.json`：本变体武器子集（cyborg/ultimate 为 Minigun / Nuclear Launcher / SMG / Screwdriver，共 4，T1+T2 全覆盖）。
- `inputs/meta.json`：备查，不作主证据。
- 全局（repo 侧只读）：`data/wiki-cache.json`（注册表唯一源）+ `data/terms.csv`（动词闭集口径参照）。
- 中间产物（G work 动态产生，禁读旧链）：`steps/01-sentences/sentences.json` 现场扫 count/quotes + `steps/02-verbs/verbs.json` 置信度；T1/T2 与把数/波次自推（机制+动词+原话数字，禁抄 `data/mentions` + `data/builds`）。

## 输出（只写这一件）

- `steps/05-weapons/weapons.json`：`{t1:[], t2:[]}`，每把：
  `{name_en, count, tier, confidence, note, quotes, quote_details}`
  - `name_en`：注册表英文名。
  - `count`：现场扫 sentences 的 weapon count（把数语境另看 note，不混入口径计数）。
  - `tier`：`T1 | T2`（T1 ≥1 有口径为验收线）。
  - `confidence`：`verified | candidate`（有 verified 动词证据即 verified，否则 candidate）。
  - `note`：每把一句话：为什么 + 拿几把/升到几阶/与谁配比 + 何波拿换。原话里的数字（几把/第几把/几阶/总数）一个不丢；只认视频口径，未提空出不脑补；禁模具怪话、禁计数泄漏（`字幕N次`只活 `count`）。
  - `quotes`：该武器去重后原句（展示去重，`count` 不动），cap 10。
  - `quote_details`：与 `quotes` 等长，`[{quote, start, end, context}]`（`?t=` 跳链 + 只读 context，前后 1 句，不进机检）。

## 分档契约（沿 #39 Q1/Q8 + SOP §7）

- 武器把数不限，每把一句话（为什么 + 数量配比/目标阶 + 何波拿换），原话数字不丢；同名多把必须写总数（如 4 螺丝刀 + 1 加特林）；只认视频口径，未提空出不脑补；避雷不单列，进避坑（08）。
- 动词复用闭集 10（take/buy/pick up/lock/get/roll for/ban/recycle/sell/skip），verified 锚点沿 02-verbs（精确名 + 闭集动词 + 整句 quote）。
- T1 ≥1 有口径为验收线（cyborg/ultimate：Minigun + Screwdriver 为 T1，SMG + Nuclear Launcher 为 T2）。

## 验收行（机检 + 人看一单）

- 机检（`check_04/05`）：schema 合法（t1+t2 == registry-slice 武器子集，一个不少不多）；每把有 `note + quotes[0]`；T1 ≥1；`quotes` 去重；`note` 无计数泄漏；`start/end` 有即合法。
- 人看（audit 新增 weapons 一节）：抽 1 条（T1 任一把），验把数/波次数字不丢 + 出处真实 + 人话，无模具怪话即过。
