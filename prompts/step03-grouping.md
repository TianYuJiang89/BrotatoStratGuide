# Step 03 — Grouping 分组（cyborg/ultimate 试点，锚+裁量）

你是分组器（judgment 层已收敛为确定性锚规则，无 agent 自由发挥）。只读相对路径，只写相对路径。禁 `..` 与绝对盘符。旧 SOP 只作参考，不作输入；旧链冻结，不新增规则。

## 输入

- `steps/02-verbs/verbs.json`：`{verified[], candidates[]}`。
- `inputs/registry-slice.json`：本变体武器+道具子集。
- `inputs/meta.json`：标题/描述/chapters，只作 reason 出处备选，主证据为 quotes。

## 输出

- `steps/03-grouping/grouping.json`：数组，每条 `{name_en, count, group, tier, confidence, inferred, has_verb, verb, verb_type, reason, quotes}`。
  - `group` 四值：`must_take | mentioned_not_taken | ban | casual_mention`。
  - `tier`：`must_take` 才有（本变体统一 `convenient`，无按名分档），余为 `null`。
  - `confidence`：`verified | candidate`（有任一 verified 证据即 verified，否则 candidate；拿不准的进 candidates 位即 candidate + 标黄）。
  - `verb_type`：`closed | mapped | none`。
  - `inferred`：无动词意图推断为 `true`（标黄永不进绿），有动词锚为 `false`。
- 主脚本拷贝晋升 `outputs/groups.json`（内容同本文件，`sha` 校验见 check_segment1）。

## 锚规则（删阈值 + 删全部按名特判，与 04/05 同一套刀法）

- **全收录保留**：`count>0` 的 68 件全进表（零提及不进）；`count` = 该件在字幕命中句数（沿 build_mentions 口径，现场扫 sentences，禁读旧链）。`count` 只活 JSON，不进 `reason` 文案。
- **ban 锚**：ban 系动词原话即 ban（`ban / recycle / sell` 闭集原话，或 candidates `mapped_to==ban` 的转述如 `avoid→ban` 含 agent 补）。无按名例外（Glass Cannon 是否 ban 只看有无 ban 系原话，本变体无则不 ban）。`verb=ban`，`confidence` 有 verified ban 则 verified 否则 candidate，`inferred=false`。机检只认：ban 引文须含拒绝动词逐字（`ban/avoid/recycl/sell/skip/ignor`）。
- **拿取锚 + 高频**：拿取系动词原话（`take / buy / pick up / lock / get / roll for` 闭集原话，或 candidates `mapped_to` 落拿取系含 agent 补）**且**高频 → `must_take`（本变体统一 `convenient`，不分 core/compromise，不按名）。高频无固定数：68 件 `count` 的 `mean+stdev` 动态 cutoff（`count>=cutoff` 即高频，无 `≥8/≥4` 写死）。`confidence` 有 verified 拿取即 verified 否则 candidate，`inferred=false`。
- **跳过位**：`skip` 系原话（`skip` 闭集原话，或 candidates `mapped_to==skip` 如 `ignoring→skip` 含 agent 补）且高频 → `mentioned_not_taken`（拿了又放 / 有资源没拿，一句话原因）；`skip` 系但低频 → `casual_mention`（低频路过照旧）。ban 优先于 skip，skip 优先于拿取。
- **路过照旧**：低频（`count<cutoff`）无 ban/skip 强信号 → `casual_mention`，一句话“路过提及、无明确评价”（1–3 次典型，但不写死数字门槛，以动态 cutoff 为准）。
- **拿不准进 candidates 位**：无动词（`verb_type=none`）或信号冲突无法定级 → 不硬分组，`confidence=candidate + inferred=true` 标黄，`reason` 写清为什么拿不准 + 关键原句短引，`quotes` 照旧全收录。字段已在 schema，不加字段。
- `reason` 人话：结论 + 一句人话理由（含动词锚：拿取/拒绝动词原话是哪个）+ 关键原句短引（`原话“…”`，须出自本条 `quotes`，60 字内短引）；禁模具怪话（无依据的配/冲突）、禁计数泄漏（`字幕N次` 只活在 JSON `count`，不进 `reason` 文案）。

## 好/坏例

- 好：Boxing Glove ban，锚 `ban`（[132] I'm going to ban the boxing glove），reason 写清拒绝动词 + 短引，不编机制。
- 好：Turret must_take convenient，锚 `buy`（拿取系原话）+ 高频（动态 cutoff 之上），reason 写清拿取动词 + 短引，不写 `字幕8次`。
- 好：Landmines mentioned_not_taken，锚 `ignoring→skip`（转述种子 + agent 补同字段），reason 写清跳过语境 + 短引。
- 好：Bonk Dog casual inferred:true，无动词，reason 写清拿不准 + 短引，标黄。
- 坏：`Glass Cannon 永不 ban` 按名特判；`Mutation/Focus 永妥协` 按名分档；`count>=8/>=4` 写死阈值；`reason` 写 `字幕出现 N 次`；ban 无拒绝动词原话却进 ban。

## 验收行（机检 + 人看两抽）

- 机检（check_segment1）：schema 合法；68 全收录（`count>0` 全进）；verified 全部分组；candidates 每条有 `quote+reason` 且 `inferred` 为 bool；低频有一句话交代；ban 必有拒绝动词逐字；must_take 必有拿取系动词信号；`outputs/groups.json` 与 `steps/03-grouping/grouping.json` 一致；`sha` 对上。
- 人看（audit.html 两抽）：一 ban 锚 + 一转述补（mapped_to 含 agent 补），各抽 1 条验出处真实 + 理由人话，无模具怪话、无计数泄漏即过；结论落本票评论。不含多变体复制、不含 docs 渲染。
