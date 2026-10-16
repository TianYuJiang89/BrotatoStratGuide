# 新增角色攻略 SOP（显式调用版）

> 为无记忆 LLM session 设计：新 session 不靠记忆恢复共识，靠显式读本文件 + 引用已关票决议。
> 对应 map 决议见 [Brotato 角色 HTML 攻略制作体系：思路→模板→流程](https://github.com/TianYuJiang89/BrotatoStratGuide/issues/1)。
> 本文件是 [《新增角色流程：从选视频到发布 HTML 的复用步骤》](https://github.com/TianYuJiang89/BrotatoStratGuide/issues/6) 的决议资产（Q1–Q4 已锁），先落 `docs/sop/` 跑通 1–2 个角色，跑顺再包成正式 skill。

## 0. 调用约定

* 人显式说“按 SOP 做 XX 角色攻略”（如“按 SOP 做工程师”），agent **先读本文件全文**，再读其引用的四票决议链接，不靠猜。
* 全链机器跑，人只做三件事：**报角色名、选定候选视频、验收样章**。人不手改产物。

## 1. 前置决议（固定，不重议）

* 取材：[《取材规范：Cephalopocalypse 视频如何选、引、转述》](https://github.com/TianYuJiang89/BrotatoStratGuide/issues/2) — Ultimate > Nightmare Guide > Nightmare > Danger 5 保底；五元组 + 发布日期双标注；转述只留可复现骨架。
* 基线：[《角色与术语基线：收录清单与中英对照表来源》](https://github.com/TianYuJiang89/BrotatoStratGuide/issues/3) — 64 = 本体 50 + Abyssal 14；中文以客户端简中为准；`data/roster.json` + `data/terms.csv` 约定（本 SOP 按次级 22 执行，基线票的“次级只收 3”作废）。
* 版式：[《页面模板原型：一页一样式，多方案可点》](https://github.com/TianYuJiang89/BrotatoStratGuide/issues/4) — A 长文式胜出，B/C 冻结；`prototype/page-variants` 仅 demo。
* 内容：[《内容结构定版：统一栏目的取舍与写法》](https://github.com/TianYuJiang89/BrotatoStratGuide/issues/5) — 10 段锁死不改序、无口径诚实空出；主 17 + 次级 22 全量两表 + 单源复用；T1/T2 把数不限；验收线已定。

## 2. 交互（SOP 第 3–4 步）

1. 问人：要建哪个角色的攻略？
2. 人回答（如“工程师”）后，按 `data/roster.json` 归一化 `en/zh/slug/dlc`（如 `Engineer/工程师/engineer/本体`）。DLC 角标、Crash Zone 后缀原样保留。roster 无此名则诚实告知，不编。Mod（无 Steam App + 无游戏文件 + 无 wiki 主表）直接拒收。

## 3. 选片候选（SOP 第 5 步，Q2=A 锁死）

* 范围：`https://www.youtube.com/@Cephalopocalypse` 全频道同角色检索。
* 优先级：Ultimate > Nightmare Guide > Nightmare > Danger 5 保底。Tier List / Challenge / Random-Random / Batomon 只作补充不作主候选。Crash Zone 须保留地图后缀。
* 输出 Top 3，每项：标题链接 + 视频 ID + 发布日期（RSS/单视频 `upload_date`）+ 难度标签 + 有无自动字幕（`en-orig`）。无 Nightmare-era 只有 Danger 5 则照给但标 `版本较老`。零命中回“无可用主引用，建议换角色/待补”，不编。
* 字幕缺失不否决候选，但标 `无字幕`（本 SOP 只做 1+2，见 §4，无字幕即该候选降级）。

## 4. 视频信息抽取（SOP 第 6 步前半，Q3=只做 1+2 锁死）

只做两件事，不做其他：

1. **元数据**（`yt-dlp --print` 单视频）：标题 / 时长 / `upload_date` / 描述 / `chapters`。描述版本号（如 `1.1.15.1`）偶有，不单信；一律发布日期 + Steam 版本双标注。chapters 对开局/中期/后期分段。注：列表页 `description/upload_date` NA 不可靠，必须逐个单视频抓（已实测）。
2. **自动字幕**（`yt-dlp --write-auto-sub --sub-langs en-orig --sub-format vtt --skip-download`）：存 `data/subs/<slug>.en-orig.vtt`。该频道实测只有自动字幕、无手动字幕；专名误听多（如 Brotato→Bart），必须对照 wiki 纠拼写，不照抄。

明确不用：音频拉回 Whisper 重转写、画面帧 OCR/视觉抽取、全视频多模态理解、YouTube Data API、第三方转写服务。字幕缺失不转听译、不看画面猜，该候选降级或标待补。

## 5. 开逐角色 issue（SOP 第 6 步后半）

人点头选定 1 个候选后，agent 开 GitHub issue（标题如 `角色攻略：工程师 (Engineer)`），正文含：

* `Part of #1`（子票回退行，无 sub-issues 时用）。
* 目标角色（roster 行）+ 选定取材五元组 + 双标注位。
* 执行步骤（锁死，执行 agent 照做）：
  1. 抓 §4 的 1+2，入库 `data/subs/<slug>.*`。
  2. 只基于字幕 + 标题/描述/chapters 写可复现骨架：核心属性优先级、武器 T1/T2、关键道具 3–5、开局/中后期转向、商店/升级 Top3、避坑 1–3。不逐波复述、不翻口播原文、不搬截图。
  3. 诚实填写模板（10 段见 §6）：无口径写 `— / 作者未提及`，中文 `中文 (English)`，DLC 角标，S–F 上色。不编把数、不脑补评级、不自造中文、不藏空段。
  4. 跑 `python scripts/build.py --slug <slug>` 生成 `docs/<slug>.html`（人绝不手改 `docs/`，见 §7）。机检全绿再提 PR/推分支。
* 禁止事项（同上 §5.3）。
* 模板用 `docs/sop/character-issue-template.md` 原样填。

## 6. 内容模板（固定抄写，不重议）

顺序锁死：机制一句话（含解锁/胜场奖励）→ 核心属性·主 17 → 核心属性·次级 22 → 武器 T1/T2（表+图标，把数不限）→ 关键道具（表：道具｜推荐理由）→ 开局/中期/后期（首句括号 W1–5/W6–12/W13–20，含转向点）→ 升级优先级 → 商店优先级 → 避坑 → 高难特例 → 取材版本（链接+ID+发布日期+难度+游戏版本双标注）。
验收线：机制一句话 + 属性 S/A 有口径 + 武器 T1 ≥1 + 道具 ≥3 + 阶段转向点 + 商店/升级 Top3 + 原视频链接 + 版本双标注；缺项标 `待补口径` 但可发布。

## 7. 单源与机器链（Q1=A + 机器前提，编码为固定约束）

* `data/roster.json`（64，`id/en/zh/dlc`）+ `data/terms.csv`（主 17 + 次级 22 全量，`en,zh,type,dlc,source_version`）+ `data/wiki-cache.json`（排序/图标/悬浮 Notable Items）+ `data/builds/<slug>.json`（每角色视频口径）为唯一可改源码；`templates/character.html` 为 A 版空壳；`docs/<slug>.html` + `docs/index.html` 为构建产物，git 跟踪但人绝不手改。
* 命令：`python scripts/build.py --all` / `--slug <slug>`；另 `scripts/check_updates.py`（Steam `1942280` dlc 数组 + Fandom `Characters` 表 `bt-dlc` 数量 + 取材日期 vs 大更新）命中即挂 `待重审`。Primal Dread 走追加，本轮 64 不动。
* 机检：10 段齐全不改序、行数/排序/图标非空、链接/DLC 角标/术语写法错即 fail；验收线缺项则 warn + `待补口径` 徽标但不 fail。

## 8. 人验与 promo（SOP 第 8 步，Q4=A 锁死）

* 机检已绿后人才看，只看三问：选片对不对、转述忠不忠实、评级违不违手感。
* 三问全过 = promo（去草稿标记，索引置可点，关 issue）；任一不过 = 在 issue 里批注具体段，执行 agent 按批改，不开新 issue。
* 排版/手机可读不重验（A 版式已冻结）。
