# 角色与术语基线研究：收录清单与中英对照表来源

对应票：`角色与术语基线：收录清单与中英对照表来源`（Part of #1，AFK research）

> 本文件是一手来源调研的落点，供内容模板（#5）与新增角色流程（#6）直接引用。结论先行，证据在后。只定基线，不写全量攻略。

## 结论（可直接写进流程）

### 1. Canonical 层级（三层，谁压谁）

1. **游戏内文本 = 最高 canonical**：角色选择页 / 图鉴 Codex / 简体中文本地化文本。英文名与中文名冲突时以客户端为准。Godot 包内翻译文件为最终依据，取不到包时以客户端截图 + 版本号为证。
2. **Steam = 范围 canonical**：本体与 DLC 的划分、DLC 身份、官方中文游戏名，以 Steam 商店/API 为准。攻略页的“适用版本”以 Steam 当前版本为准（与取材规范票 #2 的双标注衔接）。
3. **Wiki = 镜像 canonical**：英文名拼写、属性/道具枚举、DLC 标记，以 wiki 为准；其中 `brotato.wiki.gg` 为官方 wiki（浏览器人工核对），`brotato.fandom.com` 的 `api.php` 为机器可抓的镜像（HTML 被墙时走 API，见证据 §4）。两者冲突时以游戏内文本为准，wiki 只作清单初稿来源。

中文对照的 canonical 只能是**游戏客户端简体中文**，wiki（英文站）不能作为中文来源。DLC 新词（如 Curse）若客户端中文缺失，先用 Steam `schinese` 页 + 客户端截图取证，标记 `待校对`，不自造翻译。

### 2. 收录角色清单（初稿 v2026-10-16，共 64）

- **本体 50**：Apprentice, Arms Dealer, Artificer, Baby, Beast Master, Brawler, Bull, Chunky, Crazy, Cryptid, Cyborg, Demon, Doctor, Engineer, Entrepreneur, Explorer, Farmer, Fisherman, Generalist, Ghost, Gladiator, Glutton, Golem, Hunter, Jack, King, Knight, Lich, Loud, Lucky, Mage, Masochist, Multitasker, Mutant, Old, One-Armed, Pacifist, Ranger, Renegade, Saver, Sick, Soldier, Speedy, Streamer, Technomage, Vagabond, Vampire, Well-Rounded, Wildling, Wounded。
- **Abyssal Terrors DLC 14**（`bt-dlc` 标记）：Buccaneer, Builder, Captain, Chef, Creature, Curious, Diver, Druid, Dwarf, Gangster, Hiker, Ogre, Romantic, Sailor。
- **明确排除**：
  - Mod 角色：凡不在游戏文件 + Steam DLC + wiki `Characters` 表三者中的，一律不收，关闭为 `wontfix`。
  - `Brotato Soundtrack`（App `3281080`，type `music`）：音乐 DLC，不进角色清单，避免与内容 DLC 混淆。
- **已发现但本基线不收**：`Brotato: Primal Dread`（App `4498220`，type `dlc`）为第二个内容 DLC，已在 Steam `1942280` 的 `dlc` 数组中出现。本 map 基线只含本体 + Abyssal Terrors；Primal Dread 走 §5 追加机制，不在本票展开。

计数口径：Fandom `Characters` 页 `wikitext` 实测 64 个 `bt-name`，其中 14 含 `bt-dlc`（2026-10-16 抓取，见证据）。

### 3. 属性/道具术语对照表（初稿 v2026-10-16，属性 20/25）

游戏内 stat 注册表共 25 项，其中 20 项在游戏文件中有名、会被发牌、wiki 有专文；另 5 项无名、无专文，攻略对照表**暂不收**，客户端若实际出现再追加。

20 项英文 canonical（拼写以 wiki `Stats` 表为准，Type/DLC 照抄）：

| English (canonical) | Type | DLC | 中文写法（初稿占位，以客户端简中为准） |
|---|---|---|---|
| Armor | Primary | — | 护甲 (Armor) ※ |
| Attack Speed | Primary | — | 攻击速度 (Attack Speed) ※ |
| Crit Chance | Primary | — | 暴击率 (Crit Chance) ※ |
| Curse | Primary | Abyssal Terrors | 诅咒 (Curse) ※ |
| Damage | Primary | — | 伤害 (Damage) ※ |
| Dodge | Primary | — | 闪避 (Dodge) ※ |
| Elemental Damage | Primary | — | 元素伤害 (Elemental Damage) ※ |
| Engineering | Primary | — | 工程 (Engineering) ※ |
| HP Regeneration | Primary | — | 生命回复 (HP Regeneration) ※ |
| Harvesting | Primary | — | 收获 (Harvesting) ※ |
| Life Steal | Primary | — | 生命窃取 (Life Steal) |
| Luck | Primary | — | 幸运 (Luck) ※ |
| Max HP | Primary | — | 最大生命 (Max HP) ※ |
| Melee Damage | Primary | — | 近战伤害 (Melee Damage) ※ |
| Range | Primary | — | 攻击范围 (Range) ※ |
| Ranged Damage | Primary | — | 远程伤害 (Ranged Damage) ※ |
| Speed | Primary | — | 移动速度 (Speed) ※ |
| Explosion Damage | Secondary | — | 爆炸伤害 (Explosion Damage) ※ |
| Reroll Price | Secondary | Abyssal Terrors | 重随价格 (Reroll Price) ※ |
| XP Gain | Secondary | — | 经验获取 (XP Gain) ※ |

※ = 中文为占位写法，终稿必须逐项对客户端简中校对后去掉 ※；`生命窃取 (Life Steal)` 为 map Notes 已定示例，不带 ※。

道具/武器名对照表不在本票展开（量级：Items 页 18 万字符 wikitext，Weapons 页 13 万字符），只定规则：英文 canonical 取 wiki `Items`/`Weapons` 页 `bt-name`，中文取客户端简中，写法同 §4。

### 4. 写法标准（全站统一）

- 正文一律 `中文 (English)`，括号半角，英文首字母照 wiki 原样（如 `Life Steal` 不写成 `Lifesteal`）。
- 首次出现必须带全称对照，后续同页可只用中文；标题/表格列头建议双语并列。
- DLC 专属条目（角色/属性/道具/武器）首次出现必须带 `DLC` 角标或后缀 `（Abyssal Terrors DLC）`，与非 DLC 区分；`Crash Zone` 地图后缀原样保留（承 #2）。
- 版本标注沿用 #2 双标注：`取材视频（YYYY-MM-DD）` + `适用版本：<Steam 当前版本 / DLC 有无>`；大更新后标 `待重审`。

### 5. 存放位置约定 + 追加机制（流程票 #6 直接用）

- **本研究资产（冻结）**：`docs/research/roster-terminology-baseline.md` @ `research/roster-terms`，记录初稿与证据，不随游戏更新改写；更新只发新版本行，不改历史行。
- **Canonical 数据（流程票 #6 落地，不在本票建文件）**：
  - `data/roster.json`：`[{id, en, zh, dlc: null|"abyssal", mod: false}]`，`en` 为 wiki 拼写，`zh` 为客户端简中，`id` 为 URL 安全 slug（如 `one-armed`）。
  - `data/terms.csv`：`en,zh,type,dlc,source_version`，`source_version` 写校对时的 Steam 版本 + 客户端语言版本。
- **后续新角色追加（Primal Dread 及以后）**：
  1. 查 Steam `1942280` 的 `dlc` 数组是否有新 App（当前 `[2868390, 3281080, 4498220]`），确认 `type: dlc` 且非 `music`。
  2. 抓 Fandom `Characters` 表 `bt-dlc` 数量变化，新增行即候选。
  3. 对客户端简中逐项校对 `zh` 后再入 `roster.json`/`terms.csv`；未校对前攻略页标 `待校对`，不发布。
  4. Mod 永不进入：无 Steam App + 无游戏文件 + 无 wiki 主表即拒收。

## 证据（一手来源）

1. **Steam 范围（机器可抓，2026-10-16 实测）**
   - Base：`https://store.steampowered.com/api/appdetails?appids=1942280&l=schinese` → `name: 土豆兄弟(Brotato)`，`steam_appid: 1942280`，`type: game`，`dlc: [2868390, 3281080, 4498220]`。
   - Abyssal Terrors：`appdetails?appids=2868390` → `name: 土豆兄弟：深渊魔物 (Brotato: Abyssal Terrors)`，`type: dlc`。商店页 `https://store.steampowered.com/app/2868390/Brotato_Abyssal_Terrors/`。
   - Soundtrack：`appdetails?appids=3281080` → `name: Brotato Soundtrack`，`type: music` —— 非内容 DLC，排除依据。
   - Primal Dread：`appdetails?appids=4498220` → `name: 土豆兄弟：史前恐惧 (Brotato: Primal Dread)`，`type: dlc` —— 第二个内容 DLC，本基线不收、走追加机制的依据。
   - 官方中文名 `土豆兄弟` 以 Steam `schinese` 为证；中文 shell 下 API 返回 UTF-8，GBK 终端会显示乱码，不影响结论。

2. **Fandom 角色表（机器可抓，`api.php` 绕过 HTML 墙）**
   - 端点：`https://brotato.fandom.com/api.php?action=parse&page=Characters&prop=wikitext&format=json`，`wikitext len 49497`。
   - `span class="bt-name">[[...]]` 共 64，14 含 `<span class="bt-dlc">DLC</span>`，名单见 §2（`Buccaneer, Builder, Captain, Chef, Creature, Curious, Diver, Druid, Dwarf, Gangster, Hiker, Ogre, Romantic, Sailor`）。
   - 表头语：`Every playable character in Brotato, with their starting stats, unlock condition, the item or weapon they unlock, and their shop item tags.` —— 清单口径依据。

3. **Fandom 属性表（游戏文件口径）**
   - 端点：`.../api.php?action=parse&page=Stats&prop=wikitext&format=json`。
   - 表头原话：`The game's own stat registry defines 25 stats; 20 of them carry a name in the game files, are handed out by the game, and have an article here.` / `The game files do not state how any stat is applied — there is no formula for armour, dodge or any other — so no article here gives one.` —— 20/25 口径与“不给公式”依据。
   - 20 行明细：`Armor/Attack Speed/Crit Chance/Curse(DLC Abyssal)/Damage/Dodge/Elemental Damage/Engineering/HP Regeneration/Harvesting/Life Steal/Luck/Max HP/Melee Damage/Range/Ranged Damage/Speed/Explosion Damage(Secondary)/Reroll Price(DLC Abyssal, Secondary)/XP Gain(Secondary)`，`Sources` 列为引用该属性的来源数（如 `Damage 91, Max HP 77`），公式不臆测。
   - Items/Weapons 量级：`Items len 180406`，`Weapons len 133745` —— 本票不展开全量对照表的依据。

4. **DLC 场景（Abyssal Terrors 内容锚点）**
   - 端点：`.../api.php?action=parse&page=The_Abyss&prop=wikitext&format=json`，`len 21030`。
   - 首句：`The Abyss is one of the two zones of Brotato, added by the Abyssal Terrors DLC. A run there is 20 waves long on a 32×24-tile map, with at most 100 enemies alive at once.` —— DLC 增加第二张图、20 波、32×24、100 敌上限。

5. **反证据（墙与缺口，决定 canonical 层级）**
   - `https://brotato.wiki.gg/wiki/Characters` 及其 `api.php?action=query&meta=siteinfo` / `action=parse&page=Characters` 在 2026-10-16 均返回 580090 字节 `Blocked - wiki.gg` 页 —— 官方 wiki 需浏览器人工核对，不可作为自动抓取源。
   - `https://brotato.fandom.com/wiki/Characters` HTML 返回 Cloudflare `Just a moment...` 挑战页，但同站 `api.php` 正常返回 JSON —— 机器抓取走 `api.php`，HTML 墙的绕行依据。
   - Fandom 为英文站，无中文对照；中文必须回游戏客户端简中 —— §1 中文 canonical 归属的依据。

## 待后续票确认（不阻塞本基线）

- 内容模板每栏写多深、武器 T1/T2 粒度（交原型 #4 + 内容结构 #5）。
- 版本重审周期、索引页搜索/筛选是否需要（map 雾区已有）。
- `data/roster.json` / `data/terms.csv` 的实际建文件与客户端简中逐项校对（交流程票 #6，本票只定约定不建文件）。
- 图片/图标与样式资源策略、批量生产排期（map 雾区已有）。
