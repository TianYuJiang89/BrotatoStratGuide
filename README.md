# BrotatoStratGuide 生产链 (#10 单源)

名录 64（本体 50 + Abyssal 14）与术语主 17 + 次级 22 全量两表单源落地，
同一赛博格页改由集中数据重渲染。页面纯静态、单模板复用、中文、手机可读、Pages 可开、离线双击可开可读。

## 构建（产物人不手改，只改源码重构建）

```bash
python scripts/build.py --slug cyborg   # 按角色
python scripts/build.py --all            # 全量 (64 索引，1 可点)
python scripts/check.py docs/cyborg.html # 单页机检：段序 + 术语全量角标排序图标
python scripts/check_updates.py          # 基线 + 追加规则：64/17+22，Mod 拒收，未校对不发布
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
- 缺验收线 / 待校对只 warn 加徽标但可发布（退出码仍 0）。
- 旧次级 3 口径作废：次级必须 22，3 即 fail。

## 追加规则（新内容）

1. 查 Steam `1942280` 的 `dlc` 数组是否有新 App 并确认 `type: dlc` 且非 `music`（当前 `[2868390, 3281080, 4498220]`）。
2. 抓 Fandom `Characters` 表 `bt-dlc` 数量变化（当前 14），新增行即候选。
3. 对客户端简中逐项校对后再入库，未校对前标待校对不发布（`check_updates.py` 增量 `needs_review=true` 即 fail）。
4. Mod 永不进入：无 Steam App + 无游戏文件 + 无 wiki 主表即拒收（未知 slug 构建即 fail）。

## 边界（后续票，不在本票膨胀）

- #11 索引全能力：搜索筛选头像回落（本票索引仅 64 覆盖 + DLC 归属 + 可点置灰）。
- #12 图标版权页脚合规：三处统一 + 署名 + 应急开关（本票仅属性两表图标 + 注册表 + 占位，页脚署名与武器道具统一交 #12）。
- #13 取材与巡检徽标：Top3 + 双标注检查（本票取材仍为演示占位）。
- #14 流程落地加首批验证：手册 + 1-2 真角色（本票先跑通单源机器链）。
