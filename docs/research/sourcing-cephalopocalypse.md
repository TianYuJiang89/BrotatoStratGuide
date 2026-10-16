# 取材规范研究：Cephalopocalypse 视频如何选、引、转述

对应票：`取材规范：Cephalopocalypse 视频如何选、引、转述`（Part of #1，AFK research）

> 本文件是一手来源调研的落点，供内容模板与新增角色流程直接引用。结论先行，证据在后。

## 结论（可直接写进流程）

### 1. 选片优先级（同一角色有多支视频时）

1. `Brotato Ultimate Nightmares Guide` — 当前最高地狱难度，优先用最高（符合 standing preference）。
2. `Brotato Nightmare Guide` — 现行主力教学向，有 `Guide` 后缀才算教学局。
3. `Brotato Nightmare`（无 `Guide` 后缀的完整 run）— 可作主引用，但需在攻略中注明“实况复盘，非教学局”。
4. `Brotato Danger 5`（含 `Random / Random`）— 仅作**保底**：当该角色无任何 Nightmare-era 视频时可用，必须在页内标注 `版本较老（Danger 5 时代）`。

`Danger 5 保底`即第 4 条的底线含义：不能用低于 Danger 5 的视频（如普通 Danger 0–4、娱乐局）作为主引用。

### 2. 不作主引用的类型（只可作补充或排除）

- `Tier List`（如 `Extremely Detailed Brotato Class Tier List for Nightmare - Part 1/2/3`）：综述向，不含单角色可复现 build，不作主引用。
- `Challenge Run` / `Random / Random` / `Batomon Showdown Ranked`：变体娱乐局（如 `WORST WEAPON CHALLENGE - Ranger`，`Batomon Showdown Ranked`），只可作“上限/花活”补充，不可作主 build。
- `Crash Zone`：标题中出现即地图变体（如 `Sailor Crash Zone - Brotato Nightmare Guide`），引用时必须原样保留地图后缀，不可与默认图混用。
- 非 Brotato 视频（BG3 / Mechabellum / Slay the Spire 2 等）：直接排除。

### 3. 标题结构（选片时的解析规则）

实测标题范式（742 支 Brotato 视频统计）：

```text
<HOOK> - <Character> [Weapon/Build] - Brotato <Difficulty> [Guide|Challenge Run|Random / Random]
```

- `<Character>` 紧跟第一个 ` - ` 之后，是选片键（如 `Glutton`、`Fisherman Spiky Shield`、`Sailor Crash Zone`）。
- `<Difficulty>` 只取三档：`Danger 5` / `Nightmare` / `Ultimate Nightmares`，大小写以原标题为准。
- 有无 `Guide` 后缀决定是否为教学局（见优先级）。

### 4. 合格引用格式（每页必备）

每角色页至少 1 个主引用，另可列 ≤2 个补充引用。主引用必须包含五元组：

```markdown
- 主取材：[CHAIN REACTION - Glutton - Brotato Nightmare Guide](https://www.youtube.com/watch?v=Jud6a0Vl2P4)
  - 视频 ID：`Jud6a0Vl2P4` / 发布：2026-10（RSS 实测近期日更，见证据） / 难度：Nightmare Guide / 角色：Glutton
  - 适用游戏版本：Abyssal Terrors DLC 后（以攻略编写时 Steam 当前版本为准，见 §5）
```

无符合优先级视频时，宁可空缺待补，不降级引用娱乐局。

### 5. 版本漂移处理（标题不打版本号时的替代方案）

- 一手实测：单视频 watch 页当前会被 YouTube bot 墙拦截（`Sign in to confirm you're not a bot`），`yt-dlp --flat-playlist` 的 `description` / `upload_date` 字段返回 `NA`，**不可依赖自动抓取描述里的版本号**。
- 替代键：以 RSS 的 `published` 日期为准（`https://www.youtube.com/feeds/videos.xml?channel_id=UCieQlcvyyk5208GxlVU43Rg`），攻略页写 `取材视频（YYYY-MM-DD）`。
- 游戏侧以 Steam 为准：`Brotato - Abyssal Terrors` 为 DLC（App `2868390`，见 Steam 商店页 `Brotato + Abyssal Terrors DLC Bundle`），攻略页另写 `适用版本：<Steam 当前版本号 / DLC 有无>`。
- 大更新后重审的触发条件留给 map 的雾区（版本漂移维护），本规范只要求：每次复用流程必须核对“视频发布日期是否早于最近一次大更新”，早于则标 `待重审`。

### 6. 转述粒度（转述非搬运）

只记录可复现骨架，不逐波复述录像：

- 必含：核心属性优先级、推荐武器 T1/T2、关键道具 3–5 件、开局/中/后期转向点、商店与升级优先级、避坑 1–3 条。
- 不含：逐波站位/掉落流水账、原视频口播原文翻译、截图/原片搬运。
- 中文正文，术语保留中英对照（如 生命窃取 (Life Steal)），对照表以术语基线票为准。

## 证据（一手来源）

1. 频道身份与更新节奏
   - 频道：`https://www.youtube.com/@Cephalopocalypse`，`og:url` 为 `https://www.youtube.com/channel/UCieQlcvyyk5208GxlVU43Rg`（`ceph_about.html` 实测）。
   - 简介：`New videos daily at 10AM Eastern!`（about 页 `og:description`）。
   - RSS：`https://www.youtube.com/feeds/videos.xml?channel_id=UCieQlcvyyk5208GxlVU43Rg`，2026-10-15/16 仍日更（如 `COMPLETE Extremely Detailed Brotato Class Tier List for Nightmare - Part 3`，`published>2026-10-16T14:00:28+00:00`，videoId `I--gtqaCtQI`）。

2. 标题范式与难度分代（`yt-dlp --flat-playlist` 全频道 1592 条，Brotato 742 条）
   - `Danger 5`：547 条（如 `BAG: STILL BROKEN - Cryptid Lute - Brotato Danger 5 Random / Random`）——旧时代基线。
   - `Nightmare`：156 条，其中 `Nightmare Guide` 46 条（如 `CHAIN REACTION - Glutton - Brotato Nightmare Guide`）——现行教学主力。
   - `Ultimate Nightmares`：40 条（如 `This Character is Actually Invincible - Golem - Brotato Ultimate Nightmares Guide`）——当前最高。
   - `Crash Zone`：5 条（如 `SMOOTH SAILING In Choppy Waters - Sailor Crash Zone - Brotato Nightmare Guide`）——地图变体后缀。
   - `Challenge Run`：4 条，`Batomon Showdown Ranked`：3 条 —— 娱乐/变体，不作主引用。

3. 版本标注位置的反证据
   - `yt-dlp --print "%(description)s"` 对 flat-playlist 返回 `NA`；单视频详情被 `Sign in to confirm you're not a bot` 拦截；watch 页 curl 仅返回关联视频 sidebar 中的 `Danger 5`（如 RogueBrothers 的 `21 Tips and Tricks to MASH Brotato!`），无本视频 `shortDescription`。结论：不可假设“描述里一定有版本号”，必须用发布日期 + Steam 版本双标注。

4. 游戏与 DLC 身份（Steam 一手）
   - `https://store.steampowered.com/app/1942280/Brotato/` 页内含 `Brotato - Abyssal Terrors`（App `2868390`）与 `Buy Brotato + Abyssal Terrors DLC Bundle`（Bundle `46233`）。DLC 与本体分开计费，攻略页必须区分适用版本。

## 待后续票确认（不阻塞本规范）

- 术语对照 canonical 来源（交由`角色与术语基线：收录清单与中英对照表来源`）。
- 内容模板每栏写多深（交由原型 + 内容结构定版票）。
- 版本重审周期与索引页能力（map 雾区已有：版本漂移维护、索引页能力）。
