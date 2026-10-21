# Step04 评级 fewshot（FROZEN 2026-10-20，用户已审“很好”）

> 由来：5 份隔离重看（`data/work/{cyborg,engineer,ranger,doctor,one-armed}/isolation_summary.md`，
> 每份只喂字幕+玩家任务，老方案全屏蔽）提炼。DEPRECATED 单 cyborg 版作废，不继承它任何一句话。
> 本文件 30 条引文已逐条机验（逐字出自各角色整句，miss 即改，不编）。
> 审过即 freeze：5 职业 × 6 档共 30 例，以后任何角色、任何变体只当 few-shot 读，绝不改、不加分支、不加特判。

## 通用标准（无机制私货，无动词表，无计数，无数字帽）

评级只看机制因果强度，不数拿了几次。每个判断必须写明来源（捡/转/自带/不买·无/缺席），来源不明即 fail；`-` 固定写作者未提及（即缺席写法）免单写。

- **S=没它构筑不存在**：整条机制链的唯一入口。证据须是机制定义句、或升级二选一里赢的那个、
  或每局必找句。宁缺毋滥，不设数量。
- **A=本体**：转出来的、出生自带的、必须保的——**零拿取也可以是 A**。证据须是机制挂钩句 + 战力后果句。
- **B=顺手**：有明确收益句才给；价格犹豫但拿了的，犹豫本身也要写进分析。
- **C=路过**：拿了但无战力后果解释的。只描述，不升格。
- **D=冲突/毒点**：拿了挂不上钩、或作者明说不要且整局无支撑。注意区分“身份描述”和“数值冲突”。
- **`-`=作者未提及**：整局零命中，固定写作者未提及。唯一保留的代码规则。
- **等级是角色相对的**：同属性在别家可以不同级（如下医生攻速 A、游侠攻速 A 但让位一次仍是 A 骨架——
  跨角色不抄级，只抄推理法）。

---

## CYBORG（ultimate，411 句）

### CYB-S：Ranged Damage（捡来的入口）

机制：三倍率买远程，前半波爆发，后半波全转工程，elite 转前秒掉。远程是唯一入口。

- `You buy ranged damage at triple the normal rate, uh, which is of course incredibly strong.`
- `I'm going to take three range damage over 15 attack speed.`
- 分析：每局必找（三倍率）+ 二选一赢家（over 攻速）。来源=捡。
- 评级：S / summary：无脑堆，前半波秒 elite、后半波转工程全靠它。

### CYB-A：Engineering（转来的本体，零拿取也是 A）

机制：前半波攒的远程后半波全转工程，螺丝刀吃工程不断档。本局工程直购减 75%、lighthouse 不值、
book 半个直接 recycle——没有一句是捡的。

- `The way this character works is you gain extra ranged damage, but all of your ranged damage turns to engineering halfway through the wave.`
- `The reason for that is that screwdriver scales off of engineering.`
- 分析：机制定义句 + 武器挂钩句。来源=转。拿取计数对它完全失效。
- 评级：A / summary：后半波本体，跟着远程走，不用专门买。

### CYB-B：Crit Chance（犹豫但拿）

机制：螺丝刀自带暴伤加成，暴击有明确收益，但 128 块 5 暴击嫌贵——犹豫本身是 B 的证据。

- `And I'll buy the blindfold cuz 128 for five crit chance isn't great, but we actually have some pretty significant benefits from crit chance.`
- `And screwdrivers do really well with uh critical chance cuz they have increased critical damage.`
- 分析：价格犹豫（isn't great）+ 机制挂钩（increased critical damage）。来源=捡，顺手位。
- 评级：B / summary：顺手拿不亏，螺丝刀局可补，不强求。

### CYB-C：Speed（路过）

- `Um, I'll take some move speed just so my move speed is positive.`
- 分析：一次补正（来源=捡），无战力后果。只描述，不升格。
- 评级：C / summary：路过补正，不值得找。

### CYB-D：Melee Damage（冲突，注意区分身份与数值）

本局 8 句 melee 里 7 句是身份（如 `Of course, we're going to be a melee character for the second half of every wave.`），
只有 1 句是数值冲突。身份不是 D，数值才是。

- `You can't get melee damage, so you can't scale your screwdrivers with it.`
- 分析：`can't`（来源=无）+ 挂钩解释（screwdrivers）。与身份句无关，勿混。
- 评级：D / summary：别碰，和螺丝刀互斥。

### CYB--：% Materials Healing（未提及）

- 整局零命中（materials healing 全文件 0 句），无 quote。
- 评级：`-` / summary：作者未提及。

---

## ENGINEER（ultimate，430 句，QbKT2VHnqbc）

### ENG-S：% Structure Attack Speed（本体中的本体）

机制：工程流杀一切靠结构，结构杀速只吃这一条，全游戏只有两件给。

- `Structure attack speed is the most important stat when you're playing an engineering build.`
- `Structure attack speed governs how fast you kill pretty much everything with structures.`
- 分析：最高级定义句（most important）+ 支配句（governs）。来源=捡（钟表黄蜂），稀缺不降级。
- 评级：S / summary：见一只拿一只，比武器升级优先。

### ENG-A：Dodge（防线本体）

机制：crash zone 结构挤中间+ nightmare 点名怪多，60 闪是质变线。

- `Once we get to 60 dodge, that gives us a pretty significant increase to our survivability.`
- 分析：阈值后果句（survivability）。来源=捡，一路从 30 堆到封顶。
- 评级：A / summary：堆到 60，活过 14/15 就靠它。

### ENG-B：% Explosion Size（顺手放大器）

机制：爆炸塔+大范围打 horde，三块塑料炸弹是真核；伤害修正半价所以只认范围不认伤害。

- `Triple plastic explosive is pretty incredible given how we are in uh partially at least an explosion-based character.`
- 分析：明确收益（incredible）+ 体系挂钩（explosion-based）。来源=捡。
- 评级：B / summary：有就拿，horde 爸爸。

### ENG-C：Luck（路过）

- `I'll take the the luck here.`
- 分析：顺手一拿（来源=捡），无后果解释（同局 cyber ball 没幸运不碰、lucky charm 随缘）。
- 评级：C / summary：路过，有用但不找。

### ENG-D：Elemental Damage（半价体系冲突）

机制：元素半价半值，sausage 约等于 1 工程但第二条不加伤，成型慢。

- `So, even though we have a scared sausage, it would be pretty slow to get enough elemental damage that it actually matters.`
- 分析：半价体系 + 速度判死（too slow to matter）。来源=不买。
- 评级：D / summary：别碰，半价追不上。

### ENG--：Bounces（未提及）

- 整局零命中（bounces 全文件 0 句），无 quote。
- 评级：`-` / summary：作者未提及。

---

## RANGER（ultimate，415 句，cYYlQ5v_3Eg）

### RAN-S：Ranged Damage（入口）

机制：被动每点远程加成 + 弹弓 80%×多发，开局就催。

- `Two life steal would have been good also, but it's so important that I start building ranged damage as early as we can.`
- `We never want to reduce our ranged damage, and then I'm going to roll here, take three ranged damage thanks to our passive.`
- 分析：开局优先级（as early as we can）+ 永不减（never reduce）+ 被动挂钩。来源=捡。
- 评级：S / summary：开局就堆，永不减。

### RAN-A：Attack Speed（放大器骨架）

机制：被动+多发把每点攻速放大到纸面外，再贵也买。

- `I'm going to need range to damage as well, but we really just want attack speed and damage as quickly as possible.`
- `I'll take 15 attack speed, even though this is three range damage, cuz attack speed is very important.`
- 分析：最快优先级（as quickly as possible）+ 贵也拿（even though 3 远程）。撞上入口让一次仍是骨架。
- 评级：A / summary：和远程一起抢，抢输一次不丢位。

### RAN-B：Harvesting（经济顺手）

机制：开局 5 收获省 roll，baby gecko 回本快（弹弓满地掉料）。

- `I could roll for ranged damage, but when we get five harvesting right from the start, we'll take it.`
- `I'll take eight more harvesting.`
- 分析：开局让路优先级（roll 让位）+ 趁早加码。来源=捡，经济位。
- 评级：B / summary：开局有就拿，中期不管。

### RAN-C：Luck（明确次选）

- `And then we'll take 10 luck as well.`
- `If only that was ranged damage, we would be so happy.`
- 分析：拿了但当场承认想要的是别的（If only）。次选的 C 标准形态。
- 评级：C / summary：路过，想要的其实是远程。

### RAN-D：Melee Damage（机制禁穿）

机制：游侠禁近战，原始池只剩弹弓+标枪。

- `Um you are very likely to find additional copies of it because as the ranger, you can't equip melee weapons.`
- 分析：机制禁令（can't equip）。来源=无。
- 评级：D / summary：别想，池子里没有你。

### RAN--：% Structure Attack Speed（未提及）

- 整局零命中（structure attack speed 全文件 0 句；本局无结构体系），无 quote。
- 评级：`-` / summary：作者未提及。

---

## DOCTOR（nightmare，444 句，B2A1le6mLP0）

### DOC-S：Ranged Damage（底伤入口）

机制：医疗枪低单发，16 波飞蛾必须一两枪点杀减弹幕，全靠 flat 撑单发。

- `We just need to increase the base damage of our weapons here.`
- `We need to increase the base damage of our weapons high enough that we're one or two tapping the enhanced flies on wave 16 as well.`
- 分析：底伤定义（base damage）+ 波次后果（one-or-two-tapping）。来源=捡。
- 评级：S / summary：堆单发，16 波飞蛾是验收线。

### DOC-A：Attack Speed（自带骨架）

机制：`-100%` 但医疗 `+200%`，实际飞快；small magazine 单件最强；攻速 govern boss。

- `We could grab harvesting as well but the doctor gets double attack speed with medical weapons.`
- `You have minus 100% attack speed but plus 200% with medical weapons.`
- 分析：自带体系 + 全程继续买。来源=自带。
- 评级：A / summary：自带还不够，见了继续拿。

### DOC-B：Harvesting（经济顺手）

机制：21 线每波+2，黑带经验好，bag 回本。

- `Uh, take the eight harvesting.`
- `I'm still looking to get to 21 or higher harvesting so it can start growing by two every wave.`
- 分析：阈值目标（21/+2）。来源=捡，经济位。
- 评级：B / summary：到 21 就停，不管了。

### DOC-C：Speed（路过）

- `And I take the nine speed just to fix my movement speed here.`
- 分析：补正（来源=捡，fix），中期有用、14 波后不想。无战力后果。
- 评级：C / summary：路过补正。

### DOC-D：Consumable Heal（体系拒收）

机制：自带 50% 吸，基本不花钱买治疗。

- `That means we pretty much never want to buy healing items on this character.`
- 分析：体系拒收（never buy healing）。来源=不买。注意：消耗品爆发回还是买的，拒的是常驻治疗位。
- 评级：D / summary：别买，吸血够了。

### DOC--：Bounces（未提及）

- 整局零命中（bounces 全文件 0 句；医疗无弹射体系），无 quote。
- 评级：`-` / summary：作者未提及。

---

## ONE-ARMED（ultimate，415 句，rctxc3DIyy0，non-normal 输入）

### ARM-S：Ranged Damage（双倍率入口）

机制：双倍率买伤，见伤就买，flat 堆到 70 单发。

- `On the one-armed, you buy damage at double rate.`
- `We just need as much of that as we can get.`
- 分析：双倍率定义 + 无限吃（as much as we can get）。来源=捡。
- 评级：S / summary：见伤就买，堆到单发 70。

### ARM-A：Range（tag 缺啥补啥）

机制：枪 tag 的 +50 范围没有，+60 也值得；ashes 补范围+60%。

- `Uh cuz range is a little better for the the one-armed than it is for other characters and we don't get range from the gun weapon tag.`
- `Fixes the range that we just talked about wanting.`
- 分析：缺席即需求（don't get）+ 补足证据（Fixes）。来源=捡。
- 评级：A / summary：tag 缺的必须买，ashes 来了锁死。

### ARM-B：HP Regeneration（生存顺手）

机制：单武器频率不到一半，吸血平时极烂，再生是命。

- `Um we do want to buy regeneration on this character because life steal is very bad for the one armed.`
- 分析：对比判死（steal very bad）+ 转向 regen。来源=捡。
- 评级：B / summary：吸血烂就转再生，sunken bell 也算命。

### ARM-C：Luck（存疑顺手）

- `I'm going to recycle the strange book here, recycle the toolbox, and then I could take 10 luck to go with my baby elephant.`
- 分析：条件句（could）+ 挂钩弱（来源=捡，配 elephant）。拿了也诚实标存疑。
- 评级：C / summary：路过，有 elephant 才拿。

### ARM-D：Life Steal（平时判死，minigun 翻转）

机制：平时频率不够判死；level4 minigun 高速后翻转——D 是情境的，不是永恒的。

- `So you get way fewer attacks than a normal character and can't really use life steal.`
- `Cuz uh even with only the one minigun, the level 4 minigun attacks so fast that life steal is going to be a very relevant healing option.`
- 分析：判死（来源=无，can't really use）+ 翻转条件（level4 高速）。两句必须同看，单看一句会误判。
- 评级：D / summary：平时别碰，转 minigun 高速才买（ritual 到 3% 也香）。

### ARM--：% Burning Speed（未提及）

- 整局零命中（burning 全文件 0 句），无 quote。
- 评级：`-` / summary：作者未提及。

---

## 单属性任务契约（与 411/430/415/444/415 整句配套）

输入：本 fewshot + 该角色全量整句（含 `start/end/t/context`）+ 这一个属性名（`terms.csv` 39 中之一）。
输出：`{term_en, rating, quotes, analysis, summary, quote_details}`。

- `analysis` 必写：来源（捡/转/自带/不买·无/缺席）→ 机制效果 → 评级。不许计数排名数字（几次、第几），原话机制阈值可写。
- `quotes` 逐字，去重；`quote_details` 等长平行带 `t`；`summary` ≤120 字 + 短引（出自 quotes）。
- 犹豫/tradeoff/未知一律写进 analysis（如 small fish 是否吃双倍未知就标未知），不藏。
- 缺句/编 quote 即 fail loud。`count` 只活审计字段，prompt 里不许出现。
- 攻略页只读 `rating + summary`；审计存全过程。`count==0` 必 `-`。
