# TASK_DISCOVERY / TASK_EVIDENCE / TASK_GROUPING（FROZEN 2026-10-21 v3：只读 20-shot，真聊道具 vs 路过名词）

> v3 微修（DIS-01/GRP-01 去跨名句、GRP-02 加 Top1 示范、补禁令半句；其余例子未动）：discovery 逐个打勾——词汇表动态分片（40/批），收+丢==本批（机检：缺件/重叠/陌生名即 fail）。判对判错归 agent、心抽复核。

输出一件 JSON，不输出其它文字。你不填 count / quote_details（只活代码）。

## 发现段 打勾契约

你只判随附的本批名单（动态分片之一，不判其它）。输出：
`{"收": [{"name_en": "<本批一字不差>", "quotes": ["逐字，去重，≥1"]}], "丢": ["<本批一字不差>", ...]}`

收：有买/锁/拿/升/留/转 build 意图，或明确拒绝/跳过（ban/skip 也是真聊，进 ban / mentioned 档）。
丢：类别口头（含复数泛指）/ 属性词非道具 / 地图实体同名 / 动词同形（focus 动词≠道具 Focus）。
收+丢==本批（一件恰好一次；空收可，漏判即 fail）。
幻觉名/编 quote/收空 quotes/note 整句复制原文即 fail。

## 发现段 收（6 例，真聊即收，一句逐字 quote 即收）

DIS-01 Turret：`um an incendiary turret, uh a Tyler, something like that.` → 收（体系位，1 句也收）。
DIS-02 Pocket Factory：`We got a cursed pocket factory, so that's going to be really good damage for us in the second half of waves.` → 收（买+后半段伤害）。
DIS-03 Boxing Glove（ban 也是真聊）：`Uh, I'm going to ban the boxing glove.` → 收（明确拒绝，进 ban 档）。
DIS-04 Landmines（skip 也是真聊）：`Also, I'm just pretty much ignoring what the landmines are doing.` → 收（跳过语境，进 mentioned 档）。
DIS-05 Acid：`I'll lock acid as well.` / `And we'll take the acid again as well cuz my max HP remains really poor.` → 收（锁→复购）。
DIS-06 Coffee：`Take the nuke launcher and buy coffee.` / `We'll buy coffee.` → 收（买了即收，禁数帽）。

## 发现段 丢（4 例，路过名词一律丢）

DIS-07 Focus 动词同形：`So you need to kind of split your focus.` → 丢（动词，非道具 Focus）。
DIS-08 Tree 地图树：`I'm going to try to run for the trees here and use these consumables.` → 丢（地图树，非道具 Tree）。
DIS-09 属性词非道具：`The reason for that is that screwdriver scales off of engineering.` → 丢（engineering 是属性，无道具名）。
DIS-10 类别口头：`The shop also has a lot of items worth considering.` → 丢（无单道具名，只描述）。

## 分组段 must_take（3 例，拿了+后文有战果/体系位）

GRP-01 Turret must_take：`But now we also have some turrets cuz we have significantly increased tree spawns.` / `So, our turrets are actually contributing some reasonable damage as well.` → must_take / note：工程转后炮塔跟上吃加成，原话“turrets are actually contributing some reasonable damage”。
GRP-02 Pocket Factory must_take：`We got a cursed pocket factory, so that's going to be really good damage for us in the second half of waves.` → must_take / note：本局最关键，后半段伤害保险，原话“really good damage for us in the second half”。
GRP-03 Acid must_take：`I'll lock acid as well.` / `And we'll take the acid again as well cuz my max HP remains really poor.` → must_take / note：血少复购补血，原话“take the acid again”。

## 分组段 mentioned_not_taken（2 例，提过但没拿/跳过）

GRP-04 Landmines mentioned：`Also, I'm just pretty much ignoring what the landmines are doing.` / `But you'll notice that I'm basically completely ignoring the landmines.` → mentioned_not_taken / note：全程 ignoring 没拿，原话“ignoring what the landmines are doing”。
GRP-05 Peacock mentioned（本波不拿≠永久 ban）：`I definitely am not taking a peacock this wave.` → mentioned_not_taken / note：本波跳过不清算，原话“not taking a peacock this wave”。

## 分组段 ban（3 例，ban 语义替代拒绝动词表：ban / recycle / sell 原话即 ban，看语义不背表）

GRP-06 Boxing Glove ban：`Uh, I'm going to ban the boxing glove.` → ban / note：明说 ban，直接出局原话“ban the boxing glove”。
GRP-07 White Flag ban：`We'll ban white flag and get our free roll off of that.` → ban / note：ban 换免费 roll，原话“ban white flag”。
GRP-08 Recycle 语义 ban：`I think I'm just going to recycle that.` → ban / note：recycle 即出局语义，原话“going to recycle that”。

## 分组段 casual_mention（2 例，低频路过照旧，不升格）

GRP-09 Coffee casual：`Take the nuke launcher and buy coffee.` → casual_mention / note：顺手一提无后文，原话“buy coffee”。
GRP-10 Mutation casual：`I will take a jelly and we'll lock a mutation and then I'll roll.` / `And then I'll buy a mutation.` → casual_mention / note：锁了但无战果解释，原话“lock a mutation”。

## note 人话（≤120 字 + 短引逐字）

人话一句 + 短引（短引逐字出自本条 quotes）。
Top1 落 must_take 首条，note 开头点明（见 GRP-02“本局最关键”），码只验非空不验排名。
