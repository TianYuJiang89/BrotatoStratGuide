# Step 01 — Sentences 抽取（cyborg/ultimate 试点）

你是句子抽取器。只读相对路径，只写相对路径。禁 `..` 与绝对盘符。

## 输入（只认这四件，cwd = `G:/brotato-work/<slug>/<variant>/`）

- `inputs/source.vtt`：VTT 原字幕。
- `inputs/meta.json`：标题/描述/chapters + subs_source（auto/manual，本步读来源展示用）。
- `inputs/registry-slice.json`：本变体武器+道具子集（本步不用，仅备查）。
- `inputs/manifest.json`：sha1 + 取材 URL（本步校验源一致性，不改写）。

## 输出（只写这一件）

- `steps/01-sentences/sentences.json`：`[{id, text, start, end, start_s, end_s}]` 数组（B-04起统一加，供审计点跳`?t=`）。
  - `id`：从 1 起连续整数。
  - `text`：单句清洗后文本。

## 清洗契约（锁死，沿目录契约）

1. 按空行分块，丢时间戳行（含 `-->`）、序号行（纯数字）、头（`WEBVTT`/`NOTE`/`STYLE`/`REGION`）。
2. 去 HTML 标签（`<...>`），多行 join 为一句，strip。
3. 空句丢弃；单句 cap 500 字符（超长截断）；quotes cap 不适用于本步（本步全量）。
4. 不做翻译、不做归一；#43滚动折叠：去标签后词级后缀-前缀重叠去重（相邻包含即丢留最长，快照0新词自然丢），全文重建后按标点切句（.+!?后空格），句时间戳取首尾词cue时间；manual/clean无重叠自动no-op。
5. inputs/meta.json + manifest.json 含 subs_source=auto/manual（有<c>/<00:即auto），审计step1展示。

## 验收行（机检）

- `sentences.json` 合法 JSON 数组，每条含 `id:int` + `text:str` 非空。
- `id` 连续从 1 起，无跳号；`text` 无 `-->`、无 `<c>` 等残留标签。
- 折叠后整句（本试点ultimate 411句，300-600为过；1496旧数作废）；无半句复读（去重后无完全相同句），逐句读顺。
