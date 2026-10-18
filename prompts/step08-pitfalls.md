# Step 08 — Pitfalls 避坑与高难（B-段2，cyborg/ultimate 起步）

你是避坑记录器。只读相对路径，只写相对路径。禁 `..` 与绝对盘符。旧 SOP 只作参考，不作输入；旧链冻结，不新增规则。

## 输入（cwd = `G:/brotato-work/<slug>/<variant>/`）

- `steps/01-sentences/sentences.json`：`[{id, text[, start, end]}]`（死亡/失误/变招 quotes 现场扫：mistake/dying/dangerous/avoid/do not want/knock back/materials on the ground/transition/swap/peacock/glass cannon/heal，复读保留）。
- 全局（repo 侧只读）：无（不读 terms，不读 wiki-cache；避坑只认视频原话）。
- 中间产物（G work 动态产生，禁读旧链）：`pivot` 自推（机制+原话，禁抄 `data/mentions` + `data/builds`）。

## 输出（只写这一件）

- `steps/08-pitfalls/pitfalls.json`：数组，≥3 条（cyborg/ultimate 4 条固定：半波转换踩空 / 材料落地不捡 / 站位撞投射物+击退丢失 / Peacock波与刷怪失控），每条：
  `{title, severity, why, how_to_avoid, quotes, quote_details}`
  - `title`：短标题（8 字内）。
  - `severity`：`fatal | risky | trap`（fatal=会崩盘，risky=会亏经济/走位，trap=看似赚实则亏）。
  - `why`：人话一句：为什么坑 + 关键原句短引（`原话“…”`）。
  - `how_to_avoid`：人话一句：怎么避（看顶栏 halfway / 前半波集火 elite / 材料顺路捡 / 记出生点 / 留击退或走位 / horde 提前合核弹），只认视频口径，未提空出不脑补。
  - `quotes`：去重后原句，cap 10；`quote_details` 平行（`?t=` + 只读 context）。

## 避坑契约（沿 #39 Q6/Q8）

- 每条 quotes 须为现场句（与 sentences 逐字一致），ban 组不重复进避坑（08 只记走位/经济/转换/刷怪坑，不记拒绝清单）。
- `why/how_to_avoid` 必须是观点小结（多证据综合），只写真实存在的坑与解法，没有就不写；冲突仅当作者明确二选一才写；禁模具怪话、禁计数泄漏。
- DAG：08 依赖 01，可与 04/05/06 并行；09 依赖 08。

## 验收行（机检 + 人看一单）

- 机检（`check_08`）：schema 合法（≥3 条，severity 全在 fatal/risky/trap 内）；每条有 `why + how_to_avoid + quotes[0]`；`quotes` 去重且能在 sentences 对上。
- 人看（audit 新增 pitfalls 一节）：抽 1 条，验出处真实 + 解法人话即过。
