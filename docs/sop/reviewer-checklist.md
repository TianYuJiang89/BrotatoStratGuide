# Reviewer 块级审稿清单（SOP 附录，#18 落地）

> 由 SOP §9 调用：第二道闸。drafter 写稿、reviewer 审稿（drafter 不审己稿）。
> 前提：交叉表格式见 #17（`data/mentions/<slug>__<variant-id>.json`，每变体独立跑，39术语+武器/道具逐个计数附原句，variant-id 为 covers slug 化）+ 覆盖制见 #20（`builds/<slug>.json` 内 `variants` 数组，每变体 `covers` + `label`，动态诚实标签）；
> 失败来源见 #14 批注（凭印象漏 Speed/Luck/Dodge，必须机器+块级双强制）。
> 人三问是第三道闸、最后一道闸；降级（放松 gate）须另开票，本清单不直接放宽。

## 0. 输入（只认三件套，不看 drafter 脑补）

* 字幕：`data/subs/<slug>__<variant-id>.en-orig.vtt`（每变体独立存，仅取证，专名已按 wiki 纠拼写）。
* 口径：`data/builds/<slug>.json` 内 `variants` 数组（每变体 `covers` + `label` + 独立 Top3+双标注+10段，旧单层键废除）。
* 交叉表：`data/mentions/<slug>__<variant-id>.json`（`build_mentions` 产物；每变体独立跑，variant-id 为 covers slug 化如 `ultimate-nightmare`，格式沿 #17）。
* 机检：`python scripts/check_mentions.py --slug <slug>` 输出（只 warn 不 fail；缺表/缺 build 才 FAIL，必须补；`--variant <id>` 可单变体）。

术语：档位=三档之一（Danger 5 / Nightmare / Ultimate）；变体=某角色某覆盖范围（单档或合讲多档）的整套打法（Top3+双标注+10段），同页不同源，tab 由证据驱动（动态诚实标签：有证据才出 tab，无证据不占位，合讲合并，单变体退覆盖徽章）；旧空档置灰废除。

## 1. 块级范围（10段×变体逐块过）

10段（不含取材版本，取材版本只查双标注与链接）：

1. `mechanism` 机制一句话
2. `attrs-primary` 核心属性·主 17
3. `attrs-secondary` 核心属性·次级 22
4. `weapons` 武器分档（T1/T2，把数不限，每把一句话只认视频口径）
5. `items` 关键道具（≥3，够复现）
6. `phases` 开局/中期/后期（含转向点 W1–5/W6–12/W13–20）
7. `upgrade` 升级优先级（Top3 两层，升级在前）
8. `shop` 商店优先级（Top3 两层）
9. `pitfalls` 避坑（只收通用会死人的错 1–3）
10. `hard` 高难特例（只收 Nightmare / Ultimate 变招）

每变体逐块过：单变体先按单表；多变体时每变体各跑各的交叉表、各出各的意见清单块，不许跨变体借口径。

## 2. 每块查三件事（逐块打勾/打叉）

对每一块（变体×段），只查五件事：

* ① 命中清零了没：把本块涉及的术语/武器/道具逐个对交叉表。`check_mentions` WARN 还有残留即未清零，打回（提到未定级→补定级；定级无命中→须已挂名注明标题/描述/chapters）。
* ② 每条 rating 有无出处：每条 S–F / 每把武器 / 每件道具，必须有出处二选一——字幕原句（交叉表 quotes）或标题/描述/chapters 注明（note/reason 含 标题/描述/出处/chapter/title/description 任一）。
* ③ 是观点小结还是单句充数/模具怪话：note 只有一句原话、无综合（拿几次/何时/真搭配/真取舍）的，或“与X冲突”无作者二选一依据的，或计数（字幕N次）泄漏进 note 的，均视为未清零，打回重写。
* ④ 有无无出处 rating：有定级但字幕无命中、又未注明标题/描述/chapters 者，视为疑为编，打回（须补出处或删定级改空出 `— / 作者未提及`）。
* ⑤ 数量/获取方式漏了没：武器 note 缺数量（原话有数字而 note 无数字/无总数/无目标阶），或升级/商店缺获取方式（只写拿什么不写怎么拿），打回补充。

只查以上五件事，不查版式、不重验排版（A 版式已冻结，带待补照发）。

## 3. 输出：意见清单（给 drafter 改）

reviewer 不直接改稿，只输出意见清单。格式（变体×段×项）：

* `[变体 Ultimate / attrs-primary / Speed C]` 无出处：字幕有命中但 note 无原话，建议补“拿过 9 点，评有点用”或注明标题/描述。
* `[变体 Ultimate / weapons / Wrench]` 通过：交叉表命中 6 次附原句，T1 有口径。
* `[变体 Nightmare / items / Coffee]` 命中未清零：字幕提到 2 次但未入库，须补定级或说明为何不收。

drafter 按清单改完，重跑 `build_mentions` + `check_mentions` + `build.py --slug` 全绿后再送审；改不动的在原单批段说明，不开新单。

## 4. 通过标准与移交

* 通过：10段×变体每块五件事全勾，无残留 WARN 无交代、无单句充数/模具怪话/计数泄漏、无无出处 rating。
* 移交：通过后送人三问（选片对不对/转述忠不忠实/评级违不违手感）；人三问不过，在原单批段，reviewer 清单追加一轮。
* 记录：reviewer 在逐角色单评论贴意见清单全文 + `check_mentions` 输出粘贴，drafter 回复改动点点对点闭环。
