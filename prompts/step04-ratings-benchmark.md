# Step04 评级基准（FROZEN，永远不变）

> 本文件是 [04-attributes 属性评级体系重构](https://github.com/TianYuJiang89/BrotatoStratGuide/issues/58) 的 resolution 资产。
> 一经合入即 freeze：以后任何角色、任何变体只当 few-shot 读，绝不改、不加分支、不加特判。
> cyborg 只当 oneshot example，例而不判，换角色重估。

## 架构（三件套，防注意力分散）

1. 本基准 prompt（只讲标准和推理示范，不读字幕）。
2. 全量字幕 `steps/01-sentences/sentences.json`（折叠后 411 整句，含 `start/end/t/context`，原样全给）。
3. for loop 39 属性（`data/terms.csv` 主 17+次 22）：每个属性独立起一个 LLM agent，
   每次只塞 `本基准 + 全量字幕 + 这一个属性名`，专门只分析这一个。
   输出该属性的 `quote + 分析 + 评级 + summary`。

`count` 由代码照旧统计仅供审计看，prompt 明令不许按频次定级。

## SABCD 标准（通用，不点名）

- **S=不堆就换个角色**：整条机制转换链的唯一入口，没有它整局转不动。须有机制定义句
  （`the way this character works is... / turns into... / scales off...`）或二选一赢家（`over`）
  或每局必找句（`triple rate / never pass`）。单变体允许 0-1 个，宁缺毋滥。
- **A=每局必找、缺了转不动**：机制骨架支柱。须有多句拿取 + 因果链
  （`cuz / so that / to stay alive` 接战力后果）+ 机制挂钩句。光一次 `take` 无后果解释不给 A。
- **B=顺手拿不亏**：单次拿取 + 明确收益句（`doing a lot of work / pretty helpful / fixes...`）。
- **C=路过过渡**：hedge 拿取（`just / some / sort of`）+ 无收益解释，或低频提及。
- **D=机制冲突/毒点**：`can't use / don't want / not worth / given up / avoid` + 机制冲突解释。
  单次拒绝不直接给 D，除非整局无拿取支撑。
- **`-`=作者未提及**：`count==0`，固定写作者未提及，不发挥。

## Frozen oneshot（cyborg/ultimate，逐字原话，例而不判）

### S：Ranged Damage

这个角色是 cyborg：开局买远程伤害是三倍率，前半波靠远程打爆发，后半波全部远程转成工程，
螺丝刀吃工程加成所以后半波不断档，打 elite 必须在转属性前秒掉。Ranged Damage 之所以是 S，
是因为它是整条转换链的唯一入口——没有它，前半波秒不掉 elite，后半波工程也没来源。

- quote：`I'm going to take three range damage over 15 attack speed.`
- quote：`You buy ranged damage at triple the normal rate, uh, which is of course incredibly strong.`
- 分析：二选一赢家（over 15 attack speed）+ 每局必找（triple rate），机制入口。
- 评级：S
- summary：无脑堆，优先于一切，前半波秒 elite、后半波转工程全靠它。

### A：Engineering

承接 S：前半波攒的远程后半波全转工程，螺丝刀吃工程加成保证后半波不断档。
Engineering 之所以是 A，是因为它是后半波的输出本体——没有它后半波只能靠建筑。

- quote：`The way this character works is you gain extra ranged damage, but all of your ranged damage turns to engineering halfway through the wave.`
- quote：`The reason for that is that screwdriver scales off of engineering.`
- 分析：机制定义句 + 武器挂钩句，多次拿取 + 因果链完整。
- 评级：A
- summary：后半波本体，跟着远程一起堆，螺丝刀越转越强。

### B：Crit Chance

螺丝刀自带暴伤加成，暴击有明确收益，但不决定整局转不转，属于顺手补强。

- quote：`And screwdrivers do really well with uh critical chance cuz they have increased critical damage.`
- 分析：单次收益句，有机制挂钩（increased critical damage），无每局必找句。
- 评级：B
- summary：顺手拿不亏，螺丝刀局可补，不强求。

### C：Speed

只为把移速补正，无战力后果解释，典型 hedge 路过。

- quote：`Um, I'll take some move speed just so my move speed is positive.`
- 分析：一次 `take` + `just so...positive`，无收益句。
- 评级：C
- summary：路过补正，不值得专门找。

### D：Melee Damage

机制冲突：螺丝刀吃不到近战，拿了也挂不上钩。

- quote：`You can't get melee damage, so you can't scale your screwdrivers with it.`
- 分析：`can't` + 冲突解释（can't scale screwdrivers）。
- 评级：D
- summary：别碰，和螺丝刀互斥。

### -：% Materials Healing

- quote：无（`count==0`）
- 分析：作者未提及。
- 评级：`-`
- summary：作者未提及。

## 单属性任务输出契约

每属性独立 agent 只输出一件：`{term_en, rating, quotes, analysis, summary, quote_details}`。

- `rating` ∈ `S/A/B/C/D/-`；`count==0` 必 `-`（唯一保留的代码规则）。
- `quotes` 逐字出自字幕，去重；`quote_details` 等长平行，必带 `t` 可点跳 `?t=`。
- `analysis` 写机制→证据→评级全链；`summary` ≤120 字中文 + 原句短引（须出自本条 quotes），禁计数泄漏，不编数字。
- 缺句/编 quote/短引不在 quotes 里即 fail loud，不回落不补空。

## 消费分离

- 攻略页（`character.html`）：只读 `rating + summary`（+ 可选 `quotes[0:1]` 点跳，由渲染器定）。
- 审计页（`audit.html`）：存全过程（基准版本 + 全量字幕 sha + 每属性 `analysis + quotes全量 + quote_details` + `count`）。
- `ratings.json` 保持全量单真源，不拆文件；`anchors/confidence/kind/inferred` 四件退役，
  关键证据由 `quotes[0]` 首条承担。
