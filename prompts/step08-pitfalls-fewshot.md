# TASK_DISCOVERY / TASK_WORDING（FROZEN 2026-10-21：只读 20-shot，agent 发现 + 分级）

> freeze 说明：发现 8 + 分级 8 + 负例 4，共 20 例只读。第一跳码召回已退役，
> 召回归 discovery agent（全量整句→candidates[{title,seeds,extra}]，N 不定，无事件空数组诚实交）；
> wording 每条独立单 agent（发现 fewshot + 分级 fewshot + 全量整句 + 一条→{title,severity,why,how_to_avoid,reason,seeds,extra}）。
> severity 三档绝对（fatal=会崩盘，risky=会亏经济/走位，trap=看似赚实则亏，trap 须在 reason 论证看着赚在哪）。
> take 系已拿不算坑（拿不是坑，意图进 fewshot，码不管）；ban 组不重复进（坑证据不含新 grouping ban 名，码验）。

输出一件 JSON，不输出其它文字。你不填 count / quote_details（只活代码）。

## 发现契约（只读，真坑 vs 路过抱怨）

输入：该角色全量整句（含 start/end/t，原样全量，不截断）。
输出：`{"pits": [{"title": "<短标题，8字内，建议>", "seeds": ["逐字，去重，≥1"], "extra": ["逐字，去重，可空，真桶外"]}, ...]}`

- 坑=具体可躲事件（站位/换伤/孔雀/经济），不是泛泛抱怨；每坑至少一句 seeds（≥1），无事件空数组诚实交（`{"pits": []}`），不硬凑。
- seeds/extra 须逐字等于全量整句某条 text，去重；extra 与 seeds 不交（交叠即 fail）；跨坑不重叠（一句只进一坑）。
- 无警告词真坑也收（事件同一性归你判，不背警告标记表）；利好句/已拿句/泛泛抱怨一律丢。
- take 系已拿不算坑：有明确拿取（buy/take/lock/get/roll for 原形/变形肯定式，无否定）即拿不是坑，不收为 seeds/extra（解法引用含 take 作证据允许，如 horde 波前合核弹，但不得以 take 本身为坑）。
- N 不定（本例 4 坑仅演示，他例按实际，码不卡 N，粒度靠人抽）。

## 发现例（8 例，真坑收 + 路过丢 + 无警告词真坑收）

DIS-01 换伤斩杀真坑收：`So, we need enough ranged damage to make sure that we're doing that.` / `And uh the fact that we swap halfway through means that we're going to turn from a really dangerous ranged attacker into a kind of wimpy melee attacker partway through.` / `So, um, because the second half of waves is so much harder than the first, we're going to have to spend a lot of effort making sure that our character, uh, survives the second half of those waves.` → 收（换伤后变弱+后半波难活同一事件，3 句 seeds）。
DIS-02 站位吃弹真坑收（含无警告词）：`I've also put myself in an awkward position in this wave cuz I I went to the left of the map, uh, which is where the projectiles were spawning from.` / `If I had fled to the right of the map when I went to the engineering phase, I'd have taken less damage from projectiles spawning on top of me.` → 收（同一站位事件；第二句无警告词但同事件跟走，真坑收）。
DIS-03 站位复盘跟走：`I walked into every single projectile there for no reason at all.` → 收进站位坑 extra（同属站位吃弹事件，复盘句，无警告词也收）。
DIS-04 孔雀产怪真坑收（含诱饵）：`Use the the range damage portion of the waves to clear the hatchers and definitely do not want a bunch of enhanced flashers spawning.` / `I do not want to let a bunch of mini bosses spawn because this is a peacock wave, so enemies are doing 30% more damage than normal.` + extra `The peacock and bean teacher let us hit level 27 which was pretty awesome.` → 收（孔雀增伤+防刷怪同一事件；level 27 看着升级血赚是 trap 诱饵证据，进 extra 当看着赚示范）。
DIS-05 海星经济真坑收：`It's pretty risky and I think I'm going to pass on it.` / `Um, just cuz 15% increased enemy damage is really hard to overcome.` / `the extra income takes a while to pay off and you end up uh just dying before you get there a lot of the time cuz it's more about finding defensive stats on nightmare mode than it is about uh having high economy frequently.` → 收（强但增伤难顶+回本慢先死同一事件）。
DIS-06 tree 利好丢（44 剔除类）：`But now we also have some turrets cuz we have significantly increased tree spawns.` → 丢（tree 利好不是坑，纵在池也不收，剔除）。
DIS-07 路过抱怨丢：`We're mostly trying to avoid.` → 丢（半截话泛泛抱怨，无具体事件，判不明的直接丢掉不收）。
DIS-08 take 已拿丢：`We'll buy a screwdriver.` / `I will take a jelly and we'll lock a mutation and then I'll roll.` → 丢（已拿不是坑，take 系拿取不算坑；解法引用含 take 作证据允许，但不得以 take 本身为坑）。

## 分级契约（只读，fatal/risky/trap 绝对档）

输入：发现 fewshot + 分级 fewshot + 全量整句 + 一条（title/seeds/extra）。
输出：`{"title": "<短标题，8字内>", "severity": "fatal/risky/trap", "why": "人话一句：代价+短引", "how_to_avoid": "人话一句：动作+条件", "reason": "人话一句：为什么合成一条+扩展凭什么跟走", "seeds": ["逐字"], "extra": ["逐字"]}`

- severity 绝对档，不排名：fatal=会崩盘（换伤/孔雀放怪），risky=会亏经济/走位（站位吃弹），trap=看似赚实则亏（须在 reason 论证看着赚在哪，不然一律按 risky）。
- why 人话一句：代价是什么 + 关键原句短引（短引须出自本条 seeds+extra 逐字）；how_to_avoid 人话一句：动作+条件（何波/何时/拿什么），只认视频口径，未提空出不脑补。
- reason 人话一句：为什么这几句合成一条、扩展句凭什么跟走（trap 在此论证看着赚）；整句复制某条 quote 当 why 即 fail。
- seeds 非空（≥1，逐字），extra 可空（逐字，真坑外）；trap 诱饵证据进 extra（如 level 27 看着升级血赚）。

## 分级例（8 例，fatal 3 + risky 3 + trap 2，trap 须看着赚论证）

LVL-01 fatal 换伤斩杀：seeds 含 `So, we need enough ranged damage to make sure that we're doing that.` + `And uh the fact that we swap halfway through means that we're going to turn from a really dangerous ranged attacker into a kind of wimpy melee attacker partway through.` + `So, um, because the second half of waves is so much harder than the first, we're going to have to spend a lot of effort making sure that our character, uh, survives the second half of those waves.` → severity `fatal` / why `后半波变近战弱仔会崩盘，原话“survives the second half”` / how_to_avoid `上半波用远程火力先杀精英，记住每波过半即换伤` / reason `四句同讲换伤后变弱、后半波难活，别被切换打懵，故合成一条`。
LVL-02 fatal 孔雀放怪：seeds 含 `I do not want to let a bunch of mini bosses spawn because this is a peacock wave, so enemies are doing 30% more damage than normal.` → severity `fatal` / why `孔雀增伤下放刷怪等于自杀，原话“enemies are doing 30% more damage”` / how_to_avoid `孔雀波用远程段清孵化怪，别放出一堆小怪` / reason `三句同属孔雀波增伤+防刷怪同一事件，故合成一条`。
LVL-03 fatal 换伤精英：extra 含 `But the elite you really need to kill before your damage types swap over when you're playing the cyborg.` + `And then the goal here is to kill the elite really fast using our very high base damage.` → severity `fatal`（elite 转前不杀即崩，归换伤斩杀坑 extra）。
LVL-04 risky 站位吃弹：seeds 含 `I've also put myself in an awkward position in this wave cuz I I went to the left of the map, uh, which is where the projectiles were spawning from.` → severity `risky` / why `站错弹幕出生点白吃伤害，原话“where the projectiles were spawning from”` / how_to_avoid `进工程相位往弹幕反侧站位，视频只点了右侧与底部` / reason `种子自认左半区站位别扭，两句扩展同属同一站位吃投射物事件，故跟走`。
LVL-05 risky 站位复盘：extra 含 `I walked into every single projectile there for no reason at all.` → severity `risky`（白吃伤害亏走位，归站位坑 extra）。
LVL-06 risky 通用：seeds 含 `So, this wave is is definitely dangerous.` → severity `risky`（单句危险警告，无崩盘证据，按 risky，不硬抬 fatal）。
LVL-07 trap 孔雀诱饵：extra 含 `The peacock and bean teacher let us hit level 27 which was pretty awesome.` → severity `trap` / why `看着赚回本、实则增伤先死亏经济崩盘，原话“just dying before you get there”` / reason `trap 论证看着赚在“hit level 27”看着升级血赚，实则 30%增伤+刷怪会崩`（诱饵证据进 extra 当看着赚示范）。
LVL-08 trap 海星诱饵：seeds 含 `It's pretty risky and I think I'm going to pass on it.` + `Um, just cuz 15% increased enemy damage is really hard to overcome.` + `the extra income takes a while to pay off and you end up uh just dying before you get there a lot of the time cuz it's more about finding defensive stats on nightmare mode than it is about uh having high economy frequently.` → severity `trap` / why `看着赚回本、实则增伤先死亏经济崩盘，原话“just dying before you get there”` / how_to_avoid `孔雀夜魇下直接跳过海星，视频只讲跳过` / reason `trap 论证看着赚在“extra income”看着回本赚，实则 15%增伤+缺防御先死`。

## 负例（4 例，take 当坑/无 seed 硬塞/跨事件硬并/整句复制当 why）

NEG-01 take 已拿当坑判负：`We'll buy a screwdriver.` 当坑 seeds → fail（拿不是坑，take 系已拿确未入坑；解法引用含 take 作证据允许，但不得以 take 本身为坑）。
NEG-02 无 seed 硬塞判负：某坑 seeds 空数组，extra 硬塞 `But now we also have some turrets cuz we have significantly increased tree spawns.` → fail（每坑至少一句 seeds，无事件空数组诚实交，不硬塞）。
NEG-03 跨事件硬并判负：把站位坑 `I've also put myself in an awkward position in this wave cuz I I went to the left of the map, uh, which is where the projectiles were spawning from.` 与孔雀坑 `I do not want to let a bunch of mini bosses spawn because this is a peacock wave` 只因同含 spawn 就合并 → fail（事件不同，spawn 同词不硬并）。
NEG-04 整句复制当 why 判负：why 全文等于某条 quote 原文（如 `So, we need enough ranged damage to make sure that we're doing that.` 一字不差当 why）→ fail（why 须人话+短引，小结≠原文）。
