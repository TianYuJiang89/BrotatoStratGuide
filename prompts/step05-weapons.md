# Step 05 — Weapons 分档（B-段1，锚+裁量+排名制，cyborg/ultimate 起步）

你是武器分档器（确定性排名，无 agent 自由发挥）。只读相对路径，只写相对路径。禁 `..` 与绝对盘符。旧 SOP 只作参考，不作输入；旧链冻结，不新增规则。

## 输入（cwd = `G:/brotato-work/<slug>/<variant>/`）

- `steps/01-sentences/sentences.json`：现场扫 count/quotes（复读保留）。
- `inputs/registry-slice.json`：本变体武器子集（cyborg/ultimate 4 把，T1+T2 全覆盖）。
- 中间产物（G work 动态产生，禁读旧链）：`steps/02-verbs/verbs.json` 置信度（verified=精确名+闭集动词+整句 quote）；禁抄 `data/mentions` + `data/builds`。

## 输出（只写这一件）

- `steps/05-weapons/weapons.json`：`{t1[], t2[]}`，每把：
  `{name_en, count, tier, confidence, kind, inferred, anchors, note, quotes, quote_details}`
  - `tier`：`T1 | T2`（T1≥1 为验收线）。
  - `confidence`：T1 必 `verified`（拿取动词锚）；T2 按有无 verified 取 `verified/candidate`。
  - `kind`：T1 为 `anchor`；T2 为 `discretion`。
  - `inferred`：T1 为 `false`（走绿）；T2 为 `true`（标黄永不进绿）。
  - `anchors`：T1 非空（拿取动词 + 数字词，逐字原话，机检只认这个）；T2 必 `[]`。
  - `note`：通用模板（无按名模板），T1 必含把数/波次原话数字（须逐字出自 quotes，不编数字，未提空出不脑补）+ 人话；T2 过渡/备选位人话。禁计数泄漏、禁模具怪话。
  - `quotes`：去重后原句；`quote_details` 平行（`?t=` 跳链 + 只读 context）。

## 分档契约（删 `is_core_gun` + 绝对阈值 + 按名 note 模板）

- T1 锚：verified 拿取动词（02-verbs 精确名 + 闭集动词 + 整句 quote）+ 把数/波次原话不丢（note 须含 quotes 内数字词逐字：one/two/three/four/five/second/level/wave/1/2/3/4/5；机检逐字对 note 与 quotes）。
- T1 判定改排名制：registry 子集内按 `score=count+动词信号（verified+5）` 排，最大断层切分，不卡绝对数；保底 Top1。
- 裁量：T2 过渡/备选位（前中期过渡，有 T1 即换，不升满），只查格式（note+quotes），审计标黄。

## 好/坏例

- 好：Minigun T1，锚 `take/second`（[27] take a second minigun），note 含 second 逐字出自 quotes，人话 + 短引。
- 好：Screwdriver T1，锚 `buy/four`（[61] buy a screwdriver、four screwdrivers），note 含 four 逐字出自 quotes。
- 好：Nuclear Launcher T2，`kind discretion + inferred true + anchors []`，note 过渡位人话 + 短引，不升满。
- 坏：按名写模板（Minigun 必开局锁1把、Screwdriver 必4把）；卡绝对数（count≥8 才 T1）；T1 note 无数字；T1 anchors 有成员未逐字出自 quotes；T1 confidence 非 verified。

## 验收

- 机检：t1+t2==registry-slice 子集；T1≥1；每把有 `note + quotes[0]`；T1 须 `kind anchor + inferred false + verified + anchors 非空逐字出自 quotes + note 含 quotes 内数字词逐字`；T2 须 `kind discretion + inferred true + anchors []`（裁量只查格式）；排名制 `最小T1 score ≥ 最大T2 score`；`quotes` 去重；`quote_details` 平行；`note` 无计数泄漏。
- 人看：抽 1 条 T1 锚，验把数/波次数字不丢 + 出处真实 + 人话即过。
