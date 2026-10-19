# Step 04 — Attributes 评级（B-段1，锚+裁量，cyborg/ultimate 起步）

你是属性评级器（judgment 层已收敛为确定性锚规则，无 agent 自由发挥）。只读相对路径，只写相对路径。禁 `..` 与绝对盘符。旧 SOP 只作参考，不作输入；旧链冻结，不新增规则。

## 输入（cwd = `G:/brotato-work/<slug>/<variant>/`）

- `steps/01-sentences/sentences.json`：`[{id, text[, start, end]}]`（`?t=` 跳链用；复读原样保留）。
- 全局（repo 侧只读）：`data/terms.csv`（主 17 + 次级 22，共 39，全量）。
- 中间产物（禁读旧链）：禁抄 `data/mentions` + `data/builds`；count/quotes 现场扫 sentences（沿 build_mentions 口径，Ranged 含 `range damage` 别名）。

## 输出（只写这一件）

- `steps/04-attributes/ratings.json`：数组，39 全量，每条：
  `{term_en, term_zh, type, count, rating, confidence, kind, inferred, anchors, reason, quotes, quote_details}`
  - `rating`：`S | A | B | C | D | -`。`count>0` 必 S–D；`count==0` 必 `-`（理由写作者未提及）。
  - `confidence`：S/A 必 `verified`（锚定绿）；B/C/D 必 `candidate`（裁量黄）；`-` 必 `none`。
  - `kind`：S/A 为 `anchor`；B/C/D 为 `discretion`；`-` 为 `none`。
  - `inferred`：S/A 为 `false`（走绿）；B/C/D 为 `true`（标黄永不进绿）；`-` 为 `false`。
  - `anchors`：S/A 非空数组，逐字原话（机检只认这个）；B/C/D/`-` 必 `[]`。
  - `reason`：人话一句 + 关键原句短引（`原话“…”`，须出自本条 quotes）。禁计数泄漏（`字幕N次`只活 `count`）。
  - `quotes`：去重后原句；`quote_details` 与 `quotes` 等长平行（`?t=` 跳链 + 只读 context）。

## 锚规则（删 `_S/_A/_B/_D` 写死，与 08 同一套刀法）

- 拿取动词闭集（机检只认这些逐字，不含 get/lock/roll）：buy/bought/buying、upgrade/upgraded/upgrading、take/took/taken/taking、pick up/picked up。get 太泛（got lucky 误报），lock 系商店锁道具（mutation locked 误报），roll 系重随非拿取。
- 同句共现：term + 拿取动词同句、窗 30 字内、动词未否定（n't/never/without/hard/unfortunately）、term/动词不同 span（pickup 自匹配排除）。有共现即有锚。
- 升级二选一赢过谁：含 over + 拿取动词句，over 前 winner/后 loser，最长匹配定 term（`range damage` 2 词优先于 range/damage 单字）。S=赢家（cyborg 单例 Ranged Damage），A=其余有锚。
- 裁量：无锚 + 有负面（can't/don't/do not/never/without/hard/unfortunately/negative/given up/gave up/reduced/lost/lose/dangerous/avoid/-100%）→ D；无锚无负面按 count 排名上半 B（顺手）/下半 C（妥协/路过），无绝对数。
- `count==0` → `-`（作者未提及）保留。

## 好/坏例

- 好：Ranged Damage S，锚 `buy/take/over`（[12] buy ranged damage、[32] take plus one、[311] take three range damage over 15 attack speed），reason 写清拿取 + 赢过谁 + 短引。
- 好：Life Steal A，锚 `take`（[209] take two life steal、[313] take four life steal），reason 写清拿取 + 短引，不编机制。
- 坏：把 `mutation locked` 里的 locked 当拿取锚收进 % Pickup Range；把 `got lucky` 里的 got 当拿取锚收进 Luck；把整句 quote 复制当 reason；reason 写 `字幕出现 N 次`。
- 坏：S/A 无 anchors 却标 verified 走绿；B/C/D 有 anchors 却标黄；`count==0` 却有 quotes。

## 验收

- 机检：39 全量；`count>0` 必 S–D + `reason + quotes[0]`；`count==0` 必 `-` + `quotes==[]`；S/A 须 `kind anchor + inferred false + verified + anchors 非空逐字出自 quotes`；B/C/D 须 `kind discretion + inferred true + candidate + anchors []`（裁量只查格式）；`quotes` 去重；`quote_details` 平行；`reason` 无计数泄漏。
- 人看：抽 1 条 S/A 锚，验出处真实 + 人话 + 无计数泄漏即过。
