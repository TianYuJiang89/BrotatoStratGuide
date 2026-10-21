# TASK_SEGMENTATION / TASK_WORDING（FROZEN 2026-10-21：只读 20-shot，运营波次切分 + 三问）

> freeze 说明：切分 8 + 三问 8 + 负例 4，共 20 例只读。切分归 agent（自定义波次，不抄作者章题）；
> 三问综合多条可执行短引，禁整句复制/模具话/编数字/计数泄漏。N 不定（本例 7 桶仅演示，他例按实际，码不卡 N，粒度靠人抽）。

输出一件 JSON，不输出其它文字。你不填 count / quote_details（只活代码）。

## 切分契约（只读，不抄章题）

输入：该角色全量整句（含 start/end/t，原样全量，不截断）。
输出：`{"buckets": [{"phase": "<运营语言，不抄作者章题>", "waves": "<原话作证，无证据空串>", "quotes": ["逐字，去重，≥1"]}, ...]}`

- phase：运营语言（如前期攒伤/转工程/horde 转核弹/elite 狩猎/终局收束），不许抄作者章题（如 Character overview / Strategy and early game）；各桶 phase 互异。
- waves 非空须原话作证（整串是本桶某句的子串，或关键词须出自本桶）；无证据空串，不编；纯配装转折段允许空串。
- quotes：逐字等于全量整句某条 text，去重，每桶 ≥1；桶间不重叠（一句只进一桶）；编 quote / 空桶 / 重叠即 fail。
- N 不定（本例 7 桶仅演示，他例按实际；码不卡 N，粒度靠人抽）。

## 切分例（8 例，本例 N=5 演示）

SEG-01 前期远程攒伤：`So for the first half of the wave, you're a very powerful ranged attacker, but for the second half of the wave, that all turns into engineering.` / `We need to kill elites really quickly before our damage swaps over.` / `I want to add a second ranged weapon just to make certain that we can kill elites quickly and keep down the more dangerous enemies at the beginning of the the run.` → phase `前期远程攒伤转工程` / waves ``（纯配装转折，无波次号，诚实空出） / quotes 3 句去重。
SEG-02 过渡补位：`We'll buy a screwdriver.` / `We'll add a screwdriver.` / `My max HP is really low.` → phase `过渡补位与血量兜底` / waves ``（无波次证据，空出不编） / quotes 3 句。
SEG-03 波次点名：`Um because you don't deal well with the enhanced flies on wave 16.` / `Can I buy that going into wave 16?` → phase `对空短板与 wave 16 预案` / waves `wave 16`（逐字出自本桶 quotes） / quotes 2 句。
SEG-04 horde 转核弹：`So, given that we're going into the horde wave, I'm going to take the nuke launcher, uh, which means combining here.` / `Obviously, we're taking the nuke launcher for the horde wave because it's much better than an upgraded minigun on a horde wave since it clears it's an explosion` / `Now we have a horde wave next.` / `I'm not as worried about the horde wave.` → phase `horde 波转核弹清场` / waves `horde wave`（逐字出自本桶） / quotes 4 句。
SEG-05 elite 狩猎：`And obviously upgrading our minigun is going to help as well for killing elites and bosses quickly.` / `And then the goal here is to kill the elite really fast using our very high base damage.` / `That'll help us kill the elite faster, which we really want.` → phase `elite 速杀与转伤窗口` / waves ``（elite 系怪名非波次号，本例空出） / quotes 3 句。
SEG-06 peacock 控场：`I do not want to let a bunch of mini bosses spawn because this is a peacock wave, so enemies are doing 30% more damage than normal.` → phase `peacock 波控 mini boss` / waves `peacock wave`（逐字出自本桶） / quotes 1 句（1 句也收，禁数帽）。
SEG-07 终局收束：`And then we'll we'll go to wave 20.` / `So, I want to kill the whale boss first because it's typically got the more dangerous attack patterns.` / `And so, we might not kill both bosses before we transition between damage types.` / `And so, specifically in the boss wave, having more enemies around to be able to life steal off of can often be advantageous.` → phase `终局 whale 先杀与收束` / waves `wave 20`（逐字出自本桶首句） / quotes 4 句。
SEG-08 桶间不重叠：上例 7 桶 quotes 互不重叠（一句只进一桶）；若 `Scary at the end of wave 10, but we survived here.` 已进某桶，他桶再收即重叠 fail。

## 三问契约（每桶独立单 agent）

输入：切分 fewshot + 三问 fewshot（本文件） + 全量整句 + 一桶（phase/waves/quotes）。
输出：`{"phase": "<与桶一字不差>", "goal": "≤120字人话+短引", "focus": "≤120字人话+短引", "pivot": "≤120字人话+短引", "extra_quotes": ["逐字，真桶外，无则[]"]}`

- phase 须与桶一字不差；goal/focus/pivot 各 ≥8 字，人话一句：goal 点局面+机制+短引，focus 点可执行动作+原话数字不丢+短引，pivot 点到下一桶衔接条件+短引（末桶写收束复盘）。
- 三问须综合多条（只复读一条判负）；短引须逐字出自本桶 quotes（桶外引须先入 extra_quotes 才可引）；整句复制某条 quote 判负。
- extra_quotes：可选桶外补引用（跨桶串讲的关键句才补，不限条数，须必要）；必须逐字出自全量整句，且不在本桶 quotes 内（真桶外）；与本桶重复/桶内已收判负；无则 []，空桶诚实空出不补。
- 禁模具话（按本章节奏来/衔接点/不编数字单独出现判负）；禁计数泄漏（字幕 N 次不进文案）；禁编数字（原话数字须逐字，未提空出不脑补）。

## 三问例（8 例）

WRD-01 前期远程攒伤：桶 `前期远程攒伤转工程` + quotes（含 `So for the first half of the wave, you're a very powerful ranged attacker` + `We need to kill elites really quickly before our damage swaps over.`）→ goal `前半波远程爆发 elite 转前秒掉，原话“kill elites really quickly before our damage swaps over”` / focus `补第二把远程保 elite 速杀，原话“add a second ranged weapon”` / pivot `攒伤转工程不断档，原话“turns into engineering”` / extra []。
WRD-02 过渡补位：桶 `过渡补位与血量兜底` + quotes（含 `We'll buy a screwdriver.` + `My max HP is really low.`）→ goal `低血过渡靠螺丝刀续伤，原话“We'll buy a screwdriver”` / focus `见螺丝刀即锁补伤害，原话“We'll add a screwdriver”` / pivot `保血进 horde，原话“My max HP is really low”` / extra []。
WRD-03 wave 16 预案：桶 `对空短板与 wave 16 预案` + quotes（含 `Um because you don't deal well with the enhanced flies on wave 16.`）→ goal `wave 16 强化蝇难处理须预案，原话“enhanced flies on wave 16”` / focus `进 wave 16 前补对空，原话“going into wave 16”` / pivot `活过 wave 16 进 horde，原话“wave 16”` / extra []。
WRD-04 horde 转核弹：桶 `horde 波转核弹清场` + quotes（含 `So, given that we're going into the horde wave, I'm going to take the nuke launcher` + `Obviously, we're taking the nuke launcher for the horde wave`）→ goal `horde 波核弹清场最优解，原话“taking the nuke launcher for the horde wave”` / focus `进 horde 合核弹，minigun 留打 elite，原话“going into the horde wave”` / pivot `清完 horde 回 elite 狩猎，原话“horde wave next”` / extra [`I can't take a scarf going into a horde wave.`]（真桶外：逐字出自全量整句，不在本桶内，补 horde 配装禁忌必要）。
WRD-05 elite 狩猎：桶 `elite 速杀与转伤窗口` + quotes（含 `And then the goal here is to kill the elite really fast using our very high base damage.`）→ goal `高基础伤 elite 速杀窗口，原话“kill the elite really fast”` / focus `升级 minigun 提 elite 斩杀，原话“killing elites and bosses quickly”` / pivot `elite 转前清完进 peacock，原话“kill the elite faster”` / extra []。
WRD-06 peacock 控场：桶 `peacock 波控 mini boss` + quotes（含 `I do not want to let a bunch of mini bosses spawn because this is a peacock wave`）→ goal `peacock 波禁刷 mini boss，原话“peacock wave”` / focus `先清小怪压增伤，原话“30% more damage than normal”` / pivot `控住刷怪进终局，原话“mini bosses spawn”` / extra []。
WRD-07 终局收束：桶 `终局 whale 先杀与收束` + quotes（含 `So, I want to kill the whale boss first` + `And then we'll we'll go to wave 20.`）→ goal `wave 20 双 boss 先杀 whale，原话“kill the whale boss first”` / focus `留怪吸血站桩输出，原话“life steal off of”` / pivot `收束复盘：转伤前未必双杀，原话“transition between damage types”` / extra []。
WRD-08 桶外补必要性：桶外句 `I'll take a corrupted shard and then we'll go to wave 18.` 若与本桶衔接条件直接相关才可入 extra；无关凑数判负；extra 逐字出自全量整句，与本桶重复判负。

## 负例（4 例，现 prompt 判负清单：只复读一条/模具话/编数字/计数泄漏/整句复制）

NEG-01 只复读一条判负：goal `本章作者打法：So for the first half of the wave…原话“So for the first half…”`（只复读一条，无综合第二条，无可执行动作）→ fail。
NEG-02 模具话+计数泄漏判负：focus `配装重心按本章节奏来，字幕共出现 12 次螺丝刀`（模具话单独出现 + 字幕 N 次进文案）→ fail。
NEG-03 编数字/编波次判负：waves `wave 25`（全量整句无 wave 25，原话无此号）/ focus `四把螺丝刀进 wave 16`（quotes 无 four，本桶无此数）→ fail。
NEG-04 整句复制判负：goal 全文等于某条 quote 原文（小结 == 原文，一字不差，无人话综合）→ fail。
