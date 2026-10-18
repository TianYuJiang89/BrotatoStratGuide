# CONTEXT.md

Single-context glossary for BrotatoStratGuide (wayfinder map #33, ticket: 目录与格式契约).

## Glossary

- **slug**: character English id (e.g. `cyborg`, `engineer`). Matches `data/roster.json` `id`.
- **variant-id**: single source of truth for a variant directory name (e.g. `ultimate`, `danger-5`, `ultimate-nightmare`). Slugified from covers; merged multi-difficulty coverage uses one id with `-` join.
- **covers**: display difficulty array (e.g. `["Ultimate"]`, `["Ultimate","Nightmare"]`). Lives inside `manifest.json` / `meta.json` only; never creates extra directories.
- **inputs/**: per-variant read-only inputs under `G:/brotato-work/<slug>/<variant>/inputs/`. Fixed four files: `source.vtt`, `meta.json`, `registry-slice.json`, `manifest.json`. `top3.json` stays repo-side as selection evidence, not an input.
- **steps/**: per-variant process data under `G:/brotato-work/<slug>/<variant>/steps/<step>/`. B链9步：`01-sentences/`、`02-verbs/`、`03-grouping/` + `04-attributes/`、`05-weapons/`、`06-phases/`、`07-priorities/`、`08-pitfalls/`、`09-assemble/`。
- **步骤**: B链执行单位，一步一 session，对应一份 prompts/step0X + steps/0X-*/ 落盘 + check。
_Avoid_: 段落，验收段
- **段落**: SOP §7 内容单位（十段）；多段可合入一步（04⊃主+次，07⊃升级+商店，08⊃避坑+高难）。
_Avoid_: 步骤
- **验收段**: 验收闸单位；段1 = 04+05先验，段2 = 06-09后验。
_Avoid_: 步骤
- **过程审计视图**: `templates/audit.html` 常设资产，每步 check 与审计节一一对应；测试读 G 盘，正式随产物发布，不由 agent 生成。
_Avoid_: 测试报告
- **outputs/**: per-variant final product under `G:/brotato-work/<slug>/<variant>/outputs/`. Pilot: `groups.json`; B-段1加 `ratings.json` + `weapons.json` (与 steps/04-*/05-* 一致, sha 对上).
- **sentence record**: `{id, text[, start, end]}`；start/end 可选（B-04 起统一加，供审计点跳 `?t=`）；VTT parse 复读原样保留，展示去重、count 口径不动； strips HTML, cap 500 chars, quotes cap 10 (along #17).
- **context**: `quote` 外另加前后 1-2 cue 只读字段，只给人看，不进机检；`quote` 保持逐字原文（verified 锚点）。
- **verb record**: `{verb, object_norm, sentence_id, quote}` + discretion fields (`surface_verb, mapped_to, inferred`); closed 10 verbs (take/buy/pick up/lock/get/roll for/ban/recycle/sell/skip) are lower bound, never extended.
- **verified**: exact `name_en` match (case-insensitive) + closed verb + verbatim quote; machine-green anchor.
- **candidates**: agent discretion (alias norm / verb paraphrase / no-verb intent), each with `surface + normalized_to/mapped_to + quote + reason`; `inferred:true` for no-verb intent; audit-HTML yellow, never machine-green.
- **surface**: verbatim word in subtitle; **object_norm**: normalized to registry `name_en`; **mapped_to**: paraphrase target in closed 10.
- **quote_details**: `[{quote, start, end, t, context}]`, 与 `quotes` 等长平行; `?t=` 跳链 + 只读 context 用, 不进机检; `quotes` 展示去重, `count` 口径不动.
- **groups.json**: final grouping JSON (必拿分档核心/顺手/妥协 + 提过未拿说原因 + ban说依据). `03-grouping/` draft adds `reason + count` only; pilot includes all `count>0`; 誠实评价 must cite verified/candidates signal.
- **ratings.json**: 04-attributes 输出, 39 全量 (主 17 + 次级 22). `count>0` 必 S-D (提过即算口径), `count==0` 必 `-` (作者未提及); `reason` 人话 + 原句短引, 禁计数泄漏; `quotes` 去重 + `quote_details` 只读.
- **weapons.json**: 05-weapons 输出, `{t1[], t2[]}`. T1≥1 为验收线; `note` 含把数/目标阶/何波拿换 (原话数字不丢); `quotes` 去重 + `quote_details` 只读.
- **base**: audit-HTML dynamic root. HTML resolves `inputs/` + `steps/*/` + `outputs/` by relative path under `?base=<slug>/<variant>` + directory picker; no hardcoded absolute drive letter.
- **DAG层**: 审计视图分层 (沿 #39 Q6: `01→{02→03,04,05,06,08}→07→09`); L0 基座 (01) / L1 并行 (02→03,04,05,06,08) / L2 (07, 依赖 04/05/06) / L3 组装 (09). B-段2 未开工时 06-09 为空节占位 (缺节即 fail).
