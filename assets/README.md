# assets/ 应急自托管目录 (#12)

平时空目录 + `.gitkeep`，**只校验不下载**。

- 目录约定：`assets/chars/<slug>.png`、`assets/weapons/<slug>.png`、
  `assets/items/<slug>.png`、`assets/stats/<slug>.png`。
  文件名全小写短横线，与 `data/roster.json` 的 `id` 同键风格
 （如 `well-rounded.png`，不是 `Well_Rounded.png`；
  属性 `Max HP` → `max-hp.png`，`% Reroll Price` → `reroll-price.png`）。
  `thumb` URL 原样抄 wiki（含大小写与 `%27` 转义，不自改）。
- 触发条件：只有当 wiki 连续 7 天缩略图大面积 404 或关站时，
  才由人工一次性拉取**低分辨率缩略图**（`60px/20px`，不拉原图）进 `assets/`。
- 切换：`python scripts/build.py --use-local-assets --slug <slug>` /
  `--all` 一键把图标 `src` 切到相对路径；平时构建默认 wiki 热链。
- 巡检：`python scripts/check_resources.py`（离线结构校验）；
  `python scripts/check_resources.py --live`（全量 HEAD，只读头不下载，
  404 即挂资源待重审，不自动删图）。
- 红线：不解包、不分发游戏客户端资产；截图只文字转述，不搬原片。
