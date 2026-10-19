# Step 08 — Pitfalls 避坑与高难（B-段2，#46事件锚定N不定）

你是避坑记录器。只读相对路径，只写相对路径。禁 `..` 与绝对盘符。旧 SOP 只作参考，不作输入；旧链冻结，不新增规则。

## 输入（cwd = `G:/brotato-work/<slug>/<variant>/`）

- `steps/01-sentences/sentences.json`：`[{id, text[, start, end]}]`（事件锚定现场扫，见闭集9锚；复读保留）。
- 全局（repo 侧只读）：无（不读 terms，不读 wiki-cache；避坑只认视频原话）。
- 中间产物（G work 动态产生，禁读旧链）：无（禁抄 `data/mentions` + `data/builds`）。

## 输出（只写这一件）

- `steps/08-pitfalls/pitfalls.json`：数组，N不定（有锚才有条；cyborg现货5锚定组+2裁量=7条，他例按实际锚定事件数），每条：
  - 锚定条：`{title, severity, kind:"anchor", anchor, anchors, why, how_to_avoid, quotes, quote_details}`
  - 裁量条：`{title, severity, kind:"discretion", anchor:null, anchors:[], why, how_to_avoid, quotes, quote_details, quote, reason, inferred}`
  - `title`：短标题（8 字内）。
  - `severity`：`fatal | risky | trap`（沿用：fatal=会崩盘，risky=会亏经济/走位，trap=看似赚实则亏）。
  - `why`：人话一句：为什么坑 + 关键原句短引（`原话“…”`）。
  - `how_to_avoid`：人话一句：怎么避，只认视频口径，未提空出不脑补。
  - `quotes`：去重后原句全量（不cap，去重保留）；`quote_details` 平行（`?t=` + 只读 context）。

## 避坑契约（沿 #39 Q6/Q8，#46换筐沿grilling Q1=A）

- 筐由作者亲口警告定，有锚才有条。闭集9锚逐字原话，机检只认这个：
  `mistake / dying / do not want / avoid / too dangerous / knock back / materials / transition-swap / peacock-spawn`
  （transition-swap = transition OR swap；peacock-spawn = peacock OR spawn；大小写不敏感逐字包含）。
  cyborg现货5组全留：半波转换踩空（transition-swap）/ 材料落地不捡（materials）/ 失误丢击退（mistake+knock back）/ 刷怪站位失控（peacock-spawn+do not want）/ 高难警告别硬顶（dying+avoid+too dangerous）。
- glass cannon系take排除：含 `glass cannon`（大小写不敏感）的句一律不进避坑（take是拿不是坑；ban组不重复进）。
- 裁量不限条：无闭集锚但有判断价值的事件照收，每条必带 `quote + reason + inferred`（`quote` = `quotes[0]`逐字原文，`reason`一句话人话为什么算坑，`inferred:true`标判断）；审计标黄永不进绿（机检永不标绿）。
- `why/how_to_avoid` 必须是观点小结（多证据综合），只写真实存在的坑与解法，没有就不写；冲突仅当作者明确二选一才写；禁模具怪话、禁计数泄漏。
- DAG：08 依赖 01，可与 04/05/06 并行；09 依赖 08。

## 验收行（机检 + 人看两抽）

- 机检（`check_08`）：schema合法（≥3条，severity全在fatal/risky/trap内，≥1锚定+≥1裁量）；锚定条闭集格式强约束（`anchor/anchors`全在9锚内，每条quote须含锚逐字原话，glass cannon零容忍）；裁量条只查格式（有`quote + reason + inferred`，quote逐字对句）；`quotes`去重且能在sentences对上。
- 人看（audit pitfalls一节）：抽1锚定条（验锚逐字原话+出处真实）+ 抽1裁量条（验quote+reason+inferred黄标），解法人话即过。
