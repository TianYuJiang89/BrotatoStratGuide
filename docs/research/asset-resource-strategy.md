# 图片与图标资源策略研究：热链、自托管与版权的终稿约定

对应票：`图片与图标资源策略：热链、自托管与版权的终稿约定`（Part of #1，`wayfinder:research`，AFK）

> 一手来源调研落点，供 SOP 与 `templates/character.html` / `scripts/build.py` 直接引用。结论先行，证据在后。只定策略，不做全量下载或全角色填充。

## 结论（可直接写进 SOP）

### 1. 终稿路线：热链为主 + 缓存元数据 + 自托管只做应急开关（混合，但默认不开自托管）

- **默认终稿 = 继续热链 `https://brotato.wiki.spellsandguns.com`**，不转 `assets/` 二进制入库，不解包游戏文件。
  - 用缩略图规格，不用原图：头像/武器/道具 `60px-*.png`，属性小图标 `20px-*.png`，与原型已用规格一致（见证据 §2）。
  - 每个 `<img>` 必须带三件套（原型已实现，直接抄）：`referrerpolicy="no-referrer"` + `loading="lazy"` + `onerror="this.remove()"`，外层已有 `🥔` / `◆` 占位。断网或 wiki 挂了页面照样可读，只是图退化为占位 — 这就是“离线双击可开”的含义：**可开、可读，图按需增强**，不是离线全图。
  - 为什么默认不开自托管：① 游戏内图标著作权归 Blobfish（wiki infobox 写明 Developers Blobfish，见证据），wiki 文本走 CC-BY-SA 但图标不随之自由化，自托管二进制 = 主动再分发高清游戏资产，版权风险高于热链展示；② Steam 订阅协议默认不允许复制游戏文件再分发，解包 `.pck` 自托管直接踩线；③ 全量二进制进 `git` 会让仓库膨胀且每页仍需上百请求，自托管不省请求数，只换 host。
- **`data/wiki-cache.json` 为唯一资源注册表**（SOP 已定名，直接用）：存每个资源的 `page` / `file` / `thumb` URL + `width/height/size` + 抓取日期，不存二进制。`templates/character.html` 只从它读 URL，`scripts/build.py` 构建时把它内联进 HTML（不做运行时 `fetch`，否则 `file://` 打不开）。
- **`assets/` 只做应急开关，平时空目录 + `.gitkeep`**：目录约定 `assets/chars/<slug>.png`、`assets/weapons/<slug>.png`、`assets/items/<slug>.png`、`assets/stats/<slug>.png`，文件名全小写短横线（与 `data/roster.json` 的 `id` 同键）。只有当 wiki 连续 7 天缩略图大面积 404 或关站时，才由人工一次性拉取低分辨率缩略图（`60px/20px`，不拉原图）进 `assets/`，`build.py --use-local-assets` 一键切换相对路径。平时 CI 只校验不下载。

### 2. 版权边界（红线三条）

1. **不解包、不分发游戏客户端资产**：Godot `.pck` / Steam `depot` 里抠图再进 `git` 视为再分发，禁止。截图同理：攻略正文不贴游戏截图、不搬原片画面，只做文字转述（承取材规范票 #2“转述非搬运”）。
2. **wiki 图按“展示 + 署名 + 低分辨率”使用**：每页页脚固定版权行（见 §5），注明 `图标 © Blobfish，via Brotato Wiki (CC-BY-SA 文本 / 游戏资产原权保留)` + 链到原 `File:` 页。缩略图只用 `60px/20px`，不用原图 `images/a/a3/*.png` 直链 — 低分辨率 + 评论性使用是 fair-use 最有利的形态。
3. **wiki 文本 CC-BY-SA 4.0 合规**：页脚 Copyright Policy 链即 `https://creativecommons.org/licenses/by-sa/4.0/`（见证据 §1）。机制一句话若逐字译自 wiki，需在取材段同时链 wiki 原页 + 视频，不能只链视频。道具悬浮 `Notable Items` 同理。

### 3. 字体与样式（纯静态单模板）

- **中文字体 = 系统栈，不自带、不外链**：自带字体中文字体包数 MB（Pages 包体积 + 离线双击都要背），外链字体 `file://` 下不可控且手机流量贵。直接用原型栈，一字不改：
  ```css
  font: 16px/1.65 -apple-system, "PingFang SC", "Hiragino Sans GB", "Microsoft YaHei", sans-serif;
  ```
- **手机可读锁死三条**：`max-width:720px` 内容列、`viewport-fit=cover`、`table` 横向不溢出（`table{width:100%;border-collapse:collapse;font-size:14px}`）。`templates/character.html` 空壳照抄原型 `A` 版 CSS，不引入框架。

### 4. 与现有链路的衔接（build / check / terms 三处）

- **`templates/character.html` 引用格式**（空壳只留这一种，不许手写第二种）：
  ```html
  <img class="sic" alt="赛博格 (Cyborg)" width="34" height="34"
    src="https://brotato.wiki.spellsandguns.com/images/thumb/a/a3/Cyborg.png/60px-Cyborg.png"
    data-file="File:Cyborg.png" data-local="assets/chars/cyborg.png"
    loading="lazy" referrerpolicy="no-referrer" onerror="this.remove()">
  ```
  `src` = wiki 缩略图（`data/wiki-cache.json` 注入），`data-local` = 应急自托管相对路径（平时不用，`--use-local-assets` 时 `build.py` 把 `src` 换成它）。属性无图标时用 `<span class="sic none">◆</span>`，不挂空 `<img>`。
- **三处图标规则统一**：属性主 17 + 次级 22、武器 T1/T2、关键道具全部走同一函数 `icon(src, alt)`，规则一致：有 wiki 缩略图就挂三件套，没有就 `◆` + `作者未提及/待补`，不允许某处用原图某处用占位。次级属性本身在 wiki 无专用图标（原型已验证 `null`），统一 `◆`，悬浮 `Notable Items` 的道具小图仍用 `30px-*.png` 热链。
- **构建校验（不沿用 `check_updates.py` 旧逻辑，新增 `check_resources.py` 规则）**：
  - `scripts/build.py`：`wiki-cache.json` 缺 URL、或 `terms.csv` 中英对不上、或 DLC 角标缺失，直接 fail（缺段不发布）。`※待校对` 允许通过但强制挂 `※` 角标 + `待补口径` 徽标（warn）。
  - 新增 `scripts/check_resources.py`（不塞进 `check_updates.py`）：对 `wiki-cache.json` 全量 `HEAD` 一遍，404/5xx 即在对应逐角色 issue 挂 `资源待重审` + 本地 `state` 标红，不自动删图。`check_updates.py` 仍只管 Steam dlc 数组 + Fandom `bt-dlc` 数量 + 取材日期 vs 大更新（SOP §7 已定），两者分工不混。
- **`data/terms.csv` 联动**：`※` 只表示“中文待客户端简中校对”，不表示“图缺失”。图缺失由 `wiki-cache.json` 的 `"missing": true` 表示，构建时渲染为 `◆` + `wiki 无专用图标`。DLC 角标数据源是 `data/roster.json` 的 `dlc` 字段（`null|"abyssal"`），`terms.csv` 的 `dlc` 列只做交叉校验，不一致即 fail。

### 5. 存放目录与命名 + 版权标注位置 + ※替换规则（SOP 直接抄）

- **目录**：
  ```
  data/wiki-cache.json          # URL 注册表（唯一可改源之一）
  data/roster.json              # dlc 角标源
  data/terms.csv                # 中英对照源，※只管中文
  assets/chars|weapons|items|stats/  # 应急自托管，平时空
  templates/character.html      # 空壳，图标三件套唯一写法
  docs/<slug>.html + docs/index.html  # 构建产物，人不手改
  ```
- **命名**：`assets/` 下全小写短横线，与 `roster.json` 的 `id` 同键（如 `well-rounded.png`，不是 `Well_Rounded.png`）；`thumb` URL 原样抄 wiki（含大小写与 `%27` 转义，不自改）。
- **版权标注位置**：每页页脚固定一行（构建时注入，不手写）：
  ```html
  <footer>图标 © Blobfish，via <a href="https://brotato.wiki.spellsandguns.com/">Brotato Wiki</a>（文本 CC-BY-SA 4.0，游戏资产原权保留）· 取材视频见页顶 · 转述非搬运</footer>
  ```
  索引页同款一行 + `File:` 原页链。
- **※替换规则**：`terms.csv` 中 `※` 去掉的唯一条件 = 对着客户端简中逐项校对后（screenshot + Steam 版本号为证），由执行 agent 在逐角色 issue 里贴证后去掉，不许按 wiki 英文反猜中文、不许批量去 ※。

## 证据（一手来源，2026-10-16/17 实测）

1. **Wiki 身份与许可链（`brotato.wiki.spellsandguns.com`）**
   - 站点 `MediaWiki 1.39.10`（`api.php?action=query&meta=siteinfo` 实测：`sitename: Brotato Wiki`，`servername: brotato.wiki.spellsandguns.com`，`generator: MediaWiki 1.39.10`）。
   - 页脚三链实测（`Brotato_Wiki` HTML）：`Gaming Wikis | Terms of Use (/Term_of_Use) | Copyright Policy (https://creativecommons.org/licenses/by-sa/4.0/) | Recent Changes`。`spellsandguns.com` 主站页脚同款 `Copyright Policy -> CC-BY-SA 4.0`。结论：文本层 CC-BY-SA，游戏资产不随之自由化。
   - `Term_of_Use`（`api.php?action=parse&page=Term_of_Use`）原文：`non-transferable, non-exclusive, revocable, limited license ... solely for your own personal use` + `you shall not sell ... distribute, host, or otherwise commercially exploit the Site` + `All ... notices ... must be retained`。即：热链展示 + 保留署名可接受，整站镜像/商用分发不可。
   - 反证据：`Project:Copyrights` 页不存在（`missingtitle`），故以上页脚 + Terms 为唯一许可依据，不臆测图片独立 CC 协议。

2. **缩略图可用性与规格（热链技术可行）**
   - `HEAD https://brotato.wiki.spellsandguns.com/images/thumb/a/a3/Cyborg.png/60px-Cyborg.png` → `200 OK`，`Content-Type: image/png`，`Content-Length: 5821`，`Last-Modified: Fri, 10 Feb 2023 08:40:22 GMT`，无防盗链 403。`20px-Max_HP.png` 实测 `1469` 字节。同规格在原型 `cyborg.html` 全页去重后 **238 个 distinct `/images/thumb/...` URL**（`grep -o` 计数），按平均 1.5–6KB 估算单页全图约 0.4–1.4MB（未共享去重前），全站去重后唯一文件约数百个、总量数 MB — Pages 体量无压力，但单页上百请求必须 `loading=lazy`。
   - `api.php ... titles=File:Cyborg.png prop=imageinfo` 返回 `url: .../images/a/a3/Cyborg.png`（`size: 9132, 96x96`）+ `descriptionurl: .../File:Cyborg.png`；`File:SMG.png`（`8328` 字节）、`File:Turret.png`（`6467` 字节）同理。`extmetadata` 为空（无机器可读 License 字段），故按“原权保留 + 低分辨率展示”处理，不按 CC 二次分发。
   - `action=query&list=allimages&ailimit=5` 正常返回（含 `0.png/1.png/2.png` 等），无 API 封禁；iimage 链稳定。

3. **游戏资产归属（Steam 一手）**
   - `store.steampowered.com/api/appdetails?appids=1942280` → `type: game`，`dlc: [2868390, 3281080, 4498220]`；Fandom `Brotato_Wiki` wikitext 首段：`developed and published by Blobfish`，`Engine: Godot`。即图标著作权人 Blobfish 明确，无开放资产许可，故 §2 红线成立。

4. **原型已验证的回落（`prototype/page-variants`）**
   - `cyborg.html` / `index.html` 全站统一：`referrerpolicy="no-referrer" + onerror="this.remove()"` + 底层 `🥔`（头像）/ `◆`（无图标属性）占位 + `loading="lazy"`。索引页脚注原文：`头像来源 ... 热链 60px 缩略图，原型阶段不入库；断网时显示 🥔 占位。终稿自托管还是热链、版权边界，记入 map 雾区` — 本票即该雾区的终稿答案。
   - 次级属性 wiki 无专用图标（`DATA.attrs` 中次级 `icon: null` → `◆`），`Notable Items` 悬浮小图用 `30px-*.png` — §4 三处统一规则即把该实现锁死。

5. **构建链约束（file:// + Pages）**
   - SOP 已锁：`data/roster.json + data/terms.csv + data/wiki-cache.json + data/builds/<slug>.json` 为唯一可改源，`templates/character.html` 为空壳，`docs/*.html` 为产物人不手改。`file://` 下 `fetch(json)` 被拦，故 `build.py` 必须内联注入，不能运行时拉取 — 本策略 §4 的 `HEAD` 校验只跑在构建机/CI，不跑在浏览器。

## 待后续票确认（不阻塞本策略）

- 版本漂移维护（map 雾区已有）：`check_resources.py` 的 404 阈值（连续几天算“大面积”）与 `待重审` 挂多久自动转应急 `assets/`，由版本票定数字。
- 批量生产排期（map 雾区已有）：首批 1–2 个角色跑通 `build.py + check_resources.py` 后再谈，别提前全量拉图。
- SOP 文件补丁：`docs/sop/new-character-guide.md` §7 需追加本策略的目录/命名/页脚/※规则一行（本票决议资产已够引用，改 SOP 是执行动作，走逐角色 issue 时顺手带）。

## 资产

- 本文件：`docs/research/asset-resource-strategy.md` @ `research/asset-resources`
- 引用但不复制：`prototype/cyborg.html + index.html` @ `prototype/page-variants`（三件套与占位实现），`docs/sop/new-character-guide.md` @ `sop/new-character-flow`（链路名），取材 #2 / 基线 #3 已关票决议
