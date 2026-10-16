# 逐角色攻略 issue 模板（SOP 附录，原样填）

> 由 SOP 创建，执行 agent 照做，人只做选角/选片/验收。

Part of #1

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

## 执行步骤（锁死）

1. 入库字幕到 `data/subs/<slug>.en-orig.vtt`；专名对照 wiki 纠拼写（Brotato/武器/道具以 wiki 为准）。
2. 只基于字幕 + 标题/描述/chapters 写骨架：属性优先级、武器 T1/T2、道具 3–5、转向、商店/升级 Top3、避坑 1–3。不复述流水账、不翻原文、不搬截图。
3. 按 10 段模板诚实填 `data/builds/<slug>.json`：无口径 `— / 作者未提及`；`中文 (English)`；DLC 角标；S–F 上色。不编、不藏段。
4. 跑 `python scripts/build.py --slug <slug>`；绝不手改 `docs/`。机检全绿再提 PR/推分支。

## 禁止

* 不编武器把数与评级；不自造中文（未校对标 `※待校对`）；不藏空段；不把娱乐局（Tier List/Challenge/Random-Random/Batomon）当主引用；Crash Zone 后缀原样保留。

## 验收（人）

* 三问：选片对不对、转述忠不忠实、评级违不违手感。全过即 promo（去草稿标记，索引可点，关本 issue）；不过则在本 issue 批注具体段，执行 agent 按批改。
