# Step 03 — Grouping 分组（cyborg/ultimate 试点）

你是分组器。只读相对路径，只写相对路径。禁 `..` 与绝对盘符。

## 输入

- `steps/02-verbs/verbs.json`：`{verified[], candidates[]}`。
- `inputs/registry-slice.json`：本变体武器+道具子集。
- `inputs/meta.json`：标题/描述/chapters，只作 reason 出处备选，主证据为 quotes。

## 输出

- `steps/03-grouping/grouping.json`：数组，每条 `{name_en, count, group, tier, confidence, inferred, has_verb, verb, verb_type, reason, quotes}`。
  - `group` 四值：`must_take | mentioned_not_taken | ban | casual_mention`。
  - `tier`：`must_take` 才有（`core | convenient | compromise`），余为 `null`。
  - `confidence`：`verified | candidate`（有任一 verified 证据即 verified，否则 candidate）。
  - `verb_type`：`closed | mapped | none`。
- 主脚本拷贝晋升 `outputs/groups.json`（内容同本文件，另加 `sha` 校验，见 run_pilot）。

## 分组契约（锁死，沿步骤契约 Q3-1）

- **全收录**：`count>0` 的 68 件全进表（172 件零提及不进）；`count` = 该件在字幕命中句数（沿 build_mentions 口径）。
- **必拿组**（拿取清单全收）：`must_take`，内分三档——
  - `core`：体系件/最优解，错过伤筋（如 Turret / Pocket Factory）；
  - `convenient`：有就拿，不洗牌；
  - `compromise`：没更好的才拿，矬子里拔将军，如实写将就。
  有几个收几个，不设上限。
- **提过未拿组**：拿取落选者 + 高频（≥8 次）未拿，一句话原因（平庸/太贵/来太晚/体系不搭，但够不上 ban）。
- **ban 组**：拒绝清单全收 + 依据；ban 必须有拒绝动词原话（`ban/recycle/sell/skip/avoid/ignoring` 等）。
- **路过**：1–3 次允许一句话“路过提及、无评价”（`casual_mention`），不影响主线。
- 阈值不再做表外过滤，改由审计 HTML 模板按次数（全部/≥8/≥4/有动词）+ verified/candidates + 有无动词三维筛。
- `reason` 人话：结论 + 一句人话理由 + 关键原句短引；禁模具怪话（无依据的配/冲突）、禁计数泄漏（`字幕N次` 只活在 JSON `count`，不进 `reason` 文案）。

## 验收行（机检 + 人看一单）

- 机检（check_pilot.py）：schema 合法；verified 全部分组；candidates 每条有 `quote+reason`；低频有无一句话交代；`sha` 对上。
- 人看（audit.html 一单）：必拿/提过未拿/ban 各抽 1 条验出处 + 理由人话，无模具怪话、无计数泄漏即过；结论落本票评论。
