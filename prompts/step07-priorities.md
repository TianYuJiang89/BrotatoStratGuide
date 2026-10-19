# Step 07 — Priorities 升级/商店（B-段2，cyborg/ultimate 起步）

你是优先级排序器。只读相对路径，只写相对路径。禁 `..` 与绝对盘符。旧 SOP 只作参考，不作输入；旧链冻结，不新增规则。

## 输入（cwd = `G:/brotato-work/<slug>/<variant>/`）

- `steps/04-attributes/ratings.json`：39 全量（升级 Top3 只从 S/A 里按 count 降序取 3，不自创；04 新评级出来自动跟，不另起规则）。
- `steps/05-weapons/weapons.json`：`{t1[], t2[]}`（备查：T1 武器不重复进商店 TopN，避雷不单列进 08）。
- `steps/06-phases/phases.json`：N 段作者章节（一章一段，本例 8，他例按实际；备查：怎么拿须合章节奏，可引章节奏；空段跳过，不引用空段）。
- `steps/01-sentences/sentences.json`：现场扫商店 quotes（buy/lock/roll/shop/upgrade 语境，原话数字不丢）。
- 中间产物（G work 动态产生，禁读旧链）：`steps/03-grouping/grouping.json`（读新分组：锚+裁量动态 cutoff，68 全收录；商店 TopN 只从 `must_take + verified` 按 count 降序取，最大断层切分，不断层多收，保底 Top1；任一候选有拒绝动词原话即顺延，不点名；禁抄 `data/mentions` + `data/builds`）。

## 输出（只写这一件）

- `steps/07-priorities/priorities.json`：`{upgrades:[3], shop:[N]}`（升级 Top3 沿用，商店 TopN 断层动态，保底 Top1），每项：
  `{name, kind, why, how_to_get, quotes, quote_details}`
  - `name`：升级名（terms.csv 英文原名）/ 商店名（注册表英文原名）。
  - `kind`：`upgrade | shop`。
  - `why`：人话一句：为什么优先 + 关键原句短引（`原话“…”`），禁模具怪话、禁计数泄漏。
  - `how_to_get`：人话一句：怎么拿（商店见即拿 / 升级二选一优先 / roll 到即锁 / 何波拿换），原话数字不丢，未提空出不脑补。
  - `quotes`：去重后原句，cap 10；`quote_details` 平行（`?t=` + 只读 context）。

## 排序契约（沿 #39 Q6/Q8 + 诚实评价，#49 去 Top3 写死 + Peacock 按名顺延）

- 升级 Top3 沿用：只认 04 输出 S/A + count 降序，有几个收几个，不设上限外推；04 新评级出来自动跟，不另起规则；`why` 沿 ratings reason 口径，不重评。
- 商店 TopN 断层动态：只认 03 新分组输出 `must_take + verified` + count 降序；先通用顺延（任一候选 `quotes + reason` 含拒绝动词原话即顺延，不点名；拒绝信号为拿取否定/跳过系：`not taking/not take/don't take/do not take/don't buy/do not buy/skip/avoid/ban/recycle/sell/passed on/ignoring` 等逐字，不含泛 `don't want`），再按 `count` 最大断层切分（`gaps=count[i]-count[i+1]`，最大断层即止，不断层（max==0）多收，保底 Top1，N 动态；tie 取首个最大断层，与 05 排名制同一刀法）；`how_to_get` 凭 verbs 动词（buy/lock/pick up）+ 原话，不编数字。
- 给观点时必须凭 `verified/candidates` 信号：verified 直推，candidates 标黄待人点，不混排。
- DAG：07 依赖 03/04/05/06，段1绿后才开（跳过空段）；09 依赖 07。

## 验收行（机检 + 人看一单）

- 机检（`check_07`）：schema 合法（upgrades 3 沿用 + shop N≥1 动态）；upgrades 须全在 ratings S/A 内；shop 须全在新 grouping must_take 内（含 verified + 无拒绝动词 + 断层 TopN）；每项有 `why + how_to_get + quotes[0]`；`quotes` 去重且能在 sentences 对上。
- 人看（audit 新增 priorities 一节）：抽 1 商店项，验出处真实 + 怎么拿不丢数字 + 人话即过。
