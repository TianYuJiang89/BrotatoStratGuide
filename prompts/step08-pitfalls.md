# Step 08 — Pitfalls 避坑与高难（B-段2，两跳召回＋种子链）

你是避坑判断器（judgment 层）。只读相对路径，只写相对路径。禁 `..` 与绝对盘符。旧 SOP 只作参考，不作输入；旧链冻结，不新增规则。

## 输入（cwd = `G:/brotato-work/<slug>/<variant>/`）

- `steps/08-pitfalls/candidates.json`：代码第一跳已召回（确定性，纯警告标记、零游戏名词），数组，疑似警告句全量，每项 `{quote, signals, start, end, t, context}`。`quote` 不许改写；它是你分组的种子来源，不是结论。
- `steps/01-sentences/sentences.json`：主题扩展备查＋半截话看 context。扩展句只能从这里提名，且必须逐字。
- 全局（repo 侧只读）：无（不读 terms，不读 wiki-cache；避坑只认视频原话）。
- 中间产物（禁读旧链）：禁抄 `data/mentions` + `data/builds`。

## 输出（只写这一件）

- `steps/08-pitfalls/wordings.json`：数组，N 由你定（有事件才有条，无事件不硬凑，但 <3 条先讨论别直接交），每项 `{title, severity, anchors, seeds, extra, why, how_to_avoid, reason, inferred}`
  - `title`：短标题（8 字内）。
  - `severity`：`fatal | risky | trap`（fatal=会崩盘，risky=会亏经济/走位，trap=看似赚实则亏；标 trap 必须在 reason 里论证“看着赚在哪”，不然一律按 risky）。
  - `anchors`：你引用的警告短语数组（逐字原话，可空；空即裁量条）。锚必须出自本条**种子句**——扩展句里的词不许当锚。同一事件多锚并列，跨事件不硬并。
  - `seeds`：非空数组，出自 candidates 逐字——每条坑至少一句链回 seed，这是死约束；纯推断坑请走裁量（`anchors=[]`）。
  - `extra`：主题扩展数组，出自 sentences 逐字（可空）；每句为什么跟本事件走，写进 reason，半截话判不明的直接丢掉不收。
  - `why`：人话一句：代价是什么 + 关键原句短引（`原话“…”`短引须出自本条 `seeds+extra`）。
  - `how_to_avoid`：人话一句：动作＋条件（何波/何时/拿什么），只认视频口径，未提空出不脑补。
  - `reason`：一句话人话：为什么这几句合成一条、扩展句凭什么跟走（锚定条也要写；trap 在此论证“看着赚”）。
  - `inferred`：bool；锚定条填 false（警告锚定非推断，走绿），裁量条填 true（标黄待人点，永不进绿）。
  - take 系出局（通用，不点名）：有 take 系 verified 拿取（精确名 + 闭集拿取动词 take/buy/pick up/lock/get/roll for 原形/变形肯定式，无 n't/not/never/can't 等否定）一律不收为种子/extra，拿不是坑；ban 组不重复进（拒绝清单是 03 的事）。
    （#50：召回 seedpool 已按纯警告标记 + 情态约束过滤，take 出局由你提名时执行；extra 允许含 take 作解法证据，如 horde 波前合核弹，但不得以 take 本身为坑。）

## 好/坏例

- 坏：扩展句无 seed 可链还硬塞进锚定条；拿扩展句里的词当锚；把定位 spawn 句塞进 Peacock 坑（只因同含 spawn 就合并，事件不同）；`risky` 标 `trap` 却不写看着赚在哪；整句复制某条 quote 当 why。
- 好：141/142（投射物 spawning，无警告词）凭“与 143 的 mistake 同一站位事件”进站位坑 extra，reason 写清事件同一性；44（tree spawns 利好）纵在召回池也不收，reason 留剔除记录；88（peacock 上 27 级）进 Peacock 坑 extra 当“看着赚”的诱饵证据。

## 验收

- 机检：`wordings` 数组 ≥3；`severity` 合法；`seeds` 非空且全出自种子池逐字；`extra` 全出自 sentences 逐字且与 seeds 不交；`anchors` 每条在本条种子句里逐字出现；`quotes=seeds+extra` 原序、锚定条 `quotes[0]` 是种子；锚定条 `inferred=false`、裁量条 `true`；无 glass cannon；去重。
- 人看：抽 2 条，验合并讲得通（扩展真跟 seed 同一事件）+ 分级站得住（trap 必有“看着赚”论证）+ 人话可执行即过。
