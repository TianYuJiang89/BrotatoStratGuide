# TASK_SELECTION / TASK_WORDING（FROZEN 2026-10-21：只读 20-shot，selection 通览定双 TopN + wording 分项成文）

> freeze 说明：选择 8 + 文案 8 + 负例 4，共 20 例只读。选择归 agent（通览 grouping + ratings + weapons + phases + 全量整句→{upgrades[{name,quotes}],shop[{name,quotes}],synthesis}，N 动态由你定，保底意图进 fewshot；S/A 优先但 B 级可例外+须论证+证据；T1/ban 不进 shop 意图进 fewshot，码验交集；synthesis 写跨侧取舍+节奏+例外，码验非空+点名）。wording 每项独立单 agent（选择 fewshot + 文案 fewshot + 全量整句 + 一项+标签+synthesis+phases→{why,how_to_get}，数字不丢，未提空出）。禁断层码切（不数 count 最大断层）、禁动词表顺延（不背拒绝动词表）、禁 verified 门（不认 verified 信号）。

输出一件 JSON，不输出其它文字。你不填 count / quote_details（只活代码）。

## 选择契约（只读，通览定双 TopN）

输入：该角色全量整句（含 start/end/t，原样全量，不截断）+ 04 ratings（39 全量，term_en/rating/summary/analysis 全证据）+ 05 weapons（T1/T2 名单+note+analysis，只读）+ 03 grouping（四组全证据 name_en/group/note/analysis，建议，可推翻）+ 06 phases（运营波次节奏 phase/waves/goal/focus/pivot 全量，备查）。
输出：`{"upgrades": [{"name": "<04 term_en 一字不差>", "quotes": ["逐字，去重，非空"]}], "shop": [{"name": "<grouping candidates 一字不差>", "quotes": ["逐字，去重，非空"]}], "synthesis": {"tradeoff": "跨侧取舍：升级与商店抢钱时谁让谁", "rhythm": "按 06 哪几段排先后", "exceptions": "B 例外为什么进/must_take 13选N丢掉的为什么丢"}}`

- N 动态由你定：upgrades ≥1 且 shop ≥1（Top1 意图由你保，码只验非空，不验断层不断层）。
- S/A 优先但 B 级可例外：升级先看 S/A，B 级进 TopN 须在文案 why 论证为什么例外+证据（机检不管，靠人抽；选择只管给 quotes 证据）。
- 可推翻分组建议：grouping 只是建议，拿 quote 说话；ban 件永不进 TopN（任一证据是 ban 语义即出局，不背拒绝动词表）；T1 武器名永不进 shop（shop∩T1=∅，码验交集；意图进 fewshot，码只验交集）。
- upgrades 须出自 04 ratings term_en；shop 须出自 grouping candidates 且不在 ban 组、不在 T1 名单。
- quotes 须逐字等于全量整句某条 text，去重，每条非空；编 quote / 幻觉名 / 空 TopN 即 fail。
- 你不输出 why/how_to_get/count（只定名单+证据+综合论证，文案归 wording）。
- synthesis 必写三句：tradeoff 跨侧取舍（升级与商店抢钱/roll 时谁让谁）、rhythm 节奏（按 06 哪几段排先后，何波拿什么）、exceptions 例外交代（B 进为什么进，must_take 丢掉的为什么丢）；三句非空且须点到每个 TopN 名（码验子串，人抽看讲不讲得通）。

## 选择例（8 例，升级 4 + 商店 4）

SEL-U01 Ranged Damage S：ratings S + `You buy ranged damage at triple the normal rate, uh, which is of course incredibly strong.` / `We want to build as much ranged damage as we possibly can.` → upgrades / quotes 2 句（S 唯一入口，三倍率+全程堆）。
SEL-U02 Engineering A：ratings A + `The way this character works is you gain extra ranged damage, but all of your ranged damage turns to engineering halfway through the wave.` / `The reason for that is that screwdriver scales off of engineering.` → upgrades / quotes 2 句（A 本体，转机制+挂钩，零拿取也是 A）。
SEL-U03 Life Steal A：ratings A + `Minigun gives you the ability to use life steal extremely efficiently.` / `So, this character, despite being a a melee character, can still use life steal really well, which most of them don't get easy access to.` → upgrades / quotes 2 句（A 本体，机枪高效+后半保命）。
SEL-U04 Crit Chance B 例外：ratings B + `And I'll buy the blindfold cuz 128 for five crit chance isn't great, but we actually have some pretty significant benefits from crit chance.` / `And screwdrivers do really well with uh critical chance cuz they have increased critical damage.` → upgrades / quotes 2 句（B 级例外：犹豫但拿+螺丝刀暴伤挂钩，例外论证进文案 why，证据在此给全）。
SEL-S01 Turret shop：grouping must_take + `So, our turrets are actually contributing some reasonable damage as well.` / `But now we also have some turrets cuz we have significantly increased tree spawns.` → shop / quotes 2 句（must_take+后半有战果）。
SEL-S02 Pocket Factory shop：grouping must_take + `We got a cursed pocket factory, so that's going to be really good damage for us in the second half of waves.` → shop / quotes 1 句（must_take+后半保险，1 句也收，禁数帽）。
SEL-S03 Minigun T1 避让：weapons T1 含 Minigun + `Um, we also, because we have a minigun, start with secretly one of the very best healing items in the game.` → 不进 shop（T1 武器名永不进商店，纵在整句也不收；拿不是买，shop 只认 grouping candidates）。
SEL-S04 Boxing Glove ban 避让：grouping ban + `Uh, I'm going to ban the boxing glove.` → 不进 shop（ban 件进 TopN 即 fail，拿 quote 说话也不许进）。

SYN-01 综合论证（cyborg 4+4）：tradeoff `升级先保三倍率远程与工程转，商店钱让给炮塔体系（工厂养炮塔吃工程），Acid 只锁一手不追` / rhythm `按 06 前期拿远程中期转工程后期靠工厂炮塔残局，Tyler 残局吃工程` / exceptions `Crit Chance B级例外（盲盒犹豫但螺丝刀暴伤挂钩顺手拿），must_take 13选4丢掉的非炮塔体系暂放` → 三句须点到 8 个 TopN 名。

## 文案契约（每项独立单 agent）

输入：选择 fewshot + 文案 fewshot + 全量整句 + 一项（name+quotes）+ 本项标签（升级带 rating / 商店带 group）+ synthesis 全文 + 06 phases 全量（节奏参考）。
输出：`{"name": "<与项一字不差>", "why": "≤120字人话+短引", "how_to_get": "≤120字人话，原话数字不丢"}`

- why 人话一句：为什么优先 + 关键原句短引（短引须逐字出自本项 quotes）；how_to_get 人话一句：怎么拿（商店见即拿/升级二选一优先/roll 到即锁/何波拿换），原话数字不丢，未提空出不脑补。
- 数字不丢：why/how_to_get 里的每个数字须逐字出自本项 quotes（编数字即 fail，码验子串）；quotes 无数字则文案不写数字（未提空出）。
- 整句复制某条 quote 当 why/how_to_get 即 fail（小结须≠原文）。
- B 级例外论证：B 级项须在 why 写清为什么例外（S/A 优先，为何它也进），证据已在选择 quotes 给全，标签会告诉你它是 B。
- phases 仅供节奏参考：how_to_get 的数字/波次须出自本项 quotes，禁把 phases 波次号编进文案（未提空出）。

## 文案例（8 例，why/how_to_get+数字不丢+短引）

WRD-01 Ranged Damage：quotes 含 `You buy ranged damage at triple the normal rate, uh, which is of course incredibly strong.` → why `三倍率入口全程堆抢 elite，原话“triple the normal rate”` / how_to_get `升级二选一优先拿，商店见即买`。
WRD-02 Engineering：quotes 含 `The reason for that is that screwdriver scales off of engineering.` → why `转后全靠工程撑螺丝刀，原话“scales off of engineering”` / how_to_get `不用专门买，跟着远程走`。
WRD-03 Life Steal：quotes 含 `Minigun gives you the ability to use life steal extremely efficiently.` → why `机枪高频吃满吸血后半保命，原话“use life steal extremely efficiently”` / how_to_get `升级见吸血即拿`。
WRD-04 Crit Chance B 例外：quotes 含 `And I'll buy the blindfold cuz 128 for five crit chance isn't great` + `And screwdrivers do really well with uh critical chance cuz they have increased critical damage.` → why `B级例外：犹豫但螺丝刀暴伤挂钩值得顺手，原话“increased critical damage”` / how_to_get `128 见盲盒可拿，不强求`（数字 128 出自 quotes）。
WRD-05 Turret：quotes 含 `So, our turrets are actually contributing some reasonable damage as well.` → why `工程转后炮塔跟上吃加成，原话“turrets are actually contributing”` / how_to_get `口袋工厂铺炮塔，商店见即买`。
WRD-06 Pocket Factory：quotes 含 `We got a cursed pocket factory, so that's going to be really good damage for us in the second half of waves.` → why `后半段伤害保险越铺越强，原话“really good damage for us in the second half”` / how_to_get `商店刷出即买，诅咒也拿`。
WRD-07 Tyler 数字不丢：quotes 含 `Even the Tyler that we got pretty near the end of the game dealt 11,000 damage because it scales off of our engineering at 90% and that stat is so high.` → why `残局吃工程打出伤害，原话“dealt 11,000 damage because it scales off of our engineering at 90%”` / how_to_get `与包横幅同波商店买入`（数字 11,000/90% 逐字出自 quotes，不丢）。
WRD-08 未提空出：quotes 含 `I'll lock acid as well.`（无波次无把数）→ why `血少复购补血，原话“lock acid”` / how_to_get `见即锁`（quotes 无数字，文案不编波次不编把数，诚实空出）。

## 负例（4 例，数断层 TopN/动词表顺延/整句复制/T1 进商店）

NEG-01 数断层 TopN 判负：按 `count` 最大断层切（`gaps=count[i]-count[i+1]`，最大断层即止）定 upgrades/shop → fail（禁断层码切，N 由 agent 定，码只验非空）。
NEG-02 动词表顺延判负：候选 quotes 含 `not taking` 即按拒绝动词表顺延出局（如 `I definitely am not taking a peacock this wave.` 见 not taking 即顺延）→ fail（禁动词表，拿 quote 说话，可推翻 group 建议，不背表）。
NEG-03 整句复制判负：why 全文等于某条 quote 原文（如 `You buy ranged damage at triple the normal rate, uh, which is of course incredibly strong.` 一字不差当 why）→ fail（why 须人话+短引，小结≠原文）。
NEG-04 T1 进商店判负：shop 含 T1 武器名（如 `Minigun`，weapons T1）→ fail（shop∩T1=∅，码验交集；T1 意图进 fewshot，码只验交集）。
