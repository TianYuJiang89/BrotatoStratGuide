# BrotatoStratGuide 生产链骨架 (#9)

最薄端到端骨架：赛博格长文式单角色页 + 最小索引在主干可跑通。
页面纯静态、单模板复用、中文、手机可读、Pages 可开、离线双击可开可读。

## 构建（产物人不手改，只改源码重构建）

```bash
python scripts/build.py --slug cyborg   # 按角色
python scripts/build.py --all            # 全量
python scripts/check.py docs/cyborg.html # 单页结构机检
python -m pytest -q                      # 全套测试
mypy scripts/build.py scripts/check.py   # 类型检查
```

- 源码：`data/roster.json` + `data/builds/<slug>.json`
- 空壳：`templates/character.html` + `templates/index.html`（A 长文式）
- 产物：`docs/<slug>.html` + `docs/index.html`（git 跟踪，人不手改）
- 本地看：双击 `docs/index.html`（无需端口）；或 `python -m http.server` 后打开。

## 10 段顺序（锁死不改序）

机制一句话 → 核心属性·主表 → 核心属性·次级表 → 武器分档 →
关键道具 → 开局/中期/后期（首句括号 W1-5 / W6-12 / W13-20，含转向点）→
升级优先级 → 商店优先级（升级在前）→ 避坑 → 高难特例 → 取材与版本。

无口径保留段标题加诚实空出（`作者未提及 / —`），不隐藏不合段。

## 机检

- 缺段 / 改序即 fail（退出码 1，发不出去）。
- 缺验收线只 warn 加 `待补口径` 徽标但可发布（退出码仍 0）。

## 骨架边界（后续票补全，不在本票膨胀）

- #10 名录与术语单源：64（本体 50 + Abyssal 14）与主 17 + 次级 22 全量两表。
  骨架仅 2 名录 + 主 5 + 次 3 子集演示结构。
- #11 索引全能力：搜索筛选头像回落。骨架仅最小静态索引。
- #12 图标版权页脚合规：三处统一图标 + 署名 + 应急开关。骨架仅 🥔/◆ 占位保底可读。
- #13 取材与巡检徽标：Top3 + 双标注检查。骨架源数据为演示占位。
- #14 流程落地加首批验证：手册 + 1-2 真角色。骨架先跑通机器链。
