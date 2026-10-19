# Step 09 — Assemble 组装（B-段2，cyborg/ultimate 起步）

你是组装器。只读相对路径，只写相对路径。禁 `..` 与绝对盘符。旧 SOP 只作参考，不作输入；旧链冻结，不新增规则。不做翻译、不做归一、不重评，只聚合。

## 输入（cwd = `G:/brotato-work/<slug>/<variant>/`）

- `steps/03-grouping/grouping.json`（= `outputs/groups.json`，68 全收录）。
- `steps/04-attributes/ratings.json`（= `outputs/ratings.json`，39 全量）。
- `steps/05-weapons/weapons.json`（= `outputs/weapons.json`，T1/T2）。
- `steps/06-phases/phases.json`（8 段作者章节）。
- `steps/07-priorities/priorities.json`（升级 3 + 商店 3）。
- `steps/08-pitfalls/pitfalls.json`（≥3 条）。
- `inputs/manifest.json`（sha + URL，组装一致性锚点）+ `inputs/meta.json`（标题/chapters 备查）。

## 输出（只写这一件）

- `steps/09-assemble/guide.json`（= `outputs/guide.json`，内容一致，sha 对上）：
  `{slug, variant, covers, sha, url, title, groups, ratings, weapons, phases, priorities, pitfalls}`
  - `slug/variant/covers`：拷 manifest（variant-id 单真源，covers 只读展示）。
  - `sha`：拷 manifest sources[0].sha1（与 `source.vtt` 实际 sha 一致，缺 sha 即 fail）。
  - `url/title`：拷 manifest/meta（取材登记，不编数字）。
  - `groups/ratings/weapons/phases/priorities/pitfalls`：逐字聚合各步 JSON（深拷贝，不改写、不重排、不截断）。

## 组装契约（沿 #39 Q6/Q8 + #45）

- 聚合即复制：guide 内各节必须与对应 steps 文件逐字相等（`guide.groups == grouping.json` 等，`sha` 对上 manifest）；任何改写、重排、截断即 fail。
- 主脚本同时写 `steps/09-assemble/guide.json` + `outputs/guide.json`（内容一致，双写）。
- DAG：09 依赖 03+04+05+06+07+08；B 闭环成立条件为 09 组装一致 + 各步 check 全绿。
- 不含多变体复制、不含取证链（只认 VTT 输入）、不含 docs 渲染（旧链冻结线，另票）。

## 验收行（机检，无人看）

- 机检（`check_09`）：双写一致（steps/guide == outputs/guide）；六节逐字聚合一致；`sha` 对上 manifest + `source.vtt` 实际 sha；audit 有 09-assemble 对应节（缺节即 fail）。
