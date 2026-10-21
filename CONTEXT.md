# CONTEXT.md

Single-context glossary for BrotatoStratGuide (wayfinder map #33, ticket: 目录与格式契约).

## Glossary

- **slug**: character English id (e.g. `cyborg`, `engineer`). Matches `data/roster.json` `id`.
- **variant-id**: single source of truth for a variant directory name (e.g. `ultimate`, `danger-5`, `ultimate-nightmare`). Slugified from covers; merged multi-difficulty coverage uses one id with `-` join.
- **covers**: display difficulty array (e.g. `["Ultimate"]`, `["Ultimate","Nightmare"]`). Lives inside `manifest.json` / `meta.json` only; never creates extra directories.
- **inputs/**: per-variant read-only inputs under `G:/brotato-work/<slug>/<variant>/inputs/`. Fixed three files (#61 slice 已退役): `source.vtt`, `meta.json` (+`subs_source=auto/manual`), `manifest.json` (+`subs_source`). `top3.json` stays repo-side as selection evidence, not an input.
- **steps/**: per-variant process data under `G:/brotato-work/<slug>/<variant>/steps/<step>/`. B链9步：`01-sentences/`、`02-verbs/`、`03-grouping/` + `04-attributes/`、`05-weapons/`、`06-phases/`、`07-priorities/`、`08-pitfalls/`、`09-assemble/`。
- **步骤**: B链执行单位，一步一 session，对应一份 prompts/step0X + steps/0X-*/ 落盘 + check。
_Avoid_: 段落，验收段
- **段落**: SOP §7 内容单位（十段）；多段可合入一步（04⊃主+次，07⊃升级+商店，08⊃避坑+高难）。
_Avoid_: 步骤
- **验收段**: 验收闸单位；段1 = 04+05先验，段2 = 06-09后验。
_Avoid_: 步骤
- **重试**: 同输入同 cwd 不改 workflow 再调一次子 agent（transient/缺件/格式错，预算内自动）；check 红灯永不重试。
_Avoid_: 重跑
- **重修**: 改 prompt/代码后再跑；check 红灯唯一正路。
_Avoid_: 重跑，重试
- **复用**: 已绿步骤跳过不跑（存在 + schema 绿即 SKIP）；`--force-step` 才覆盖。
_Avoid_: 跳过，缓存
- **幂等**: 同输入同代码必出同文件；确定性代码步覆盖须逐字节一致，否则 fail；sentences 1496/折叠后 411 为不变式，偏差即 fail。
- **过程审计视图**: `templates/audit.html` 常设资产，每步 check 与审计节一一对应；测试读 G 盘，正式随产物发布，不由 agent 生成。
_Avoid_: 测试报告
- **outputs/**: per-variant final product under `G:/brotato-work/<slug>/<variant>/outputs/`. Pilot: `groups.json`; B-段1加 `ratings.json` + `weapons.json` (与 steps/04-*/05-* 一致, sha 对上). B-段2加 `phases.json` + `priorities.json` + `pitfalls.json` + `guide.json` (与 steps/06-*/07-*/08-*/09-* 一致, guide.sha 对上 manifest).
- **sentence record**: `{id, text[, start, end]}`；start/end 可选（B-04 起统一加，供审计点跳 `?t=`）；VTT parse #43滚动折叠（去标签+词级重叠去重+标点切句，manual自动no-op），无半句复读； strips HTML, cap 500 chars, quotes 全量无cap (#42跟进: 去掉10条截断, 去重保留).
- **context**: `quote` 外另加前后 1-2 cue 只读字段，只给人看，不进机检；`quote` 保持逐字原文（verified 锚点）。
- **verb record**: `{verb, object_norm, sentence_id, quote}` + discretion fields (`surface_verb, mapped_to, inferred`); closed 10 verbs (take/buy/pick up/lock/get/roll for/ban/recycle/sell/skip) are lower bound (#48 不动); 转述表改种子 + agent 补 (种子保留，agent 补的每条记 surface_verb/mapped_to/reason 进 candidates，不加字段；check 只查格式)。
- **verified**: exact `name_en` match (case-insensitive) + closed verb + verbatim quote; machine-green anchor.
- **candidates**: agent discretion (alias norm / verb paraphrase 种子 + agent 补 / no-verb intent), each with `surface + normalized_to/mapped_to + quote + reason`; `mapped_to` 必落闭集 10 之一；`inferred:true` 仅无动词意图，`inferred:false` 为有动词映射；audit-HTML yellow, never machine-green；check 只查格式 (surface+quote+reason、inferred bool)。
- **surface**: verbatim word in subtitle; **object_norm**: normalized to registry `name_en`; **mapped_to**: paraphrase target in closed 10.
- **quote_details**: `[{quote, start, end, t, context}]`, 与 `quotes` 等长平行; `?t=` 跳链 + 只读 context 用, 不进机检; `quotes` 展示去重, `count` 口径不动.
- **groups.json**: 03-grouping 输出 (#62: frozen fewshot `prompts/step03-grouping-fewshot.md` 20-shot 只读 + discovery/evidence/grouping-ranking 三段 agent; #48/#50 锚+裁量口径作废，以手册为准), 数组全量 `[{name_en, count, group, quotes, analysis, note, quote_details}]`，四组 `must_take | mentioned_not_taken | ban | casual_mention`；`tier/confidence/inferred/has_verb/verb/verb_type/mapped_to/reason` 全退役 (出现即 fail)；`count` 由代码回填 (=len(quotes)，agent 不填)；`quotes` 去重逐字出自整句 + `quote_details` 等长平行 `t` 合法只读；`analysis` 全过程 (来源→机制→分组)；`note` ≤120字人话+短引 (短引逐字出自 quotes，码保)；ranking 四组须==candidates 自洽，可推翻 evidence 建议，拿 quote 说话。攻略页只读 `group+note`，审计存全过程。
- **ratings.json**: 04-attributes 输出 (#60: frozen fewshot + for-loop 单属性 agent×39; #47/#50 锚+裁量口径作废，以 `prompts/step04-ratings-fewshot.md` 为准), 39 全量 (主 17 + 次级 22). 每条 `{term_en, term_zh, type, count, rating, quotes, analysis, summary, quote_details}`；`anchors/confidence/kind/inferred/reason` 四件退役 (出现即 fail)；`count` 由代码现场扫回填 (agent 不填，含 count 即 fail)；`count>0` 必 S-D，`count==0` 必 `-` (作者未提及，`quotes==[]` + `quote_details==[]` + `summary` 写作者未提及，唯一保留的代码规则)；SABCD 语义只看机制因果强度 (S=没它构筑不存在/A=本体/B=顺手/C=路过/D=冲突毒点/-=未提及)，不数拿取、不设 S/A 数量帽；`analysis` 全过程 (来源捡转自带挂钩缺席→机制→评级，不许数字，犹豫/tradeoff/未知一律写进)；`summary` ≤120字禁计数泄漏 (短引若有须出自 quotes)；`quotes` 去重逐字出自整句 + `quote_details` 等长平行 `t` 合法只读。攻略页只读 `rating+summary`，审计存全过程。
- **weapons.json**: 05-weapons 输出 (#61: frozen fewshot 按任务拆三本 `step05-discovery-fewshot.md` / `step05-evidence-fewshot.md` / `step05-ranking-fewshot.md` + discovery/evidence/ranking 三段 agent; #47/#50 锚+裁量口径作废，以三本手册为准), `{t1[], t2[]}`. 每条 `{name_en, count, tier, quotes, analysis, note, copies, copies_quote, quote_details}`；`confidence/kind/inferred/anchors/score/reason` 六件退役 (出现即 fail)；`count` 由代码回填 (=len(quotes)，agent 不填)；`quotes` 去重逐字出自整句 + `quote_details` 等长平行 `t` 合法只读；`analysis` 全过程 (来源→机制→分档)；`note` ≤120字人话+短引 (短引逐字出自 quotes，码保)；`copies` 配比人话+`copies_quote` 逐字 (judgment 不是数数，未提及须空 quote，码保)；T1≥1 由 ranking 保，可推翻 evidence tier，切分拿 quote 说话禁数帽；T1+T2==candidates 自洽。攻略页只读 `tier+note`，审计存全过程。
- **candidates.json**: discovery 输出 (`steps/03-grouping/candidates.json` 道具 + `steps/05-weapons/candidates.json` 武器)，数组全量 `[{name_en, count, quotes, quote_details}]` (completeness 归 discovery，slice 已退役；`count`=len(quotes))；03 侧逐个打勾（收/丢覆盖词汇全表， verdict 落 `discovery-chunk-*.json` + `discovery.json` 分片表，缺件即 fail）。
- **fewshot 快照**: 运行输入 provenance (03 `steps/03-grouping/fewshot.md` 单本 + 05 `steps/05-weapons/fewshot-discovery.md` / `fewshot-evidence.md` / `fewshot-ranking.md` 三本 + 07 `steps/07-priorities/fewshot.md` 单本)，须与 repo `prompts/step03-grouping-fewshot.md` / `step05-discovery-fewshot.md` / `step05-evidence-fewshot.md` / `step05-ranking-fewshot.md` / `prompts/step07-priorities-fewshot.md` FROZEN 文件逐字节一致 (check 验相等)；审计弹窗只读此快照，file:///picker/`?base=` 全通不碰 repo。
- **审计节点公约** (#61 模范：所有 LLM 调用按此列节点)：一调用一节点，每节点只列三行——入参文件名 / prompt 文件名 / 结果文件名，点开展示原文；骨架与数据视觉可分 (数据 `dyn` 加粗)；三不许——不许过程描述、不许模板拼串 (数去结果文件里看)、不许加工视图 (药丸/badge/摘要)。
- **base**: audit-HTML dynamic root. HTML resolves `inputs/` + `steps/*/` + `outputs/` by relative path under `?base=<slug>/<variant>` + directory picker; no hardcoded absolute drive letter.
- **DAG层**: 审计视图分层 (沿 #39 Q6: `01→{02→03,04,05,06,08}→07→09`); L0 基座 (01) / L1 并行 (02→03,04,05,06,08) / L2 (07, 依赖 04/05/06) / L3 组装 (09). B-段2 已实施后 06-09 为实节 (仍缺节即 fail).
- **phases.json**: 06-phases 输出 (#45跟进+C), N=章节数 (作者 chapters 一章一段，本例 cyborg N=8，他例按实际，`phase` 名=章标题原文，`waves` 为 `{start}-{end}s` 时间窗). 每段 `{phase, waves, goal, focus, pivot, quotes, quote_details}`；分层：`buckets.json`(代码确定性分桶：`sentence.start_s` 落窗 `[start,end)`末章含`end` + 保序去重窗内全量不cap) + `wordings.json`(agent judgment：三问综合多条可执行短引出自本窗禁整句复制/模板黑话 + `extra_quotes`窗外补引用不限条数) + `phases.json`(代码合并：窗内全量前缀须等于 buckets，窗外补标 `out_of_window:true`)；非空段 `quote_details` 只读 + 对句；空段诚实空出 (`quotes==[]` + `quote_details==[]` + `goal` 写明非打法章，类比 ratings `-`，不补窗外)。
- **priorities.json**: 07-priorities 输出 (#62: frozen fewshot `prompts/step07-priorities-fewshot.md` + priority-ranking 单 agent; #49/#50 口径作废，以手册为准), `{upgrades[N], shop[N]}` (N 动态由 agent 定，码只验非空). 升级认 04 ratings term_en，商店认 grouping candidates 且禁 ban 组 (ban 件进 TopN 即 fail，可推翻 group 建议，拿 quote 说话)；每项 `{name, kind, why, how_to_get, quotes, analysis, quote_details}`，`why` 人话+短引 (短引逐字出自 quotes，码保)，`how_to_get` 原话数字不丢，未提空出不脑补；`analysis` 全过程 (来源→TopN)。
- **pitfalls.json**: 08-pitfalls 输出 (两跳: 纯警告标记产种子池 + agent提名主题扩展 + merge种子链约束; #50 收敛: 删纯语法粘连 "'d ", 情态须同句另含非情态锚才收, 去注水; take 系出局通用规则不点名), 数组 >=3 (N由agent定, cyborg 7). 每条 `{title, severity, kind, anchor, anchors, seeds, extra, why, how_to_avoid, quotes, quote_details, quote, reason, inferred}`; `severity` 为 `fatal|risky|trap` (trap须在reason论证看着赚在哪); 锚定条 `seeds` 非空 (至少一句链回seed), `anchors` 每条出自本条种子句逐字, `inferred=false` 走绿; 裁量条 `anchors=[]`, `inferred=true` 标黄永不进绿; `quotes=seeds+extra` 原序且锚定条首句是种子; take 系 verified 拿取出局 (通用, 不点名, 拿不是坑; extra 允许含 take 作解法证据); 只认视频原话, ban 组不重复进.
- **guide.json**: 09-assemble 输出 (= outputs/guide.json 双写一致). `{slug, variant, covers, sha, url, title, groups, ratings, weapons, phases, priorities, pitfalls}`; 六节逐字聚合 + `sha` 对上 manifest + source.vtt; 只聚合不重评.
