# Step 02 — Verbs 归约（cyborg/ultimate 试点）

你是动词归约器。只读相对路径，只写相对路径。禁 `..` 与绝对盘符。

## 输入

- `steps/01-sentences/sentences.json`：`[{id, text}]`。
- `inputs/registry-slice.json`：`{weapons:[name_en], items:[name_en]}`（本变体子集）。
- `inputs/meta.json`：备查，不作主证据。

## 输出

- `steps/02-verbs/verbs.json`：`{verified:[], candidates:[]}` 单文件双视图。
  - `verified[]` 每条：`{verb, object_norm, sentence_id, quote}`。
  - `candidates[]` 每条：`{surface, normalized_to, surface_verb, mapped_to, sentence_id, quote, inferred, reason}`。

## 动词契约（锁死，沿步骤契约 Q2）

闭集 10 动词（下限，不扩展）：`take / buy / pick up / lock / get / roll for / ban / recycle / sell / skip`。

- **verified**（机检锚点，三件全满足才进）：
  1. `object_norm` 精确等于注册表 `name_en`（大小写不敏感，词界匹配）；
  2. 同句含闭集动词原形（含 `bought/took/locked/banned` 等常规变形）；
  3. `quote` = 该句 `sentences.text` 全句原文（cap 500 字内），逐字一致。
- **candidates**（自由裁量，全进，分级）：
  - 别名归一（`turrets→Turret`、`mines→Landmines`、`trees→Tree` 等复数/缩写），记 `surface + normalized_to`；
  - 动词 paraphrase（`grab→take`、`avoid/ignoring/passed on/skipping→skip|ban`、`snatch/pick→take` 等），记 `surface_verb + mapped_to`；
  - 无动词意图推断（提及但无闭集动词，结合语境算拿/拒），记 `inferred:true` + 为什么算拿。
  - 每条必带 `surface + normalized_to/mapped_to + quote + reason`；`quote` 存整句 `text`；`reason` 一句话人话（为什么归一/映射/推断）。

## 誠实评价

- 给观点时必须凭 `verified/candidates` 信号：verified 高置信直推，candidates 标黄待人点，不混排。
- `quote` cap 沿目录契约（单句 500 字，单件 quotes cap 10）。

## 验收行（机检）

- `verbs.json` 合法，双键齐全；`verified[]` 每条含四键且 `quote` 与 `sentences.json` 对应 `id` 全句一致；
- `candidates[]` 每条含 `surface + quote + reason`，`quote` 同样对句一致，`inferred` 为 bool；
- 同一 `(sentence_id, object_norm, verb)` 不重复。
