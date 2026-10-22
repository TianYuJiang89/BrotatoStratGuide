# Step 09 — Assemble 组装（B-段2，#66 对齐新链）

你是组装器。只读相对路径，只写相对路径。禁 `..` 与绝对盘符。旧 SOP 只作参考，不作输入；旧链冻结，不新增规则。不做翻译、不做归一、不重评，只聚合。

## 输入（cwd = `G:/brotato-work/<slug>/<variant>/`，只认实际产出名）

- `steps/03-grouping/grouping.json`（= `outputs/groups.json`，新 schema #62：`{name_en,count,group,quotes,analysis,note,quote_details}` 四组，`count==len(quotes)`，N 全量由 discovery 定）。
- `steps/04-attributes/ratings.json`（= `outputs/ratings.json`，新 schema #60：39 全量 `{term_en,rating,quotes,analysis,summary,quote_details}`）。
- `steps/05-weapons/weapons.json`（= `outputs/weapons.json`，新 schema #61：`{t1[],t2[]}` 每条 `{name_en,count,tier,quotes,analysis,note,copies,quote_details}`，`count==len(quotes)`，T1+T2==candidates）。
- `steps/06-phases/phases.json`（= `outputs/phases.json`，新口径 #63：运营波次自定义 N 动态，上游 `buckets.json`（segmentation）+ `wordings.json`（wording×N）+ `per_phase/*`，终稿 `phases.json`；phase 不抄作者章题，waves 原话作证）。
- `steps/07-priorities/priorities.json`（= `outputs/priorities.json`，新口径 #65：TopN 动态 N 由 selection 定，上游 `selection.json`（定双 TopN+synthesis 五句）+ `per_item/*`（wording），`shop∩T1=∅`、`shop∩ban=∅`）。
- `steps/08-pitfalls/pitfalls.json`（= `outputs/pitfalls.json`，新口径 #64：N 动态可空，上游 `candidates.json`（discovery）+ `wordings.json`（wording×N）+ `per_pitfall/*`，`quotes==seeds+extra` 原序，ban 名 scope 约束）。
- `inputs/manifest.json`（sha + URL，组装一致性锚点）+ `inputs/meta.json`（标题/chapters 备查）。

## 输出（只写这一件）

- `steps/09-assemble/guide.json`（= `outputs/guide.json`，内容一致，sha 对上）：
  `{slug, variant, covers, sha, url, title, groups, ratings, weapons, phases, priorities, pitfalls}`
  - `slug/variant/covers`：拷 manifest（variant-id 单真源，covers 只读展示）。
  - `sha`：拷 manifest sources[0].sha1（与 `source.vtt` 实际 sha 一致，缺 sha 即 fail）。
  - `url/title`：拷 manifest/meta（取材登记，不编数字）。
  - `groups/ratings/weapons/phases/priorities/pitfalls`：逐字聚合各步终稿 JSON（深拷贝，不改写、不重排、不截断）。

## 组装契约（沿 #39 Q6/Q8 + #45，#66 锁死六节）

- 聚合即复制：guide 内各节必须与对应 steps 终稿文件逐字相等（`guide.groups == grouping.json` 等，`sha` 对上 manifest）；任何改写、重排、截断即fail。
- 产物过程分家：以下过程件不进 guide（缺节也不补，出现即 fail）：`candidates.json` / `selection.json` / `discovery.json` / `discovery-chunk-*.json` / `buckets.json` / `segmentation.json` / `wordings.json` / `ranking.json` / `per_item/*` / `per_phase/*` / `per_pitfall/*` / `per_weapon/*` / `per_attr/*` / `agent-*.log.jsonl` / `fewshot*.md`。guide 只含六节终稿 + 元数据。
- 主脚本同时写 `steps/09-assemble/guide.json` + `outputs/guide.json`（内容一致，双写）。
- DAG（#66 02 已退役）：09 依赖 03+04+05+06+07+08（01→{03,04,05,06,08}→07→09）；B 闭环成立条件为 09 组装一致 + 各步 check 全绿。
- 缺节 fail loud：六节任一缺件即整步 fail，不回落、不补空、不编数字。
- 不含多变体复制、不含取证链（只认 VTT 输入）、不含 docs 渲染（旧链冻结线，另票）。

## 验收行（机检，无人看）

- 机检（`check_09` 即 `check_segment2.py` 09 段）：双写一致（steps/guide == outputs/guide）；六节逐字聚合一致；`sha` 对上 manifest + `source.vtt` 实际 sha；audit 有 09-assemble 六节清单对应节（缺节即 fail）。
