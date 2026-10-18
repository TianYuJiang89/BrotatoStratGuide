# Step 01 — Sentences 抽取（cyborg/ultimate 试点）

你是句子抽取器。只读相对路径，只写相对路径。禁 `..` 与绝对盘符。

## 输入（只认这四件，cwd = `G:/brotato-work/<slug>/<variant>/`）

- `inputs/source.vtt`：VTT 原字幕。
- `inputs/meta.json`：标题/描述/chapters（本步不用，仅备查）。
- `inputs/registry-slice.json`：本变体武器+道具子集（本步不用，仅备查）。
- `inputs/manifest.json`：sha1 + 取材 URL（本步校验源一致性，不改写）。

## 输出（只写这一件）

- `steps/01-sentences/sentences.json`：`[{id, text}]` 数组。
  - `id`：从 1 起连续整数。
  - `text`：单句清洗后文本。

## 清洗契约（锁死，沿目录契约）

1. 按空行分块，丢时间戳行（含 `-->`）、序号行（纯数字）、头（`WEBVTT`/`NOTE`/`STYLE`/`REGION`）。
2. 去 HTML 标签（`<...>`），多行 join 为一句，strip。
3. 空句丢弃；单句 cap 500 字符（超长截断）；quotes cap 不适用于本步（本步全量）。
4. 不做翻译、不做归一、不丢弃重复句（重复即多条，保留原序）。

## 验收行（机检）

- `sentences.json` 合法 JSON 数组，每条含 `id:int` + `text:str` 非空。
- `id` 连续从 1 起，无跳号；`text` 无 `-->`、无 `<c>` 等残留标签。
- 条数与 `source.vtt` 解析 cue 数一致（本试点约 1496 句，允许 ±5 波动需说明）。
