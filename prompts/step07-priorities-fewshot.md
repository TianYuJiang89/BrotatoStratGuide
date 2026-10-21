# TASK_PRIORITY（FROZEN 2026-10-21：只定 upgrades / shop TopN，N 由你定，可推翻分组建议，禁断层码切）

输入：grouping（四组）+ 04 ratings（39 全量）+ 05 weapons（T1/T2）+ 06 phases（作者章节奏）+ 全量整句。
输出一件 JSON，不输出其它文字：
{"upgrades": [{"name": "<04 term_en 一字不差>", "why": "≤120字人话+短引", "how_to_get": "≤120字人话，原话数字不丢", "quotes": ["逐字，去重，非空"], "analysis": "来源→机制→TopN"}], "shop": [{"name": "<grouping candidates 一字不差>", "why": "≤120字人话+短引", "how_to_get": "≤120字人话", "quotes": ["逐字，去重，非空"], "analysis": "来源→分组→TopN"}]}

- N 动态由你定：upgrades ≥1，shop ≥1（Top1 意图，码只验非空，不验断层不断层）。
- 可推翻分组建议：grouping 只是建议，拿 quote 说话；ban 件永不进 TopN（任一证据是 ban 语义即出局，不背拒绝动词表）。
- upgrades 须出自 04 ratings term_en；shop 须出自 grouping candidates 且不在 ban 组。
- quotes 逐字出自全量整句，去重，每条非空；编 quote / 幻觉名 / 空 TopN 即 fail。
- `why` 人话一句 + 短引（短引须逐字出自本条 quotes）；`how_to_get` 怎么拿，原话数字不丢，未提空出不脑补。
- 禁断层码切：不数 count 最大断层（count 只活代码回填，你不填）。

## upgrades 例（2 例）

PRI-U01 Life Steal：ratings A + `So, this character, despite being a melee character, can still use life steal really well.` → upgrades / why：机枪吃吸血后半波保命，原话“use life steal really well”/ how_to_get：升级二选一优先拿。
PRI-U02 Ranged Damage：ratings S + `You buy ranged damage at triple the normal rate, uh, which is of course incredibly strong.` → upgrades / why：三倍率入口无脑堆，原话“triple the normal rate”/ how_to_get：商店见即买。

## shop 例（3 例：1 正常 + 1 ban 出局 + 1 推翻）

PRI-S01 Turret shop：grouping must_take + `So, our turrets are actually contributing some reasonable damage as well.` → shop / why：工程转后炮塔跟上，原话“turrets are actually contributing”/ how_to_get：roll 到即锁。
PRI-S02 Boxing Glove 永不出局：grouping ban + `Uh, I'm going to ban the boxing glove.` → 不进 shop（ban 件进 TopN 即 fail）。
PRI-S03 Peacock 推翻：grouping must_take 但 `I definitely am not taking a peacock this wave.` → 不进 shop（拿 quote 说话，可推翻 group 建议，不硬收）。
