# 新增角色攻略 SOP（显式调用版）

> 为无记忆 LLM session 设计：新 session 不靠记忆恢复共识，靠显式读本文件 + 引用的已关票决议。
> 对应总规见 [#8](https://github.com/TianYuJiang89/BrotatoStratGuide/issues/8)
> （思路→模板→流程方法论见 map
> [#1](https://github.com/TianYuJiang89/BrotatoStratGuide/issues/1)，雾已清）。
> 本文件是 #14 流程落地的手册资产：先落 `docs/sop/` 跑通 1–2 个真角色，跑顺再包成正式 skill。

## 0. 调用约定

* 人显式说“按 SOP 做 XX 角色攻略”（如“按 SOP 做工程师”），agent **先读本文件全文**，再读其引用的决议（#8 Solution / Implementation Decisions），不靠猜。
* 全链机器跑，人只做三件事：**报角色名、选定候选视频、验收样章**。人不手改产物。

## 1. 前置决议（固定，不重议）

* 总规：[#8](https://github.com/TianYuJiang89/BrotatoStratGuide/issues/8) — 0 会话协作 + 1 收录基线 + 2 取材规范 + 3 内容模板 + 4 页面模板 + 5 单源机器链 + 6 资源策略。
* 取材：#8 §2 — `https://www.youtube.com/@Cephalopocalypse` 全频道同角色检索；Ultimate > Nightmare Guide > Nightmare > Danger 5 保底；有 Guide 后缀才算教学局；Tier List / Challenge / Random-Random / Batomon 只作补充不作主候选；Crash Zone 须保留地图后缀；五元组 + 发布日期双标注；转述只留可复现骨架。
* 基线：#8 §1 — 64 = 本体 50 + Abyssal 14；中文以客户端简中为准；`data/roster.json`（`id/en/zh/dlc`）+ `data/terms.csv`（主 17 + 次级 22 全量，旧次级 3 口径作废）。
* 版式内容：#8 §3–4 — A 长文式胜出，B/C 冻结；10 段锁死不改序、无口径诚实空出；主 17 + 次级 22 全量两表 + 单源复用；验收线已定。
* 机器链：#9 骨架（`--slug` / `--all` 双粒度，产物人不手改）→ #10 单源重渲染（缺段改序 fail，缺验收线 warn + 待补徽标）→ #11 索引全能力（搜索 + 筛选 + 仅看可点，覆盖 64，头像热链 + 占位回落）→ #12 图标版权页脚（ 三处同一函数，有图三件套、无图占位，页脚署名 + 原页链 + 双链，应急平时空）→ #13 取材巡检（Top3 + 双标注 + 待重审/资源待重审/待补徽标）→ #15 武器道具悬浮（wiki 本体信息 + 中英对照）。

## 2. 交互（人只做三件事之一：报角色名）

1. 问人：要建哪个角色的攻略？
2. 人回答（如“工程师”）后，按 `data/roster.json` 归一化 `en/zh/slug/dlc`（如 `Engineer/工程师/engineer/本体`）。DLC 角标、Crash Zone 后缀原样保留。roster 无此名则诚实告知，不编。Mod（无 Steam App + 无游戏文件 + 无 wiki 主表）直接拒收。

## 3. 选片候选（人只做三件事之二：选定候选）

* 范围：`https://www.youtube.com/@Cephalopocalypse` 全频道同角色检索。
* 优先级：Ultimate > Nightmare Guide > Nightmare > Danger 5 保底。Tier List / Challenge / Random-Random / Batomon 只作补充不作主候选。Crash Zone 须保留地图后缀。
* 输出 Top3（1 主 + 不超 2 补充），每项：标题链接 + 视频 ID + 发布日期（RSS/单视频 `upload_date`，`YYYY-MM-DD`）+ 难度标签（只认 Danger 5 / Nightmare / Ultimate）+ 有无自动字幕（`en-orig`）。主须等于 `candidates[0]` 五元组。无 Nightmare 时代只有 Danger 5 则照给但标 `版本较老`。零命中回“无可用主引用，建议换角色/待补”，不编。
* 字幕缺失不否决候选，但标 `无字幕`（只做 §4 的 1+2，无字幕即该候选降级或待补）。

## 4. 视频信息抽取（抽取：只做 1+2）

本节是三段式第一段：抽取（抽取→交叉表清零→填表，详见 §5–§7）。只做两件事，不做其他：

1. **元数据**（`yt-dlp --print` 单视频）：标题 / 时长 / `upload_date` / 描述 / `chapters`。描述版本号（如 `1.1.15.1`）偶有，不单信；一律发布日期 + Steam 版本双标注。chapters 对开局/中期/后期分段。注：列表页 `description/upload_date` NA 不可靠，必须逐个单视频抓。
2. **自动字幕**（`yt-dlp --write-auto-sub --sub-langs en-orig --sub-format vtt --skip-download`）：存 `data/subs/<slug>__<variant-id>.en-orig.vtt`（每变体独立存，构建不读，仅取证；variant-id 为 covers slug 化，如 `ultimate`、`ultimate-nightmare`、`danger-5`）。该频道实测只有自动字幕、无手动字幕；专名误听多（如 Brotato→Bart），必须对照 wiki 纠拼写，不照抄。

Cookie 协作（单视频被风控 `Sign in to confirm you're not a bot` / `DPAPI 10927` 时）：人用 `Get cookies.txt LOCALLY` 只导出 `youtube.com` 存仓库根 `cookies.txt`（已进 `.gitignore`，不入库不贴原文），agent 跑 `yt-dlp --cookies cookies.txt ...` 同命令取数；失效（`Could not copy / Failed to decrypt / LOGIN_REQUIRED`）agent 提示人重出，不换 Data API/第三方转写，gate 不变。

明确不用：音频拉回 Whisper 重转写、画面帧 OCR/视觉抽取、全视频多模态理解、YouTube Data API、第三方转写服务。字幕缺失不转听译、不看画面猜，该候选降级或标待补。

## 5. 交叉表机器 gate（清零：抽取→交叉表清零→填表之二）

大黑箱拆细（#14 失败批注：旧 §5②+§6 单步凭印象漏 Speed/Luck/Dodge，必须机器强制）。本节是三段式第二段：交叉表清零。

* 格式先定（子票「交叉表脚本与机检」#17 已定 + 「多难度 tab 原型」#20 已定覆盖制）：脚本扫字幕×39术语+注册表武器/道具名，逐个命中计数并附原句；输出落 `data/mentions/<slug>__<variant-id>.json`（每变体独立跑，variant-id 为 covers slug 化，如 `ultimate`、`ultimate-nightmare`、`danger-5`，格式沿 #17，原则不变：每变体清零）。VTT 解析按空行分块，丢时间戳/序号/WEBVTT/NOTE/STYLE，去 HTML 标签，每块一句原句（cap 500字，quotes cap 10）。
* 数据模型（#20 决议：A 胜出 + 动态诚实标签）：`data/builds/<slug>.json` 内 `variants` 数组，每变体自带 `covers` + 显示名 `label` + 独立 Top3+双标注+10段；tab 按数组渲染，有几个渲染几个；旧单层键与固定三 key 废除。排序按最高难度从高到低（Ultimate > Nightmare > Danger 5）；标签用全名（Danger 5，不用 D5）。同一视频合讲多档则合并为一个变体（如 Ultimate + Nightmare，内容/取材/交叉表只跑一份）；资料源只讲 Danger 5 就只出 Danger 5。单变体退化为覆盖徽章，不留单 tab 栏。tab 为 A 方案 sticky 分段独占切换（APG tablist：箭头/Home/End，44px 触区，横滑，vanilla JS 离线可用，页内首个 JS）。
* 命令：`python scripts/build_mentions.py --slug <slug>` / `--all` 建全部分块（`--variant <id>` 单变体）；`python scripts/check_mentions.py --slug <slug>` / `--all` 机检（`--variant <id>` 单变体）。`check_mentions` 只 warn 不 fail，不动现有 `check.py` 门禁；缺表/缺 build 才 FAIL（gate 未跑必须补）。
* 清零定义（drafter 自清，reviewer 复查）：① 提到未定级（count>0 但无 S–F/武器不在 T1+T2/道具不在列）→ 补定级；② 定级无命中（有定级但 count==0）须挂名注明出处是标题/描述/chapters（note/reason 含 标题/描述/出处/chapter/title/description 任一），否则疑为编 WARN。清零后 `check_mentions` 仍 warn 可发布，但必须逐条有交代，不许凭印象空出。
* 一事一过（注意力回收）：填表按 §7 分步表逐段独立过，每段只做一件事——先把该段涉及的全部证据列全（交叉表该段全部 quotes + 标题/描述/chapters 相关处），再写小结定级，跑完本段机检（`build_mentions` + `check_mentions` + `build.py --slug`）再进下一段；不许全表一批过。note 必须是观点小结（多证据综合：拿几次/何时拿/真搭配/真取舍），只写真实存在的搭配与取舍，没有就不写，禁止为填槽编造“与X冲突”；“冲突”仅当作者明确二选一（ban/卖掉/roll掉/明确说不要）才写。计数（字幕N次）只活在 mentions JSON 与 issue 交单，不进 note/页面；note 只留结论 + 一句人话理由 + 关键原句短引。单句原话贴充数、模具怪话（无依据的配/冲突、计数泄漏）均视为未清零，reviewer 打回。
* 术语：档位=三档之一（Danger 5 / Nightmare / Ultimate）；变体=某角色某覆盖范围（单档或合讲多档）的整套打法（Top3+双标注+10段），同页不同源，tab 由证据驱动（动态诚实标签：有几份证据做几个变体，有证据才出 tab，无证据不占位；同一视频合讲多档则合并为一个变体如 Ultimate + Nightmare；单变体退化为覆盖徽章即 coverbadge，不留单 tab 栏；标签全名 Danger 5，排序按最高难度从高到低 Ultimate > Nightmare > Danger 5）；旧空档置灰废除，被动态诚实标签取代。

## 6. 开逐角色单（模板原样填）

人点头选定 1 个候选后，agent 开 GitHub issue（标题如 `角色攻略：工程师 (Engineer)`），正文用 `docs/sop/character-issue-template.md` 原样填，含：

* `Part of #8`（子票回退行）。
* 目标角色（roster 行）+ 选定取材五元组 + 双标注位。
* 执行步骤（锁死）：① 抓 §4 的 1+2（抽取）；② 跑 §5 交叉表并清零（`build_mentions` 建表 + `check_mentions` 自清，提到未定级补定级、定级无命中挂名注明标题/描述/chapters）；③ 只基于字幕 + 标题/描述/chapters + 交叉表写可复现骨架（核心属性优先级、武器 T1/T2、关键道具、开局/中后期转向、商店/升级 Top3、避坑 1–3，不逐波复述、不翻口播原文、不搬截图）并诚实填 10 段（见 §7 填表）；④ 跑构建（见 §8），人不手改 `docs/`，机检全绿再分支；⑤ 过 reviewer 块级 gate（见 §9，drafter 不审己稿）后再送人三问。
* 禁止事项：不编把数与评级、不自造中文、不藏空段、不把娱乐局当主引用、后缀保留。

## 7. 内容模板（填表：固定抄写，不重议）

顺序锁死：机制一句话（含解锁/胜场奖励）→ 核心属性·主 17 → 核心属性·次级 22 → 武器分档（表 + 图标，把数不限）→ 关键道具（表：道具｜推荐理由）→ 开局/中期/后期（首句括号 W1–5/W6–12/W13–20，含转向点）→ 升级优先级 → 商店优先级（升级在前）→ 避坑 → 高难特例 → 取材版本（链接 + ID + 发布日期 + 难度 + 游戏版本双标注）。

* 武器把数不限，每把一句话（为什么 + 拿几把/升到几阶/与谁配比 + 什么波次拿换），原话里的数字（几把/第几把/几阶/总数）一个不丢；同名多把必须写总数（如 4 把螺丝刀 + 1 加特林）；只认视频口径，未提空出不脑补；避雷不单列，进避坑。
* 道具下限弹性：本质够复现，不硬卡 5；验收线至少 3 件，3–5 件均可，照单抓取能复现作者思路即可。
* 商店与升级两层写法：先属性优先级 Top3，再点名 2–3 件必拿必刷；每项必须注明怎么拿（直购/转化白嫖/任务送/商店刷），只写“拿什么”不写“怎么拿”视为未清零；升级在前商店在后。
* 避坑只收通用会死人的错（1–3 条）；高难特例只收 Nightmare / Ultimate 才成立的变招。
* 验收线：机制一句话 + 属性 S/A 有口径 + 武器 T1 ≥1 + 道具 ≥3 + 阶段转向点 + 商店/升级 Top3 + 原视频链接 + 版本双标注；缺项标 `待补口径` 但可发布。
* 提过即算口径：视频里明确拿过/roll 过/ban 过的属性都算口径，必须定级；顺手拿一次、备选后放弃的给 C 并写明原话（如“拿过 9 点，评有点用”），不写 `—`；只有全程没出现过的才空出（`— / 作者未提及`）。
* 分步表（一事一过，每步独立产出+验收，不许跳步）：
  1. 核心属性·主→输入：交叉表 terms 主 17 全 quotes；产出：段首 S/A 一览一句（drafter 填，不进机检）+ 每项 rating+观点小结 note；验收：`check_mentions` 本段无提到未定级 + `build.py --slug` 绿。
  2. 核心属性·次级→输入：terms 次级 22 全 quotes；产出/验收同上。
  3. 武器分档→输入：weapons 全 quotes + 把数/波次上下文；产出：T1/T2 表（每把 note 含为什么+数量配比/目标阶+何波拿换，原话数字不丢）；验收：T1 ≥1 有口径 + 机检绿。
  4. 关键道具→输入：items 全 quotes；产出：道具表（每件 reason 观点小结）；验收：≥3 件 + 机检绿。
  5. 开局/中期/后期→输入：chapters + 阶段相关 quotes；产出：三段（首句 W1–5/W6–12/W13–20 括号+转向点）；验收：三段齐 + 转向点明确 + 机检绿。
  6. 升级优先级→输入：升级相关 quotes；产出：Top3 先行 + 每项怎么拿 + 点名；验收：Top3 有口径 + 每项有获取方式 + 机检绿。
  7. 商店优先级→输入：商店/reroll 相关 quotes；产出：Top3 + 每项怎么拿 + 2–3 件必拿；验收：同上 + 升级在前。
  8. 避坑/高难→输入：死亡/失误/变招 quotes；产出：避坑 1–3 + 高难变招；验收：只收通用会死人的错/只收高难成立招 + 机检绿。
* 每条 rating 必须有出处：观点小结（多证据综合，真搭配/真取舍，无则不写）+ 关键原句短引或标题/描述/chapters 注明，不贴计数；无出处 rating 视为疑为编，单句贴充数/模具怪话视为未清零，reviewer 块级必打回（详见 `docs/sop/reviewer-checklist.md`）。

## 8. 单源与机器链（产物人不手改，机检全绿再分支）

* 唯一可改源码：`data/roster.json`（64）+ `data/terms.csv`（主 17 + 次级 22）+ `data/wiki-cache.json`（注册表唯一 URL 源，不存二进制，构建时内联）+ `data/builds/<slug>.json`（每角色视频口径 ratings）；`templates/character.html` 为 A 版空壳；`docs/<slug>.html` + `docs/index.html` 为构建产物，git 跟踪但人绝不手改。
* 命令（产物人不手改，只改源码重构建）：
  `python scripts/build.py --slug <slug>` / `--all`；
  `python scripts/check.py docs/<slug>.html`（段序 + 术语全量角标排序图标 + 取材门禁）；
  `python scripts/check_updates.py`（Steam `1942280` dlc 数组 + Fandom `Characters` 表 `bt-dlc` 数量 + 取材日期 vs 大更新，命中即挂 `待重审`，人工触发复核）；
  `python scripts/check_resources.py`（注册表 + 应急空目录，`--live` 全量 HEAD 挂资源待重审）；
  `python scripts/build_mentions.py --slug <slug>` / `--all` + `python scripts/check_mentions.py --slug <slug>` / `--all`（交叉表机器 gate，只 warn 不 fail，不动 `check.py` 门禁）；
  `python -m pytest -q`；`mypy scripts/build.py scripts/check.py scripts/check_updates.py scripts/build_mentions.py scripts/check_mentions.py`。
* 机检：10 段齐全不改序、行数/排序/图标非空、链接/DLC 角标/术语写法错即 fail；取材难度非三档 / 娱乐局进候选 / 超 3 / 主候选不一致 / 链接错 / 日期非法 / 抽取含 frames-multimodal 即 fail；验收线缺项则 warn + `待补口径` 徽标但不 fail。Primal Dread 走追加，本轮 64 不动。
* 资源：默认热链 wiki 缩略图（小规格，不用原图），每个图片三件套（替代文本 + 宽高 + 缩略图源 + 原文件标记 + 应急路径 + 懒加载 + 无来源引用 + 失败移除）；断网回落占位仍可读；应急目录平时空，连续 7 天大面积 404 才人工切 `--use-local-assets`。

## 9. 三道闸：机器 gate + reviewer 块级审 + 人验三问（人只做三件事之三：验收三问）

* 三道闸顺序锁死：① drafter 按 §5 自清零（交叉表机器 gate）；② reviewer 按 `docs/sop/reviewer-checklist.md` 块级审（10段×变体逐块查，输出意见清单给 drafter 改）；③ 人才看三问：选片对不对、转述忠不忠实、评级违不违手感。reviewer 是第二道闸，人三问退为第三道闸、最后一道闸。
* drafter 不审己稿（写稿与审稿必须两人/两角色分离，单人执行时隔日重审亦视为自审，仍须换人）；降级（放松 gate）须另开票，本 SOP 不直接放宽。
* 三问全过 = 发布（去草稿标记，索引置可点，关 issue）；任一不过 = 在 issue 里批注具体段，执行 agent 按批改，不开新 issue。
* 带待补照发，排版不重验（A 版式已冻结，手机可读不重验）。
