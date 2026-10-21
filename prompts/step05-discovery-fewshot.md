# TASK_DISCOVERY（FROZEN 2026-10-21 v4：只判本批，逐个打勾收/丢）

> v4 微修（判据并复数泛指、DIS-08 兼示范只提一次、补 quote_details 半句；其余例子未动）：discovery 逐个打勾——武器表动态分片（40/批），收+丢==本批（机检：缺件/重叠/陌生名即 fail）。判对判错归 agent、心抽复核。

输出一件 JSON，不输出其它文字。

## 发现段 打勾契约

你只判随附的本批名单（动态分片之一，不判其它）。输出：
`{"收": [{"name_en": "<本批一字不差>", "quotes": ["逐字，去重，≥1"]}], "丢": ["<本批一字不差>", ...]}`

收：有买/锁/升/留/转 build 意图链（buy/lock/upgrade/use，卖了再买回也算），一句逐字 quote 即收。
丢：开局 trick 即卖 / 类别口头（含复数泛指）/ 子串误触（claw tree≠Claw，laser guns≠Laser Gun）/ cursed 犹豫没买 / 只提一次无后文。
收+丢==本批（一件恰好一次；空收可，漏判即 fail）。
幻觉名/编 quote/收空 quotes 即 fail。你不填 count / quote_details。

## 收（6 例）

DIS-01 Slingshot：`So we're going to be using slingshot.` / `slingshot gives us the primitive weapon tag.` / `We'll buy a slingshot.` / `buy another slingshot.` → 收（用→买→锁→再买，体系入口）。
DIS-02 Minigun：`Okay, minigun gives me a lot of healing from life steal as well.` / `So, I think I will sell this slingshot, buy the minigun.` / `the minigun was really nice giving me a bunch of life steal, and of course uh dealing the most damage.` → 收（卖旧买新+战果，后期转）。
DIS-03 Screwdriver：`The easiest way to win with the cyborg is to use screwdrivers in addition to your ranged weapons.` / `screwdriver scales off of engineering.` / `We'll buy a screwdriver.` / `Buy another screwdriver.` → 收（win 法+挂钩+连买）。
DIS-04 SMG：`That would be the ideal, but SMG does a a reasonable minigun impression.` / `It's the Walmart minigun.` → 收（过渡明示，1 句也收，禁数帽）。
DIS-05 Medical Gun：`a cursed medical gun isn't uh the best weapon of all time, and we may sell it later, but it's a pretty powerful boost to our damage in the early game` / `I bought the medical gun.` → 收（买了+早期限伤+声明会卖，过渡位）。
DIS-06 Nuclear Launcher（别名 nuke launcher 归一到此名）：`Uh, so this is a ranged weapon, the nuclear launcher.` / `We'll buy nuclear launcher.` / `given that we're going into the horde wave, I'm going to take the nuke launcher` → 收（买+horde 位）。

## 丢（4 例）

DIS-07 Pistol：`The Ranger also tries to trick the player by starting you with a pistol` / `We're going to sell this pistol immediately` → 丢（trick+立刻卖，无 build 意图）。
DIS-08 Javelin：`Only slingshots and javelins can appear from the primitive weapon category.` → 丢（类别口头，1 句无后文；只提一次同判丢）。
DIS-09 Claw：`I'm going to ban peaceful bee and I'll ban claw tree as well.` → 丢（claw tree 是道具树，不是武器 Claw）。
DIS-10 Laser Gun：`the normal build with just submachine guns and laser guns and just building guns as normal.` → 丢（复数泛指，无单把 build 意图）。
