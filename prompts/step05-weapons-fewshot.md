# Step05 武器分档 fewshot（FROZEN 2026-10-21，用户已审“很好”）

> 由来：`cyborg/ultimate`（411 句）+ `ranger/ultimate`（415 句）两局实看提炼。
> cyborg 旧结论：Minigun/Screwdriver T1、SMG/Nuke T2（对上即过）。
> ranger 大 slice 教训：scan 子串命中 10 个武器名，真构筑只有弹弓主线，其余全是路过/误触——
> `Pistol` 开局 trick 即卖、`Javelin` 类别口头、`Claw` 误触 claw tree（道具树）、`Laser Gun`
> 误触 laser guns 复数泛指——子串 scope 框死分母，判法再 agent 也救不回，故 completeness 归 discovery。
> 审过即 freeze：以后任何角色、任何变体只当 few-shot 读，绝不加分支、不加特判、不设数字帽。

## 通用标准（无机制私货，无动词表，无计数，无数字帽）

分档只看构筑因果（拿了干什么、什么时候换、不拿会怎样），不数拿了几次。切分拿 quote 说话，禁数帽。

- **候选（discovery 收）**：有买/锁/升/留/转的 build 意图链（buy/lock/upgrade/use/sell 再买回都算），
  有一句逐字 quote 即收。来源不明即 fail。
- **路过（discovery 丢）**：开局 trick 即卖、类别口头、子串误触（claw tree→Claw、laser guns→Laser Gun）、
  cursed 犹豫没买、只提一次无后文。只描述，不收录。
- **T1=carry/主力**：整局扛伤害或体系入口，没它构筑不存在。证据须是机制挂钩句 + 把数/波次后果句。
- **T2=过渡/备选**：前中期过渡、有 T1 即换、不升满。证据须是过渡位人话 + 短引。
- **`note` 人话**：一句人话 + 一句短引（含把数/波次数字，原话逐字：second/four/horde wave/70,000 等）。
  攻略页只读 `tier + note`；审计存全过程。`count` 只活审计字段（=len(quotes)），prompt 里不许出现。

---

## DISCOVERY 真 vs 路过（10 例：6 收 4 丢）

### DIS-01（收）：Slingshot 买链（ranger 主线）

- name_en=`Slingshot`（词汇表一字不差）

- `So we're going to be using slingshot.`
- `And the reason for this is that slingshot gives us the primitive weapon tag.`
- `We'll buy a slingshot.`
- `We'll lock fertilizer, ban glasses, and then reroll, buy a slingshot, ban toxic sludge, and roll and buy another slingshot.`
- 判定：收。用/买/锁链完整（using→buy→lock→buy another），primitive tag 体系入口。

### DIS-02（收）：Minigun 后期转（ranger 后期）

- name_en=`Minigun`

- `Okay, minigun gives me a lot of healing from life steal as well.`
- `So, I think I will sell this slingshot, buy the minigun.`
- `And then the minigun was really nice giving me a bunch of life steal, and of course uh dealing the most damage.`
- 判定：收。卖弹弓买 minigun + 战果句（most damage），后期转有实据。

### DIS-03（收）：Screwdriver 体系（cyborg 主力）

- name_en=`Screwdriver`

- `The easiest way to win with the cyborg is to use screwdrivers in addition to your ranged weapons.`
- `The reason for that is that screwdriver scales off of engineering.`
- `We'll buy a screwdriver.`
- `Buy another screwdriver.`
- 判定：收。win 法 + 挂钩（scales off engineering）+ 连买。

### DIS-04（收）：SMG 过渡（cyborg 备选）

- name_en=`SMG`

- `That would be the ideal, but SMG does a a reasonable minigun impression.`
- `It's the Walmart minigun.`
- 判定：收。过渡位明示（reasonable impression + Walmart），虽只有 1 句也是候选（禁数帽）。

### DIS-05（收）：Medical Gun 买后卖（ranger 过渡）

- name_en=`Medical Gun`

- `And, you know, a cursed medical gun isn't uh the best weapon of all time, and we may sell it later, but it's a pretty powerful boost to our damage in the early game here, and it gives us a bunch of healing with the 81% life steal per shot that it has.`
- `Now, one thing that we do have is slightly lower HP uh because I bought the medical gun.`
- 判定：收。买了（bought）+ 早期限伤 + 声明会卖（sell later），过渡位。

### DIS-06（收）：Nuke horde 位（cyborg 备选）

- name_en=`Nuclear Launcher`（别名 nuke launcher 归一到此名）

- `Uh, so this is a ranged weapon, the nuclear launcher.`
- `We'll buy nuclear launcher.`
- `So, given that we're going into the horde wave, I'm going to take the nuke launcher, uh, which means combining here.`
- 判定：收。买 + horde wave 位，有 combining 后文。

### DIS-07（丢）：Pistol 开局 trick（ranger 路过）

- `The Ranger also tries to trick the player by starting you with a pistol, which is a pretty weak weapon and pretty bad for the character.`
- `We're going to sell this pistol immediately so that guns don't show up in the pool.`
- 判定：丢。trick + 立刻卖（immediately），无 build 意图。

### DIS-08（丢）：Javelin 类别口头（ranger 路过）

- `Only slingshots and javelins can appear from the primitive weapon category.`
- 判定：丢。类别口头，无买/用链。

### DIS-09（丢）：Claw 子串误触（ranger 路过）

- `I'm going to ban peaceful bee and I'll ban claw tree as well.`
- 判定：丢。claw tree 是道具树（Trees），不是武器 Claw。子串命中即误触，scan 口径作废。

### DIS-10（丢）：Laser Gun 复数泛指（ranger 路过）

- `So today what I'm going to do is show you a different way to beat the Ranger that makes it a little bit easier and overcomes some of the downsides of the normal build with just submachine guns and laser guns and just building guns as normal.`
- 判定：丢。laser guns 复数泛指 + submachine guns 并列，无单把 build 意图。

---

## TIER 切分（6 例：3×T1 + 3×T2，拿 quote 说话，禁数帽）

### T1-01：Minigun 主力（cyborg）

- `Obviously, we'll take a second minigun if a second minigun shows up.`
- `So our minigun was the big performer, 70,000 damage nuke launcher for 18k.`
- 分析：拿法（take second）+ 战果（big performer 70,000）。来源=捡，整局扛把子。
- 切分：T1 / note：主力连发，见第二把直接拿，原话“take a second minigun”。

### T1-02：Screwdriver 体系（cyborg）

- `The reason for that is that screwdriver scales off of engineering.`
- `But we have four screwdrivers reducing its effect.`
- `In the second half, it'll still happen sometimes, though less frequently because most of our kills are going to be with screwdriver attacks.`
- 分析：挂钩（scales off engineering）+ 四把成型 + 后半波 kills 全靠它。
- 切分：T1 / note：工程转后全靠它，原话“four screwdrivers”。

### T1-03：Slingshot 入口（ranger）

- `And the reason for this is that slingshot gives us the primitive weapon tag.`
- `So we're going to be using slingshot.`
- 分析：唯一入口（primitive tag）+ 整局 using。来源=自带转买。
- 切分：T1 / note：开局即定主线，原话“primitive weapon tag”。

### T2-01：SMG 过渡（cyborg）

- `That would be the ideal, but SMG does a a reasonable minigun impression.`
- `It's the Walmart minigun.`
- 分析：过渡明示（reasonable impression + Walmart），有 T1 即换，不升满。
- 切分：T2 / note：过渡备选，minigun 平替，原话“Walmart minigun”。

### T2-02：Nuke horde 位（cyborg）

- `Obviously, we're taking the nuke launcher for the horde wave because it's much better than an upgraded minigun on a horde wave since it clears it's an explosion.`
- 分析：horde wave 专用（for the horde wave），清场位，打 elite 靠 minigun。
- 切分：T2 / note：horde 波专用清场，原话“for the horde wave”。

### T2-03：Blunderbuss 没买（ranger 备选未遂）

- `I could potentially buy blunderbuss.`
- `If this was a level three blunderbuss, I probably would.`
- `Um I could sell my level four slingshot for the level three blunderbuss.`
- 分析：三提全是 could/would 条件句，无一次真买。备选未遂也是 T2（诚实标未遂，不升格）。
- 切分：T2 / note：三犹豫没下手，原话“could potentially buy”。

---

## NOTE 人话示范（4 例：把数/波次数字逐字，≤120 字）

- NOTE-01：`主力连发，见第二把直接拿，原话“take a second minigun”。`（数字 second 出自 quotes 逐字）
- NOTE-02：`工程转后全靠它，四把成型，原话“four screwdrivers”。`（数字 four 出自 quotes 逐字）
- NOTE-03：`horde 波专用清场，打 elite 还是 minigun，原话“for the horde wave”。`（波次 horde wave 出自 quotes 逐字）
- NOTE-04：`决赛战报：minigun 70,000 对 nuke 18k，主力无悬念，原话“70,000 damage”。`（数字 70,000 出自 quotes 逐字）

---

## 三段任务契约（与全量整句配套）

输入：本 fewshot + 该角色全量整句（含 `start/end/t/context`，原样全量，不截断）+ 武器词汇表（78，全局唯一）。

- **discovery (TASK_DISCOVERY)**：输出 `{"candidates": [{"name_en": "<词汇表一字不差>", "quotes": ["逐字出自上表，去重，≥1"]}]}`。
  completeness 归你（scan 子串已退役）；幻觉名/编 quote 即 fail；`count` 你不填。
- **evidence (TASK_EVIDENCE)**（每把独立一 agent）：输入 fewshot + 全量整句 + 这一个武器名，
  输出 `{"name_en": "<一字不差>", "tier": "T1/T2（建议）", "quotes": [...逐字...], "analysis": "来源→机制→分档", "note": "≤120字人话+短引"}`。
  空证据即 fail（S-D 必有 quotes，无 `-` 档，武器无“未提及”）。
- **ranking (TASK_RANKING)**：输入全量整句 + N 份 evidence，输出 `{"t1": [{"name_en": ..., "note": ...}], "t2": [...]}`。
  T1≥1 由你保，可推翻 evidence tier；切分拿 quote 说话，禁数帽；T1+T2==candidates 自洽，否则 fail。

缺件/编 quote/幻觉名即 fail loud，不回落不补空。`count` 只活审计字段（=len(quotes)），prompt 里不许出现。
