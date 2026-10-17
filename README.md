# BrotatoStratGuide 生产链 (#14 流程落地加首批验证)

手册 `docs/sop/` 落主干，新 session 显式调用可恢复共识；首批真角色工程师落链（Ultimate Guide 真片 Top3 + 双标注）。
名录 64（本体 50 + Abyssal 14）与术语主 17 + 次级 22 全量两表单源落地，
武器注册表首批 3+1（SMG/Pistol/Minigun + Wrench），道具首批 4。取材 Top3 + 双标注 + 巡检徽标落链：
难度只认三档、娱乐局永不作主候选、抽取只做两件且纠专名、
旧日期挂待重审、资源失效挂资源待重审、缺项挂待补徽标可发布。
页面纯静态、单模板复用、中文、手机可读、Pages 可开、离线双击可开可读。

## 构建（产物人不手改，只改源码重构建）

```bash
python scripts/build.py --slug engineer  # 按角色（首批真角色，Top3 真片）
python scripts/build.py --slug cyborg   # 按角色（演示占位，待补）
python scripts/build.py --all            # 全量 (64 索引，2 可点：cyborg + engineer)
python scripts/check.py docs/cyborg.html # 单页机检：段序 + 术语全量角标排序图标 + 取材门禁
python scripts/check_updates.py          # 基线 + 追加规则 + 取材日期巡检（旧日期待重审）
python scripts/check_resources.py        # 注册表 + 应急空目录（--live 全量 HEAD 挂资源待重审）
python -m pytest -q                      # 全套测试
mypy scripts/build.py scripts/check.py scripts/check_updates.py  # 类型检查
```

- 源码唯一可改：`data/roster.json` (64) + `data/terms.csv` (17+22) + `data/wiki-cache.json` (唯一 URL 源) + `data/builds/<slug>.json` (视频口径 ratings)
- 空壳：`templates/character.html` + `templates/index.html`（A 长文式）
- 产物：`docs/<slug>.html` + `docs/index.html`（git 跟踪，人不手改）
- 应急：`assets/` 平时空 + `.gitkeep`，只切开关时人工拉低分缩略图（合规见 #12）
- 本地看：双击 `docs/index.html`（无需端口）；或 `python -m http.server` 后打开。

## 10 段顺序（锁死不改序）

机制一句话 → 核心属性·主表 (17) → 核心属性·次级表 (22) →
武器分档 → 关键道具 → 开局/中期/后期（首句括号 W1-5 / W6-12 / W13-20，含转向点）→
升级优先级 → 商店优先级（升级在前）→ 避坑 → 高难特例 → 取材与版本。

无口径保留段标题加诚实空出（`作者未提及 / —`），不隐藏不合段。

## 写法与单源

- 正文一律中文括号英文，括号半角，英文照抄来源站（如 Life Steal 不写成 Lifesteal）。
- DLC 专属首次出现带角标 `DLC` (Abyssal Terrors DLC)，写法见页内徽标。
- 中文以客户端简中为准，`※` + `待校对` = 占位待客户端校对，不自造翻译。生命窃取示例不带待校对，其余逐项带。
- 主表随 wiki Stats 原序，次级随 wiki 次级表原序（消耗品治疗到重随价格），英文与 wiki 对齐。
- 主图标为 wiki 原图小规格热链，次级本身无图标统一 ◆ 占位，悬浮为 wiki 来源道具（多时前 10 + 等共 N 件）。
- 缓存注册表为唯一 URL 源，不存二进制，构建时内联，不运行时拉取（否则 file 协议打不开）。

## 机检

- 缺段 / 改序 / 术语对不上 / 角标缺失 / 注册表缺 URL 即 fail（退出码 1，发不出去）。
- 取材门禁错即 fail：难度非三档 / 娱乐局进 Top3 / 候选超 3 / 主候选不一致 / 链接错 / 日期非法 / 抽取含 frames-multimodal。
- 缺验收线只 warn 加徽标但可发布（退出码仍 0）：Top3 零命中诚实空缺 / 无字幕降级待补 / 未纠专名 / 双标注缺项。
- 旧次级 3 口径作废：次级必须 22，3 即 fail。

## 取材与巡检（#13）

- Top3：`source.candidates` 1 主 + 不超 2 补充，每项标题链接加标识加日期加难度加字幕有无；主须等于 `candidates[0]` 五元组；空即暂无可用主引用待补，不编娱乐局。
- 难度只认 `Danger 5 / Nightmare / Ultimate`；有 `Guide` 后缀才算教学局，否则注明实况复盘非教学局；`Tier List / Challenge / Random / Batomon` 进候选即 fail。
- 抽取只做两件：单视频元数据 + 自动字幕（`transcript: {captions: auto/none, corrected: bool}`），无字幕降级待补；含 `frames / multimodal` 即 fail；须对照 Wiki 纠专名。
- 双标注：`published` (YYYY-MM-DD) + `game_version` 齐全，占位即待补；早于 `LAST_MAJOR_UPDATE (2026-09-01)` 即待重审徽标 warn 可发布。
- 资源：`resource_review: true` 即资源待重审徽标 warn；`check_resources.py --live` 全量 HEAD 失效挂资源待重审（视频 watch 页不 HEAD，bot 墙会误报，只查注册表）。
- `check_updates.py` 默认即查各 build 取材日期 drift（人工触发复核，命中待重审 warn 不 fail）。

## 追加规则（新内容）

1. 查 Steam `1942280` 的 `dlc` 数组是否有新 App 并确认 `type: dlc` 且非 `music`（当前 `[2868390, 3281080, 4498220]`）。
2. 抓 Fandom `Characters` 表 `bt-dlc` 数量变化（当前 14），新增行即候选。
3. 对客户端简中逐项校对后再入库，未校对前标待校对不发布（`check_updates.py` 增量 `needs_review=true` 即 fail）。
4. Mod 永不进入：无 Steam App + 无游戏文件 + 无 wiki 主表即拒收（未知 slug 构建即 fail）。

## 流程落地与首批验证（#14）

- 手册：`docs/sop/new-character-guide.md`（显式调用：先读全文再读 #8，不靠记忆；人只做报角色名/选定候选/验收三件事）+ `docs/sop/character-issue-template.md`（原样填：目标角色 + 选定取材 + 执行步骤 + 禁止 + 三问验收）。
- 首批真角色：工程师（`data/builds/engineer.json`，主 `Wge0_hd9Rt8` Ultimate Guide 2026-09-01 + 补充 `QbKT2VHnqbc`，双标注 `Steam 1.1.15.1`，字幕 auto 已纠专名；T1 扳手一把一句话视频口径，T2 空诚实待补；道具炮塔/咖啡/改良工具均视频实提；商店升级两层先 Top3；避坑通用致命；高难只收高难变招）。赛博格仍演示占位待补。
- 发布：`docs/engineer.html` + `docs/index.html`（2 可点，去草稿）；三问全过即关单，不过原单批改；带待补照发（T2 空待补），排版不重验；产物人不手改，机检全绿。

## 边界（后续票，不在本票膨胀）

- 第 2 个真角色与批量生产（按玩哪个做哪个，本票只验 1 个真 + 1 演示）。
