# Step 07 — Priorities 升级/商店（B-段2，cyborg/ultimate 起步）

你是优先级排序器。只读相对路径，只写相对路径。禁 `..` 与绝对盘符。旧 SOP 只作参考，不作输入；旧链冻结，不新增规则。

## 输入（cwd = `G:/brotato-work/<slug>/<variant>/`）

- `steps/04-attributes/ratings.json`：39 全量（升级 Top3 只从 S/A 里按 count 降序取 3，不自创）。
- `steps/05-weapons/weapons.json`：`{t1[], t2[]}`（备查：T1 武器不重复进商店 Top3，避雷不单列进 08）。
- `steps/06-phases/phases.json`：8 段作者章节（备查：怎么拿须合章节奏，可引章节奏；空段跳过，不引用空段）。
- `steps/01-sentences/sentences.json`：现场扫商店 quotes（buy/lock/roll/shop/upgrade 语境，原话数字不丢）。
- 中间产物（G work 动态产生，禁读旧链）：`steps/03-grouping/grouping.json`（商店 Top3 只从 `must_take + verified` 按 count 降序取 3；Peacock 有明确拒绝原话时诚实跳过，顺延下一位；禁抄 `data/mentions` + `data/builds`）。

## 输出（只写这一件）

- `steps/07-priorities/priorities.json`：`{upgrades:[3], shop:[3]}`，每项：
  `{name, kind, why, how_to_get, quotes, quote_details}`
  - `name`：升级名（terms.csv 英文原名）/ 商店名（注册表英文原名）。
  - `kind`：`upgrade | shop`。
  - `why`：人话一句：为什么优先 + 关键原句短引（`原话“…”`），禁模具怪话、禁计数泄漏。
  - `how_to_get`：人话一句：怎么拿（商店见即拿 / 升级二选一优先 / roll 到即锁 / 何波拿换），原话数字不丢，未提空出不脑补。
  - `quotes`：去重后原句，cap 10；`quote_details` 平行（`?t=` + 只读 context）。

## 排序契约（沿 #39 Q6/Q8 + 诚实评价）

- 升级 Top3：只认 04 输出 S/A + count 降序（cyborg/ultimate：Damage / Ranged Damage / Engineering），有几个收几个，不设上限外推；`why` 沿 ratings reason 口径，不重评。
- 商店 Top3：只认 03 输出 `must_take + verified` + count 降序；有拒绝动词原话（ban/skip/not taking）的不硬塞（Peacock 本波明确不拿即顺延，凭动词信号，非抄 builds）；`how_to_get` 凭 verbs 动词（buy/lock/pick up）+ 原话，不编数字。
- 给观点时必须凭 `verified/candidates` 信号：verified 直推，candidates 标黄待人点，不混排。
- DAG：07 依赖 04/05/06，段1绿后才开（跳过空段）；09 依赖 07。

## 验收行（机检 + 人看一单）

- 机检（`check_07`）：schema 合法（upgrades 3 + shop 3）；upgrades 须全在 ratings S/A 内；shop 须全在 grouping must_take 内；每项有 `why + how_to_get + quotes[0]`；`quotes` 去重且能在 sentences 对上。
- 人看（audit 新增 priorities 一节）：抽 1 项（升级或商店），验出处真实 + 怎么拿不丢数字 + 人话即过。
