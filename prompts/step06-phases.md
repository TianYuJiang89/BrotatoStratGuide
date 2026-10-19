# Step 06 — Phases 作者章节三问（B-段2，#45跟进+C，agent judgment）

你是阶段总结器（judgment 层）。只读相对路径，只写相对路径。禁 `..` 与绝对盘符。旧 SOP 只作参考，不作输入；旧链冻结不新增规则。

## 输入（cwd = `G:/brotato-work/<slug>/<variant>/`）

- `steps/06-phases/buckets.json`：代码已分桶（确定性），数组 N=章节数（cyborg 本例 N=8他例按实际，标题/顺序以 `inputs/meta.json chapters` 为准），每项 `{phase, waves, quotes[窗内全量保序去重不cap], quote_details}`。`quotes` 不许改写、不许增删、不许重排，你只写三问+可选窗外补。
- `steps/01-sentences/sentences.json`：全局召回池（C 用）。`extra_quotes` 必须逐字出自这里。
- `inputs/meta.json`：`chapters` timed 仅备查（章顺序/时间窗），不重切分。

## 输出（只写这一件）

- `steps/06-phases/wordings.json`：数组 N=章节数，与 buckets 一一对应，每项 `{phase, goal, focus, pivot, extra_quotes}`
  - `phase`：抄 buckets 同序章标题原文一字不差。
  - `goal`：人话一句：本章要达成的局面。必须综合本窗多条引文（只复读一条判负），点名具体机制/怪/武器，带关键原句短引（`原话“…”`短引须出自本窗 `quotes`，C 补的窗外句也可引但须注明窗外）。
  - `focus`：人话一句：配装/走位重心。必须可执行（拿什么/锁什么/何时转），原话数字不丢（几把/第几波/多少伤），带短引。
  - `pivot`：人话一句：到下一章的衔接条件（末章写收束复盘）。带短引。
  - `extra_quotes`：可选窗外补引用（C），`[]` 或多条（不限条数，须必要）。跨章串讲的关键句才补，且必须窗外（与窗内重复/窗内已收判负），逐字等于 `sentences.text`。无则 `[]`。空窗（`quotes==[]`）不补保持诚实空出。
  - 禁模具话：`按本章节奏来/衔接点/不编数字` 单独出现判负；禁计数泄漏（`字幕N次`不进文案）；禁整句复制某条 quote（小结必须 ≠ 任何一条原文）。

## 好/坏例（坏=旧模板，禁止）

- 坏：`本章（X）作者打法：{Q0}…原话“{Q0}…”`（只复读一条）、`配装/走位重心按本章节奏来`（无动作）、`转向下一章衔接点`（无条件）。
- 好（Late-game progression）：`goal：peacock波+30%伤别刷出mini boss堆优先清enhanced vampire squids，nuke launcher是解；原话“…peacock wave…”` / `focus：nuke launcher清场+补life steal站桩…；原话“…nowhere to hide…”` / `pivot：留血量和结构进Final boss，whale先杀；原话“…whale boss first…”` + `extra_quotes` 可补窗外的转换机制句并标窗外。

## 验收

- 机检：`wordings` N=章节数、phase 对齐；非空段三问≥8字、非整句复制、短引出自本窗（窗外引须在 `extra_quotes` 内）；`extra_quotes`、逐字对句、须真在窗外；空段照抄固定句且 `extra_quotes==[]`。
- 人看：抽1打法章验综合多条+可执行+人话即过；有窗外补的加抽1条验窗外必要性。
