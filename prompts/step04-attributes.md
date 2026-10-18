# Step 04 — Attributes 评级（B-段1，cyborg/ultimate 起步）

你是属性评级器。只读相对路径，只写相对路径。禁 `..` 与绝对盘符。旧 SOP 只作参考，不作输入；旧链冻结，不新增规则。

## 输入（cwd = `G:/brotato-work/<slug>/<variant>/`）

- `steps/01-sentences/sentences.json`：`[{id, text[, start, end]}]`（B-04 起统一带 `start/end`，`?t=` 跳链用；复读原样保留，不合并计数）。
- `inputs/registry-slice.json`：本变体武器+道具子集（本步备查，不作主证据）。
- `inputs/meta.json`：标题/描述/chapters（备查，不作主证据）。
- 全局（repo 侧只读）：`data/terms.csv`（主 17 + 次级 22，共 39，全量两表口径）。
- 中间产物（G work 动态产生，禁读旧链）：`steps/01-sentences/sentences.json` 现场扫 count/quotes（沿 build_mentions 口径，复读保留）；rating/note 自推（机制+动词信号+原话，禁抄 `data/mentions` + `data/builds`，旧链已隔离退役）。

## 输出（只写这一件）

- `steps/04-attributes/ratings.json`：数组，39 全量（主 17 + 次级 22，一个不少），每条：
  `{term_en, term_zh, type, count, rating, confidence, reason, quotes, quote_details}`
  - `term_en`：terms.csv 英文原名（大小写按表）。
  - `term_zh`：terms.csv 中文。
  - `type`：`primary | secondary`。
  - `count`：现场扫 sentences 的 term count（`count==0` 即未提及，沿提过即算口径）。
  - `rating`：`S | A | B | C | D | -`。`count>0` 必须有口径（S–D，不许空出）；`count==0` 才许 `-`（理由写作者未提及）。
  - `confidence`：`verified | candidate | none`。有任一 verified 级出处即 verified，否则 candidate；未提及为 none。
  - `reason`：人话一句：结论 + 一句理由 + 关键原句短引（`原话“…”`）。禁模具怪话（无依据的配/冲突）、禁计数泄漏（`字幕N次`只活 `count`，不进 `reason`）。
  - `quotes`：该 term 去重后原句（展示去重，`count` 口径不动，沿复读契约），cap 10。
  - `quote_details`：与 `quotes` 等长，`[{quote, start, end, context}]`。`start/end` 拷 sentences（`?t=` 跳链用，可空）；`context` 为该句前后 1 句拼接（只读，只给人看，不进机检，quote 保持逐字原文）。

## 评级契约（沿 #39 Q1/Q8）

- 提过即算口径：视频里明确拿过/roll 过/ban 过的属性都必须定级；顺手拿一次、备选后放弃的给 C 并写明原话；只有全程没出现过的（`count==0`）才空出（`- / 作者未提及`）。
- note 必须是观点小结（多证据综合），只写真实存在的搭配与取舍，没有就不写；冲突仅当作者明确二选一（ban/卖掉/roll 掉/明确说不要）才写。
- 计数只活 JSON `count`（现场扫 sentences），不进 note/页面。

## 验收行（机检 + 人看一单）

- 机检（`check_04/05`）：schema 合法（39 全量，主 17 + 次级 22 一个不少）；`count>0` 必有 S–D 且有 `reason + quotes[0]`；`count==0` 必为 `-` 且 `quotes==[]`；`quotes` 去重；`reason` 无计数泄漏；`start/end` 有即合法时间格式。
- 人看（audit 新增 attributes 一节）：抽 1 条（属性 S/A 口径），验出处真实 + 理由人话，无模具怪话、无计数泄漏即过。
