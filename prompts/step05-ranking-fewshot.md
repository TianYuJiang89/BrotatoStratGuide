# TASK_RANKING（FROZEN 2026-10-21 v3：只切分，不编 quote；T1≥1 由你保）

输入：全量整句 + N 份 evidence。输出一件 JSON，不输出其它文字：
{"t1": [{"name_en": "<候选一字不差>", "note": "≤120字定稿人话+短引", "copies": "终定配比", "copies_quote": "逐字"}], "t2": [{"name_en": "...", "note": "...", "copies": "...", "copies_quote": "..."}]}

T1=carry/主力：整局扛伤害或体系入口。T2=过渡/备选：有 T1 即换、不升满。
可推翻 evidence tier；切分拿 quote 说话，禁数帽。
T1+T2 == 候选名单，一把不多一把不少；幻觉名即 fail。
note ≤120 字：人话+短引（短引须出自对应 evidence quotes 逐字）。
同句多引：同一原话被多把引用时判归属，只一家能拿它当判据。
配比终定：每条 copies/copies_quote 可推翻 evidence；copies_quote 须逐字出自对应 evidence quotes；evidence 写未提及你也只能写未提及。
你不输出 quotes/analysis/count。缺件即 fail。

## 切分例（6 例，3×T1 + 3×T2）

T1-01 Minigun：`Obviously, we'll take a second minigun if a second minigun shows up.` / `So our minigun was the big performer, 70,000 damage nuke launcher for 18k.` → T1（拿法+战果，整局扛把子）/ note：主力连发，见第二把直接拿原话“take a second minigun”。
T1-02 Screwdriver：`screwdriver scales off of engineering.` / `But we have four screwdrivers reducing its effect.` / `most of our kills are going to be with screwdriver attacks.` → T1（挂钩+四把成型+后半 kills 全靠它）/ note：工程转后全靠它，四把成型原话“four screwdrivers”。
T1-03 Slingshot：`slingshot gives us the primitive weapon tag.` / `So we're going to be using slingshot.` → T1（唯一入口+整局 using）/ note：开局即定主线原话“primitive weapon tag”。
T2-01 SMG：`SMG does a a reasonable minigun impression.` / `It's the Walmart minigun.` → T2（过渡明示，有 T1 即换）/ note：过渡备选 minigun 平替原话“Walmart minigun”。
T2-02 Nuke：`we're taking the nuke launcher for the horde wave because it's much better than an upgraded minigun on a horde wave` → T2（horde 专用清场）/ note：horde 波专用清场原话“for the horde wave”。
T2-03 Blunderbuss：`I could potentially buy blunderbuss.` / `If this was a level three blunderbuss, I probably would.` → T2（三提全是 could/would，无一次真买；备选未遂不升格）/ note：三犹豫没下手原话“could potentially buy”。

## NOTE 例（数字逐字，沿用 evidence 口径）

- `主力连发，见第二把直接拿原话“take a second minigun”。`
- `工程转后全靠它，四把成型原话“four screwdrivers”。`
- `horde 波专用清场，打 elite 还是 minigun原话“for the horde wave”。`
- `决赛战报：minigun 70,000 对 nuke 18k，主力无悬念原话“70,000 damage”。`
