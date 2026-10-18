# Research: YouTube 自动字幕 VTT 的滚动复读与业界处理方式

问题：`step01` 句子出现"半句→整句→半句"交替，是 `.vtt` 缺陷还是我们 API 调用问题？专业用户如何处理这类数据？

## 一线来源

- W3C WebVTT 规范（https://www.w3.org/TR/webvtt1/ ，标题 "WebVTT: The Web Video Text Tracks Format"）：cue 是**显示单元**（按时间轴上屏/消失），不是"一句话"。播放器渲染滚动字幕时以后 cue 覆盖前 cue，天然允许前后 cue 文本重叠。
- yt-dlp README（2026-10-18 拉取，179KB）：`--write-subs` 拉**人工字幕**，`--write-auto-subs` 拉**自动生成字幕**，两者是不同开关；另有 `--sub-format` / `--convert-subs` / `--sub-langs` / `--skip-download`。即：生态默认人工字幕质量更高，自动字幕是降级选项。
- youtube-transcript-api（PyPI `youtube-transcript-api` 1.2.4，作者 jdepoix）：`list()` 返回 TranscriptList，**默认优先人工字幕**，可用 `find_manually_created_transcript()` / `find_generated_transcript()` 显式挑选；`fetch()` 返回 `FetchedTranscript`，即 `[{text, start, duration}]` 的**合并后片段**，没有滚动复读。同一份自动字幕数据，走 transcript 轨道拿到的是干净片段，走 raw `.vtt` 拿到的是带 `<c>` 逐词时间戳的滚动窗口——两种形态，同一数据源。

## 结论：都不是"缺陷"，是形态用错

1. 我们的 `data/subs/*.en-orig.vtt`（yt-dlp auto-sub 原样）带 karaoke 词级标签 + 增量 cue/快照 cue 交替，是自动字幕 raw 格式的**正常形态**，API 没调错，换调法也拿不到更干净的（Brotato 这类视频没有人工字幕）。
2. 专业做法不在"换 API"，而在"parse 层折叠"：cue 按**显示事件**理解，不把每个 cue 当一句话。标准三步——去内联标签（`<c>`、时间戳）→ 丢快照/复读 cue（文本被相邻 cue 包含即丢，只留最长）→ 按时间间隔合并 + 句子切分；时间戳保留在合并后的段上（正好对上我们的 `?t=` 跳链需求）。
3. 人工字幕优先是全生态共识（yt-dlp 开关分离、transcript-api 默认偏好），所以 parse 应做成：有人工字幕用人工，没有才走自动字幕+折叠；折叠是必备项，不是可选项。

## 对本链的含义

- 修 `parse_vtt_timed`（step01）：加滚动折叠，`sentences` 从 1496 收缩；02–05 重跑，check 断言更新，#40 决议数字以重验为准。
- 输入契约加一条：`inputs/` 记 `subs_source=auto/manual`，审计 step1 输入行展示，人工字幕到了可直接替换。
