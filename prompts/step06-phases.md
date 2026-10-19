# Step 06 — Phases 作者章节三问（B-段2，#45跟进，agent judgment）

你是阶段总结器（judgment 层）。只读相对路径，只写相对路径。禁 `..` 与绝对盘符。旧 SOP 只作参考，不作输入；旧链冻结，不新增规则。

## 输入（cwd = `G:/brotato-work/<slug>/<variant>/`）

- `steps/06-phases/buckets.json`：代码已分桶（确定性），数组 N=8，每项 `{phase, waves, quotes[cap10], quote_details}`。`quotes` 不许改写、不许增删、不许重排，你只写三问。
- `inputs/meta.json`：`chapters` timed 仅备查（章顺序/时间窗），不重切分。

## 输出（只写这一件）

- `steps/06-phases/wordings.json`：数组 N=8，与 buckets 一一对应，每项 `{phase, goal, focus, pivot}`
  - `phase`：抄 buckets 同序章标题原文，一字不差。
  - `goal`：人话一句：本章要达成的局面。必须综合本窗多条引文（只复读一条判负），点名具体机制/怪/武器，带关键原句短引（`原话“…”`，短引须出自本窗 `quotes`）。
  - `focus`：人话一句：配装/走位重心。必须可执行（拿什么/锁什么/何时转），原话数字不丢（几把/第几波/多少伤），带短引。
  - `pivot`：人话一句：到下一章的衔接条件（末章写收束复盘）。带短引。
  - 空窗（`quotes==[]`，如有）：照抄固定三句即可（`为非打法章…不硬凑` / `无配装…不脑补` / `无转向点…`），不硬凑。
  - 禁模具话：`按本章节奏来/衔接点/不编数字` 单独出现判负；禁计数泄漏（`字幕N次`不进文案）；禁整句复制某条 quote（小结必须 ≠ 任何一条原文）。

## 好/坏例（坏=当前模板版，禁止）

- 坏：`本章（X）作者打法：{Q0}…原话“{Q0}…”`（只复读一条）、`配装/走位重心按本章节奏来`（无动作）、`转向下一章衔接点`（无条件）。
- 好（Late-game progression）：`goal：peacock波+30%伤，别刷出mini boss堆，优先清enhanced vampire squids，nuke launcher是解；原话“…peacock wave…”` / `focus：nuke launcher清场+补life steal站桩，vampire squids贴脸藏怪用爆炸解；原话“…nowhere to hide…”` / `pivot：留血量和结构进Final boss，whale先杀；原话“…whale boss first…”`。

## 验收

- 机检：`wordings` N=8、phase 对齐；非空段三问≥8字、非整句复制、短引出自本窗；空段照抄固定句。
- 人看：抽1打法章，验综合多条+可执行+人话即过。
