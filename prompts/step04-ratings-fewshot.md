# Step04 评级 fewshot（DRAFT 待审，看完再冻）

> 由来：5 份隔离重看（`data/work/{cyborg,engineer,ranger,doctor,one-armed}/isolation_summary.md`，
> 每份只喂字幕+玩家任务，老方案全屏蔽）cross-check 提炼。DEPRECATED 那版作废，不继承它任何一句话。
> 本文件审过后才 freeze；审之前是 draft，不进 prompt。

## 通用标准（无机制私货，无动词表，无计数，无数字帽）

评级只看机制因果强度，不数拿了几次。每个判断必须写明来源（捡 / 转 / 自带 / 挂钩），来源不明即 fail。

- **S=没它构筑不存在**：整条机制链的唯一入口。证据须是机制定义句（角色是怎么赢的）、
  或升级二选一里赢的那个、或每局必找句。宁缺毋滥，不设数量。
- **A=本体**：转出来的、出生自带的、必须保的——**零拿取也可以是 A**，只要没它后半程转不动。
  证据须是机制挂钩句 + 战力后果句。
- **B=顺手**：有明确收益句才给；价格犹豫但拿了的，犹豫本身也要写进分析。
- **C=路过**：拿了但无战力后果解释的。只描述，不升格。
- **D=冲突/毒点**：拿了挂不上钩、或作者明说不要且整局无支撑。注意区分“身份描述”（如后半波当近战打）
  和“数值冲突”（近战伤害挂不上武器）——前者不是 D。
- **`-`=作者未提及**：整局无句，固定写作者未提及。唯一保留的代码规则。

## Fewshot（逐字原话，例而不判，换角色重估）

### S1：cyborg Ranged Damage（捡来的入口）

机制：三倍率买远程，前半波爆发，后半波全转工程，elite 必须转前秒掉。远程是整条链的唯一入口。

- `You buy ranged damage at triple the normal rate, uh, which is of course incredibly strong.`
- `I'm going to take three range damage over 15 attack speed.`
- 分析：每局必找（三倍率）+ 二选一赢家（over 攻速）。入口证据，后有 `buying nine ranged damage is so good` 连买印证。
- 评级：S / summary：无脑堆，前半波秒 elite、后半波转工程全靠它。

### A1：cyborg Engineering（转来的本体，零拿取也是 A）

机制：前半波攒的远程后半波全转工程，螺丝刀吃工程保证不断档。本局工程直购减 75%、lighthouse 不值、
book 半个直接 recycle——**没有一句是捡的**，但没有它后半波只能靠建筑。

- `The way this character works is you gain extra ranged damage, but all of your ranged damage turns to engineering halfway through the wave.`
- `The reason for that is that screwdriver scales off of engineering.`
- 分析：机制定义句 + 武器挂钩句。来源=转，不是捡。拿取计数对它完全失效，数 take 会直接误判。
- 评级：A / summary：后半波本体，跟着远程走，不用专门买。

### A2：doctor Attack Speed（自带的本体）

机制：`-100%` 攻速但医疗 `+200%`，实际攻速飞快；small magazine 是远程单件最强；攻速 govern boss 击杀。
出生自带一大把，照样是骨架——来源=自带。

- `We could grab harvesting as well but the doctor gets double attack speed with medical weapons.`
- `You have minus 100% attack speed but plus 200% with medical weapons.`
- 分析：自带体系 + 全程继续买（咖啡/书/旗）。同属性在别家可能是 B，在医生就是 A——**等级是角色相对的**。
- 评级：A / summary：自带还不够，见了继续拿，boss 就靠它转。

### B1：ranger Attack Speed（重要但输给核心）

机制：被动+多发把每点攻速放大到纸面外，但同屏出现 3 远程时让路。

- `I'll take 15 attack speed, even though this is three range damage, cuz attack speed is very important.`
- 分析：明确收益（very important）+ 当场让路（even though 3 远程）。B 的标准形态：好，但不是入口。
- 评级：B / summary：见了拿，撞上远程核心就让。

### C1：cyborg Speed（路过）

- `Um, I'll take some move speed just so my move speed is positive.`
- 分析：一次补正，无战力后果。只描述，不升格。
- 评级：C / summary：路过补正，不值得找。

### D1：cyborg Melee Damage（冲突，注意区分身份与数值）

本局 8 句 melee 里 7 句是身份（后半波当近战打，如 `we're going to be a melee character for the second half`），
只有 1 句是数值冲突。身份（如 `Of course, we're going to be a melee character for the second half of every wave.`）不是 D，数值才是。

- `You can't get melee damage, so you can't scale your screwdrivers with it.`
- 分析：`can't` + 挂钩解释（screwdrivers）。与身份句无关，勿混。
- 评级：D / summary：别碰，和螺丝刀互斥。

### T1：engineer SCARF（tradeoff：危险也拿）

机制：11 波加速 spitter 天下，+敌速极危险；但 regen+移速是命。

- `Increasing enemy move speed on wave 11 is pretty dangerous, but I really want the regeneration and the move speed for us is pretty good.`
- 分析：危险承认（dangerous）+ 需求压倒（really want）。评级看需求那头，但危险必须写进 summary 让人走位还债。
- 评级：B / summary：硬拿，11 波龟缩 micro 走位还债。

## 单属性任务契约（与 411/430/415/444/415 整句配套）

输入：本 fewshot + 该角色全量整句（含 `start/end/t/context`）+ 这一个属性名（`terms.csv` 39 中之一）。
输出：`{term_en, rating, quotes, analysis, summary, quote_details}`。

- `analysis` 必写：来源（捡/转/自带/挂钩）→ 机制效果 → 评级。不许数字（几次、排第几）。
- `quotes` 逐字，去重；`quote_details` 等长平行带 `t`；`summary` ≤120 字 + 短引（出自 quotes）。
- 犹豫/tradeoff/未知一律写进 analysis（如 small fish 是否吃双倍未知就标未知），不藏。
- 缺句/编 quote 即 fail loud。`count` 只活审计字段，prompt 里不许出现。
- 攻略页只读 `rating + summary`；审计存全过程。`count==0` 必 `-`。
