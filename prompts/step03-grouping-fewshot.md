# TASK_DISCOVERY / TASK_EVIDENCE / TASK_GROUPING（FROZEN 2026-10-24 v4：只读 26-shot，真聊道具 vs 路过名词，六组）

> v4 新增（#74：wishlist/taken 两档）：愿望单（想要+持续追没拿到）与拿了无下文（拿/锁无反悔但无战果）从 mentioned/casual 剥离；GRP-09 Coffee 与 GRP-10 Mutation 由 casual 修订进 taken（单锁/买两次无下文）；casual 收窄到纯嘴提（无购买无锁）；锁/买=拿除非明确不拿（举证责任倒置）。discovery 逐个打勾——词汇表动态分片（40/批），收+丢==本批（机检：缺件/重叠/陌生名即 fail）。判对判错归 agent、心抽复核。

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

## 分组段 must_take（3 例，拿了+后文有战果/体系位，不动）

GRP-01 Turret must_take：`But now we also have some turrets cuz we have significantly increased tree spawns.` / `So, our turrets are actually contributing some reasonable damage as well.` → must_take / note：工程转后炮塔跟上吃加成，原话“turrets are actually contributing some reasonable damage”。
GRP-02 Pocket Factory must_take：`We got a cursed pocket factory, so that's going to be really good damage for us in the second half of waves.` → must_take / note：本局最关键，后半段伤害保险，原话“really good damage for us in the second half”。
GRP-03 Acid must_take：`I'll lock acid as well.` / `And we'll take the acid again as well cuz my max HP remains really poor.` → must_take / note：血少复购补血，原话“take the acid again”。

## 分组段 wishlist（3 例，想要+持续追≥2 没拿到，非整活；单次随口不进）

判法：点名想要（want/need/looking for 原话）+ 寻找行为≥2（roll/lock/留钱/抱怨没出，须两条不同 quote 作证），非整活（joke/meme 口吻不进）。单次随口（只有一句想要、无追）不进 wishlist，进 casual_mention。
note 强制披露没拿到（须含“没拿到”或“未拿到”，缺披露即 fail）+ 短引逐字。

GRP-04 Small Magazine wishlist：`I really want a small magazine for this build.` / `I'm rolling for small magazine, still nothing.` / `I'll keep my money, still no small magazine.` → wishlist / note：全程想要+连 roll 留钱追，没拿到，原话“rolling for small magazine”。
GRP-05 Incendiary Turret wishlist：`I want an incendiary turret so bad.` / `Where is my incendiary turret, come on.` → wishlist / note：点名要+抱怨没出，没拿到，原话“Where is my incendiary turret”。
GRP-06 Coil 反例不进（单次随口）：`Coil could be nice I guess.`（仅一句，无 roll/lock/留钱/抱怨第二证）→ 不进 wishlist，进 casual_mention / note：单次随口无追，原话“Coil could be nice”。

## 分组段 taken（3 例，拿/锁了且无明确不拿，usefulness 无下文；锁/买=拿）

判法：拿/锁实锤（buy/lock/take/pick up 原话，举证责任倒置：锁/买=拿，除非有明确不拿 skip/recycle/sell/ban 原话才算反悔）+ usefulness 无下文（后文无战果/体系位解释）。有战果进 must_take；有持续追+想要进 wishlist；有明确不拿进 mentioned_not_taken/ban。
note 强制披露无下文（须含“无下文”，缺披露即 fail）+ 短引逐字。

GRP-07 Coffee taken（买两次无下文，原 GRP-09 修订）：`Take the nuke launcher and buy coffee.` / `We'll buy coffee.` → taken / note：买两次但后文无战果解释，无下文，原话“buy coffee”。
GRP-08 Beanie taken（锁了无反悔无下文）：`I'll lock beanie for now.` / `We locked beanie, let's roll.` → taken / note：锁了无反悔但无战果，无下文，原话“lock beanie”。
GRP-09 Mutation taken（单锁+买无下文，原 GRP-10 修订）：`I will take a jelly and we'll lock a mutation and then I'll roll.` / `And then I'll buy a mutation.` → taken / note：锁+买但无战果解释，无下文，原话“lock a mutation”。反例：若锁后有持续追（`still rolling for mutation` + `need mutation`）可升 wishlist/must_take，不锁死 taken。

## 分组段 mentioned_not_taken（2 例，明确没拿/跳过；无购买无锁）

GRP-10 Landmines mentioned：`Also, I'm just pretty much ignoring what the landmines are doing.` / `But you'll notice that I'm basically completely ignoring the landmines.` → mentioned_not_taken / note：全程 ignoring 没拿，原话“ignoring what the landmines are doing”。
GRP-11 Peacock mentioned（本波不拿≠永久 ban）：`I definitely am not taking a peacock this wave.` → mentioned_not_taken / note：本波跳过不清算，原话“not taking a peacock this wave”。

## 分组段 ban（3 例，ban 语义替代拒绝动词表：ban / recycle / sell 原话即 ban，看语义不背表）

GRP-12 Boxing Glove ban：`Uh, I'm going to ban the boxing glove.` → ban / note：明说 ban，直接出局原话“ban the boxing glove”。
GRP-13 White Flag ban：`We'll ban white flag and get our free roll off of that.` → ban / note：ban 换免费 roll，原话“ban white flag”。
GRP-14 Recycle 语义 ban：`I think I'm just going to recycle that.` → ban / note：recycle 即出局语义，原话“going to recycle that”。

## 分组段 casual_mention（2 例，纯嘴提：无购买无锁，低频路过照旧，不升格）

判法收窄：只有嘴提（see/could be/nice 等），无 buy/lock/take/pick up 原话，也无想要+追。有买/锁即至少 taken（举证责任倒置），不许塞回 casual。

GRP-15 Jelly casual 纯嘴提：`That jelly could be good sometime.` → casual_mention / note：纯嘴提无购买无锁，原话“jelly could be good”。
GRP-16 Scope casual 纯路过：`I saw a scope in the shop, anyway moving on.` → casual_mention / note：路过一提无后文，原话“saw a scope in the shop”。

## note 人话（≤120 字 + 短引逐字 + 披露）

人话一句 + 短引（短引逐字出自本条 quotes）。
Top1 落 must_take 首条，note 开头点明（见 GRP-02“本局最关键”），码只验非空不验排名。
wishlist note 须含“没拿到”或“未拿到”（缺披露即 fail）；taken note 须含“无下文”（缺披露即 fail）。
显示层：攻略页必拿区 = must_take + wishlist（wishlist 强制“没拿到”标记+原话）；taken 单独一区排必拿与 ban 之间。
