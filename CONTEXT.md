# CONTEXT.md

Single-context glossary for BrotatoStratGuide (wayfinder map #33, ticket: 目录与格式契约).

## Glossary

- **slug**: character English id (e.g. `cyborg`, `engineer`). Matches `data/roster.json` `id`.
- **variant-id**: single source of truth for a variant directory name (e.g. `ultimate`, `danger-5`, `ultimate-nightmare`). Slugified from covers; merged multi-difficulty coverage uses one id with `-` join.
- **covers**: display difficulty array (e.g. `["Ultimate"]`, `["Ultimate","Nightmare"]`). Lives inside `manifest.json` / `meta.json` only; never creates extra directories.
- **inputs/**: per-variant read-only inputs under `G:/brotato-work/<slug>/<variant>/inputs/`. Fixed four files: `source.vtt`, `meta.json` (+`subs_source=auto/manual`), `registry-slice.json`, `manifest.json` (+`subs_source`). `top3.json` stays repo-side as selection evidence, not an input.
- **steps/**: per-variant process data under `G:/brotato-work/<slug>/<variant>/steps/<step>/`. B链9步：`01-sentences/`、`02-verbs/`、`03-grouping/` + `04-attributes/`、`05-weapons/`、`06-phases/`、`07-priorities/`、`08-pitfalls/`、`09-assemble/`。
- **步骤**: B链执行单位，一步一 session，对应一份 prompts/step0X + steps/0X-*/ 落盘 + check。
_Avoid_: 段落，验收段
- **段落**: SOP §7 内容单位（十段）；多段可合入一步（04⊃主+次，07⊃升级+商店，08⊃避坑+高难）。
_Avoid_: 步骤
- **验收段**: 验收闸单位；段1 = 04+05先验，段2 = 06-09后验。
_Avoid_: 步骤
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
- **groups.json**: final grouping JSON (#48 锚+裁量，删阈值 + 删全部按名特判). ban 锚 (ban 系原话 ban/recycle/sell 或 mapped_to==ban 含 agent 补，无 Glass Cannon 例外)；must_take 锚 (拿取系原话 take/buy/pick up/lock/get/roll for 或 mapped_to 落拿取系含 agent 补 + 高频，68 件 count mean+stdev 动态 cutoff，无 ≥8/≥4 写死，本变体统一 convenient，无 core/compromise 按名分档)；mentioned_not_taken (skip 系原话 skip 或 mapped_to==skip 如 ignoring→skip 含 agent 补 + 高频)；低频路过照旧 (casual_mention)；拿不准进 candidates 位 (candidate + inferred true 标黄，字段已在 schema)；68 全收录 (count>0 全进) 保留；`reason` 人话 + 原句短引 (须出自 quotes)，禁计数泄漏；`quotes` 去重 + `quote_details` 只读。
- **ratings.json**: 04-attributes 输出 (#47 锚+裁量, 删 _S/_A/_B/_D 写死), 39 全量 (主 17 + 次级 22). `count>0` 必 S-D, `count==0` 必 `-` (作者未提及, kind none/inferred false/anchors []/confidence none) 保留; S=升级二选一赢家 (over 最长匹配, cyborg 单例 Ranged Damage, anchors 含 over 逐字), A=其余有锚 (拿取动词闭集 buy/upgrade/take/pick up, 不含 get/lock/roll, 同句窗 30/动词未否定/重叠跳过, anchors 非空逐字出自 quotes, kind anchor/inferred false/confidence verified 走绿); B/C/D=无锚裁量 (kind discretion/inferred true/confidence candidate 标黄, anchors [], 只查格式): D=有负面 (can't/don't/do not/never/without/hard/unfortunately/negative/given up/gave up/reduced/lost/lose/dangerous/avoid/-100%), B/C=无锚无负面按 count 排名上半 B(顺手)/下半 C(妥协/路过) 无绝对数; `reason` 人话 + 原句短引 (须出自 quotes), 禁计数泄漏; `quotes` 去重 + `quote_details` 只读.
- **weapons.json**: 05-weapons 输出 (#47 锚+裁量+排名制, 删 is_core_gun/绝对阈值/按名模板), `{t1[], t2[]}`. T1≥1 验收线保留; T1 锚 (kind anchor/inferred false/confidence verified 走绿, anchors 非空: verified 拿取动词 + 数字词逐字出自 quotes, 机检只认逐字) + `note` 通用模板必含把数/波次原话数字 (one/two/three/four/five/second/level/wave/1-5 须逐字出自 quotes, 不编数字); T2 裁量 (kind discretion/inferred true/anchors [], 只查格式, 标黄: 过渡/备选位); T1 判定改排名制 (registry 子集内按 score=count+verified+5 排, 最大断层切分, 不卡绝对数, 最小T1 score≥最大T2 score); `quotes` 去重 + `quote_details` 只读.
- **base**: audit-HTML dynamic root. HTML resolves `inputs/` + `steps/*/` + `outputs/` by relative path under `?base=<slug>/<variant>` + directory picker; no hardcoded absolute drive letter.
- **DAG层**: 审计视图分层 (沿 #39 Q6: `01→{02→03,04,05,06,08}→07→09`); L0 基座 (01) / L1 并行 (02→03,04,05,06,08) / L2 (07, 依赖 04/05/06) / L3 组装 (09). B-段2 已实施后 06-09 为实节 (仍缺节即 fail).
- **phases.json**: 06-phases 输出 (#45跟进+C), N=章节数 (作者 chapters 一章一段，本例 cyborg N=8，他例按实际，`phase` 名=章标题原文，`waves` 为 `{start}-{end}s` 时间窗). 每段 `{phase, waves, goal, focus, pivot, quotes, quote_details}`；分层：`buckets.json`(代码确定性分桶：`sentence.start_s` 落窗 `[start,end)`末章含`end` + 保序去重窗内全量不cap) + `wordings.json`(agent judgment：三问综合多条可执行短引出自本窗禁整句复制/模板黑话 + `extra_quotes`窗外补引用不限条数) + `phases.json`(代码合并：窗内全量前缀须等于 buckets，窗外补标 `out_of_window:true`)；非空段 `quote_details` 只读 + 对句；空段诚实空出 (`quotes==[]` + `quote_details==[]` + `goal` 写明非打法章，类比 ratings `-`，不补窗外)。
- **priorities.json**: 07-priorities 输出 (#49 去 Top3 写死 + Peacock 按名顺延，吃新分组), `{upgrades[3], shop[N]}`. 升级 Top3 沿用只认 ratings S/A 按 count 降序 (04 新评级自动跟，不另起规则); 商店 TopN 断层动态只认新 grouping must_take verified 按 count 降序 (最大断层切分，不断层多收，保底 Top1，N 动态；任一候选有拒绝动词原话即顺延，不点名，无 Top3 写死); 每项 `{name, kind, why, how_to_get, quotes, quote_details}`, `how_to_get` 原话数字不丢.
- **pitfalls.json**: 08-pitfalls 输出 (两跳: 纯警告标记产种子池 + agent提名主题扩展 + merge种子链约束), 数组 >=3 (N由agent定, cyborg 7). 每条 `{title, severity, kind, anchor, anchors, seeds, extra, why, how_to_avoid, quotes, quote_details, quote, reason, inferred}`; `severity` 为 `fatal|risky|trap` (trap须在reason论证看着赚在哪); 锚定条 `seeds` 非空 (至少一句链回seed), `anchors` 每条出自本条种子句逐字, `inferred=false` 走绿; 裁量条 `anchors=[]`, `inferred=true` 标黄永不进绿; `quotes=seeds+extra` 原序且锚定条首句是种子; glass cannon系take排除; 只认视频原话, ban 组不重复进.
- **guide.json**: 09-assemble 输出 (= outputs/guide.json 双写一致). `{slug, variant, covers, sha, url, title, groups, ratings, weapons, phases, priorities, pitfalls}`; 六节逐字聚合 + `sha` 对上 manifest + source.vtt; 只聚合不重评.
