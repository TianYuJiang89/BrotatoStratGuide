# 逐角色攻略 issue 模板（SOP 附录，原样填）

> 由 SOP 创建，执行 agent 照做，人只做选角/选片/验收三件事。

Part of #8

## 目标角色

* `en / zh / slug / dlc`（以 `data/roster.json` 为准，中文以客户端简中为准）：
* 示例：`Engineer / 工程师 / engineer / 本体`

## 选定取材（人已点头）

* 主取材：[标题](https://www.youtube.com/watch?v=<ID>)
  * 视频 ID：`<ID>` / 发布：`YYYY-MM-DD` / 难度：`Nightmare Guide` / 角色：`<En>`
  * 适用游戏版本：`<Steam 当前版本 / DLC 有无>`（双标注；早于最近大更新则标 `待重审`）
* 备选（≤2）：同格式，或“无”。

## 固定输入（只做 1+2）

* 元数据：`yt-dlp --print "%(title)s | %(duration_string)s | %(upload_date)s | %(description)s" --skip-download <URL>` + `--print "%(chapters)s"`。
* 自动字幕：`yt-dlp --write-auto-sub --sub-langs en-orig --sub-format vtt --skip-download -o "data/subs/<slug>.%(ext)s" <URL>`。
* 不做：Whisper 重转写、看画面帧、多模态整视频理解、Data API、第三方转写。无字幕不猜，标待补/换候选。

## 执行步骤（锁死：抽取→交叉表清零→填表）

1. 入库字幕到 `data/subs/<slug>.en-orig.vtt`；专名对照 wiki 纠拼写（Brotato/武器/道具以 wiki 为准）。
2. 跑交叉表并清零：`python scripts/build_mentions.py --slug <slug>` 建 `data/mentions/<slug>.json`，再 `python scripts/check_mentions.py --slug <slug>` 自清（提到未定级补定级、定级无命中挂名注明标题/描述/chapters，否则疑为编；只 warn 不 fail，缺表才 FAIL 必须补）。
3. 只基于字幕 + 标题/描述/chapters + 交叉表写骨架：属性优先级、武器 T1/T2（把数不限，每把一句话只认视频口径）、道具（下限弹性，至少 3 件够复现）、转向、商店/升级 Top3（两层：先 Top3 再点名，升级在前）、避坑 1–3（只收通用会死人的错）、高难特例（只收 Nightmare / Ultimate 变招）。不复述流水账、不翻原文、不搬截图。
4. 按 10 段模板诚实填 `data/builds/<slug>.json`：提过即算口径（顺手拿给 C 写明原话，全程未出现才空出 `— / 作者未提及`）；每条 rating 必须有出处（字幕原句或标题/描述/chapters 注明，无出处视为疑为编）；`中文 (English)`；DLC 角标；S–F 上色。不编、不藏段。
5. 跑 `python scripts/build.py --slug <slug>`；绝不手改 `docs/`。机检全绿（`check.py` + `check_updates.py` + `check_resources.py` + `check_mentions.py` 只 warn）再送 reviewer 块级审（drafter 不审己稿，见 `docs/sop/reviewer-checklist.md`），改完再送人三问。

## 禁止

* 不编武器把数与评级；不自造中文（未校对标 `※待校对`）；不藏空段；不把娱乐局（Tier List/Challenge/Random-Random/Batomon）当主引用；Crash Zone 后缀原样保留。

## 验收（reviewer 块级 + 人三问）

* 先过 reviewer 块级审（drafter 不审己稿，输出意见清单改完再送人）；再看三问：选片对不对、转述忠不忠实、评级违不违手感。全过即发布（去草稿标记，索引可点，关本 issue）；不过则在本 issue 批注具体段，执行 agent 按批改。
