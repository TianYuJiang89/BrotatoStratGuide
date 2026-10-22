#!/usr/bin/env python3
"""新链索引页生成器 (Issue #73): 五角色 guide 一页可达.

视觉继承旧版索引页 (同 CSS/同筛选搜索/同卡片结构/同页脚署名),
只是卡片数据对接新链: 名单与字段现场读 G work, 不手写.

Deterministic-first + No silent fallback:
- 名单与核心字段只认 G work (不读旧链构建数据, 不碰旧索引页):
  `<work-root>/<slug>/<variant>/outputs/guide.json` (slug/variant/covers/sha/url/title)
  `<work-root>/<slug>/<variant>/inputs/meta.json` (published 取证日期)
  `<work-root>/<slug>/<variant>/inputs/manifest.json` (sha 对拍: guide.sha 须命中 sources[].sha1)
  另要求 `<work-root>/<slug>/<variant>/outputs/guide.html` 存在 (所链目标, 缺即死链 -> fail loud).
- 展示字段 (中文名/头像) 读 repo 现成注册表, 同样不手写:
  `data/roster.json` (zh/en/dlc) + `data/wiki-cache.json` (chars 60px 热链).
  名录缺五单中任一即 fail; 头像缺失则回落 🥔 占位 (沿旧版).
- 缺任一单任一件即整页 fail loud (exit 1, `FAIL:` 指明缺件, 不写半成品, 不静默缺卡).
- 同输入同代码必同字节 (幂等, 页内无 wall-clock).
- 看攻略 href: out 与目标同盘则相对 href (产物 bundle 可点),
  跨盘 (D: repo -> G: work) 则回退 `file://` 绝对 URI (由 --work-root 派生, 代码内无硬编码盘符).
- 测试读 G 盘 (`--work-root G:/brotato-work`), 正式随产物发布 (沿 standing).

固定五单 (增减须改码 + 改测, 发现式扫描一律不做):
  cyborg/ultimate, doctor/nightmare, engineer/ultimate, one-armed/ultimate, ranger/ultimate.
  顺序沿 data/roster.json 名录序.

用法:
  python scripts/build_new_index.py
  python scripts/build_new_index.py --work-root G:/brotato-work --out docs/new_index.html
"""

from __future__ import annotations

import argparse
import html
import json
import os
import re
import sys
from pathlib import Path
from typing import Any, NoReturn

# 固定五单 (Issue #73 回归: 五卡齐全可点; 缺一单 fail loud).
# 顺序沿 data/roster.json 名录序 (cyborg 10 < doctor 12 < engineer 13 < one-armed 35 < ranger 37).
EXPECTED: list[tuple[str, str]] = [
    ("cyborg", "ultimate"),
    ("doctor", "nightmare"),
    ("engineer", "ultimate"),
    ("one-armed", "ultimate"),
    ("ranger", "ultimate"),
]

_SHA_RE = re.compile(r"^[0-9a-f]{40}$")
_DATE_RE = re.compile(r"^\d{4}-\d{2}-\d{2}$")


def _repo_root() -> Path:
    return Path(__file__).resolve().parent.parent


def fail(msg: str) -> NoReturn:
    raise SystemExit(f"FAIL: {msg}")


def _load_json(path: Path, what: str) -> Any:
    if not path.is_file():
        fail(f"缺件即 fail: {what} 不存在: {path}")
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except json.JSONDecodeError as e:
        fail(f"格式错即 fail: {what} 非法 JSON: {path} ({e})")
    raise AssertionError("unreachable")  # fail() raises


def _href_for(out_path: Path, target: Path) -> str:
    """out 与目标同盘 -> 相对 href; 跨盘 (D:->G:) -> file:// 绝对 URI."""
    out_abs = out_path.resolve()
    tgt_abs = target.resolve()
    try:
        rel = os.path.relpath(str(tgt_abs), str(out_abs.parent))
        return rel.replace(os.sep, "/")
    except ValueError:
        return tgt_abs.as_uri()


def _abbr_for_en(en: str) -> str:
    """英文缩写 (沿旧链构建器口径): 首字母小写, 空格/连字符/下划线切分."""
    parts = re.split(r"[\s\-_]+", en)
    return "".join(p[0].lower() for p in parts if p)


def _esc(text: object) -> str:
    return html.escape(str(text), quote=True)


def _static_card(entry: dict[str, Any]) -> str:
    """静态卡片: 与底部 JS card() 同构 (旧版无 JS 首屏可读, 有 JS 重渲染自愈)."""
    dlc = entry["dlc"]
    dlc_attr = "abyssal" if dlc == "abyssal" else ""
    dlc_label = "Abyssal Terrors DLC" if dlc == "abyssal" else "本体"
    covers_txt = " + ".join(entry["covers"])
    sub = f"{entry['slug']} · {entry['variant']} · {covers_txt} · 取证 {entry['published']}"
    if entry["img"]:
        ava = (
            '<div class="ava"><span>🥔</span>'
            f'<img loading="lazy" alt="{_esc(entry["en"])}" src="{_esc(entry["img"])}" '
            'referrerpolicy="no-referrer" onerror="this.remove()"></div>'
        )
    else:
        ava = '<div class="ava"><span>🥔</span></div>'
    return (
        f'<div class="card" data-slug="{_esc(entry["slug"])}" data-variant="{_esc(entry["variant"])}" '
        f'data-dlc="{dlc_attr}" data-playable="1" data-sha="{_esc(entry["sha"])}">'
        f"{ava}"
        f'<div class="nm">{_esc(entry["zh"])} ({_esc(entry["en"])})'
        f"<small>{_esc(sub)} · SHA "
        f"<code title=\"{_esc(entry['sha'])}\">{_esc(entry['sha'][:8])}</code></small>"
        f"<small>视频："
        f"<a href=\"{_esc(entry['video_url'])}\" target=\"_blank\" rel=\"noopener\">"
        f"{_esc(entry['video_title'])}</a></small></div>"
        f'<div class="right"><span class="tag ok">● 可点</span>'
        f"<div class=\"links\"><a href=\"{_esc(entry['guide_href'])}\">看攻略</a></div></div></div>"
    )


def build(work_root: Path, out_path: Path, repo: Path) -> Path:
    """组装五卡索引 (旧版视觉); 任一缺件/错键即 fail loud, 成功才写盘."""
    roster_raw = _load_json(repo / "data" / "roster.json", "repo data/roster.json")
    if not isinstance(roster_raw, list):
        fail("格式错即 fail: data/roster.json 须为数组")
    by_id = {r.get("id"): r for r in roster_raw if isinstance(r, dict)}
    wiki_raw = _load_json(repo / "data" / "wiki-cache.json", "repo data/wiki-cache.json")
    if not isinstance(wiki_raw, dict):
        fail("格式错即 fail: data/wiki-cache.json 须为对象")
    chars = wiki_raw.get("chars")
    char_map: dict[str, Any] = chars if isinstance(chars, dict) else {}

    entries: list[dict[str, Any]] = []
    for slug, variant in EXPECTED:
        base = work_root / slug / variant
        guide_path = base / "outputs" / "guide.json"
        meta_path = base / "inputs" / "meta.json"
        manifest_path = base / "inputs" / "manifest.json"
        guide_html_path = base / "outputs" / "guide.html"

        guide = _load_json(guide_path, f"{slug}/{variant} guide.json")
        meta = _load_json(meta_path, f"{slug}/{variant} meta.json")
        manifest = _load_json(manifest_path, f"{slug}/{variant} manifest.json")
        if not guide_html_path.is_file():
            fail(f"缺件即 fail (死链不发): {slug}/{variant} outputs/guide.html 不存在: {guide_html_path}")

        if not isinstance(guide, dict):
            fail(f"格式错即 fail: {slug}/{variant} guide.json 须为对象")
        if guide.get("slug") != slug or guide.get("variant") != variant:
            fail(
                f"错位即 fail: {slug}/{variant} guide.json slug/variant 为 "
                f"{guide.get('slug')!r}/{guide.get('variant')!r}"
            )
        covers = guide.get("covers")
        if not isinstance(covers, list) or not covers or not all(isinstance(c, str) and c for c in covers):
            fail(f"格式错即 fail: {slug}/{variant} guide.json covers 须为非空字符串数组")
        sha = guide.get("sha")
        if not isinstance(sha, str) or not _SHA_RE.match(sha):
            fail(f"格式错即 fail: {slug}/{variant} guide.json sha 须为 40 位 hex")
        url = guide.get("url")
        title = guide.get("title")
        if not isinstance(url, str) or not url.startswith("https://"):
            fail(f"格式错即 fail: {slug}/{variant} guide.json url 须为 https 链接")
        if not isinstance(title, str) or not title.strip():
            fail(f"格式错即 fail: {slug}/{variant} guide.json title 缺失")

        if not isinstance(meta, dict) or not isinstance(meta.get("published"), str):
            fail(f"格式错即 fail: {slug}/{variant} meta.json published 缺失")
        published = str(meta.get("published"))
        if not _DATE_RE.match(published):
            fail(f"格式错即 fail: {slug}/{variant} meta.json published 须为 YYYY-MM-DD, got {published!r}")

        if not isinstance(manifest, dict):
            fail(f"格式错即 fail: {slug}/{variant} manifest.json 须为对象")
        sources = manifest.get("sources")
        src_list: list[Any] = sources if isinstance(sources, list) else []
        if sha not in {s.get("sha1") for s in src_list if isinstance(s, dict)}:
            fail(f"对不上即 fail: {slug}/{variant} guide.sha {sha[:8]} 未命中 manifest sources[].sha1")

        roster_entry = by_id.get(slug)
        if not isinstance(roster_entry, dict) or not roster_entry.get("en") or "zh" not in roster_entry:
            fail(f"缺件即 fail: data/roster.json 缺 {slug} 名录 (zh/en)")
        en = str(roster_entry.get("en"))
        thumb = char_map.get(en, {}).get("thumb") if isinstance(char_map.get(en), dict) else ""
        if not isinstance(thumb, str):
            thumb = ""

        try:
            guide_rel = guide_html_path.resolve().relative_to(work_root.resolve()).as_posix()
        except ValueError:
            guide_rel = f"{slug}/{variant}/outputs/guide.html"
        entries.append({
            "slug": slug,
            "variant": variant,
            "covers": list(covers),
            "sha": sha,
            "published": published,
            "video_title": title,
            "video_url": url,
            "guide_href": _href_for(out_path, guide_html_path),
            "guide_rel": guide_rel,
            "zh": str(roster_entry.get("zh")),
            "en": en,
            "dlc": roster_entry.get("dlc"),
            "img": thumb,
            "abbr": _abbr_for_en(en),
        })

    roster_json = json.dumps([{
        "slug": e["slug"], "variant": e["variant"], "covers": e["covers"],
        "sha": e["sha"], "published": e["published"],
        "videoTitle": e["video_title"], "videoUrl": e["video_url"], "guide": e["guide_href"],
        "zh": e["zh"], "en": e["en"], "dlc": e["dlc"], "img": e["img"], "abbr": e["abbr"],
        "playable": True,
    } for e in entries], ensure_ascii=False)
    static_cards = "".join(_static_card(e) for e in entries)

    page = f"""<!DOCTYPE html>
<html lang="zh-CN">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1, viewport-fit=cover">
<title>土豆兄弟 (Brotato) · 新链攻略索引</title>
<style>
:root {{ --bg:#f7f5ef; --card:#fff; --ink:#1f1b16; --muted:#7a7166; --line:#e7e0d2; --acc:#0e8a16; }}
* {{ box-sizing:border-box; }}
body {{ margin:0; background:var(--bg); color:var(--ink); font:16px/1.65 -apple-system,"PingFang SC","Microsoft YaHei",sans-serif; }}
.wrap {{ max-width:720px; margin:0 auto; padding:16px 14px 80px; }}
header h1 {{ font-size:22px; margin:14px 0 4px; }}
header p {{ color:var(--muted); margin:0 0 12px; font-size:14px; }}
.filter {{ position:sticky; top:0; z-index:5; background:rgba(247,245,239,.96); padding:10px 0; display:flex; gap:8px; flex-wrap:wrap; align-items:center; }}
.filter input[type=search] {{ flex:1 1 160px; font-size:15px; padding:9px 12px; border:1px solid var(--line); border-radius:999px; background:#fff; }}
.filter select {{ font-size:14px; padding:9px 10px; border:1px solid var(--line); border-radius:999px; background:#fff; }}
.filter label.chk {{ font-size:13px; color:var(--muted); display:flex; gap:5px; align-items:center; background:#fff; border:1px solid var(--line); border-radius:999px; padding:8px 12px; }}
.count {{ font-size:13px; color:var(--muted); margin:8px 2px; }}
.grid {{ display:grid; gap:10px; }}
.card {{ background:var(--card); border:1px solid var(--line); border-radius:12px; padding:10px 12px; display:flex; gap:12px; align-items:center; }}
.ava {{ position:relative; width:52px; height:52px; flex:0 0 52px; border-radius:12px; background:#efe9d8; overflow:hidden; }}
.ava span {{ position:absolute; inset:0; display:flex; align-items:center; justify-content:center; font-size:26px; }}
.ava img {{ position:absolute; inset:0; width:100%; height:100%; object-fit:contain; image-rendering:pixelated; background:#efe9d8; }}
.card .nm {{ font-weight:700; }}
.card .nm small {{ display:block; font-weight:400; color:var(--muted); font-size:12px; }}
.card .nm small a {{ color:var(--acc); font-weight:400; }}
.card .nm code {{ font-family:monospace; font-size:11px; background:#f2eee4; padding:0 5px; border-radius:5px; }}
.card .right {{ margin-left:auto; text-align:right; }}
.tag {{ font-size:12px; border:1px solid var(--line); border-radius:999px; padding:2px 8px; color:var(--muted); white-space:nowrap; }}
.tag.ok {{ color:var(--acc); border-color:var(--acc); }}
.links {{ display:flex; gap:6px; flex-wrap:wrap; margin-top:8px; justify-content:flex-end; }}
.links a {{ font-size:13px; background:#1f1b16; color:#fff; border-radius:999px; padding:4px 10px; text-decoration:none; }}
.empty {{ background:#fff; border:1px dashed var(--line); border-radius:12px; padding:18px; text-align:center; color:var(--muted); font-size:14px; }}
.foot {{ margin-top:16px; font-size:13px; color:var(--muted); }}
@media (max-width:480px){{ header h1{{font-size:19px;}} .ava{{width:46px;height:46px;flex-basis:46px;}} }}
</style>
</head>
<body>
<div class="wrap">
<header>
<h1>土豆兄弟 (Brotato) · 新链攻略索引</h1>
<p>旧版视觉 · 新链数据现场组装 · 五角色一页可达 · 纯静态 · 双击可开 · 手机可读</p>
</header>
<div class="filter" role="search">
<input id="q" type="search" placeholder="搜索：赛博 / cyborg / ranger…" autocomplete="off">
<select id="dlc" aria-label="DLC 筛选">
<option value="all">全部（含 DLC）</option>
<option value="base">仅本体</option>
<option value="abyssal">仅 Abyssal Terrors DLC</option>
</select>
<label class="chk"><input id="playable" type="checkbox"> 仅看可点</label>
</div>
<div class="count" id="count">共 {len(entries)} 个角色，当前可点 {len(entries)} 个，当前命中 {len(entries)} 个</div>
<div class="grid" id="grid">
{static_cards}</div>
<div class="foot"><p>构建产物，人不手改，只改源码重构建。共 {len(entries)} 单，全部现场组装；旧索引页不动（随旧链退役，沿 #51 时机）。</p><p>头像图标 © Blobfish，via <a href="https://brotato.wiki.spellsandguns.com/">Brotato Wiki</a>（文本 <a href="https://creativecommons.org/licenses/by-sa/4.0/">CC BY-SA 4.0</a>，游戏资产原权保留）<a href="https://brotato.wiki.spellsandguns.com/wiki/Characters">原页：Characters</a> · <a href="https://brotato.wiki.spellsandguns.com/wiki/Stats">原页：Stats</a> 热链 60px 缩略图，注册表集中管理；断网时显示 🥔 占位，仍可读；转述非搬运，不搬截图原片。</p></div>
</div>
<script>
// 索引全能力（沿旧版）：搜索+筛选+仅看可点，同源 ROSTER 内联渲染，file:// 可跑，无 fetch。
// 搜索 norm：小写去空格/连字符/下划线子串，覆盖中文/英文/slug 去分隔/英文首字母缩写/难度。
var ROSTER = {roster_json};
var q = document.getElementById("q"), dlc = document.getElementById("dlc"),
    playable = document.getElementById("playable"),
    grid = document.getElementById("grid"), count = document.getElementById("count");
function norm(s){{ return String(s).toLowerCase().replace(/[\\s\\-_]+/g,""); }}
function initials(en){{
  var parts = String(en).split(/[\\s\\-_]+/), a = "";
  for (var i=0;i<parts.length;i++){{ if(parts[i]) a += parts[i][0].toLowerCase(); }}
  return a;
}}
function hay(r){{
  var ab = r.abbr || initials(r.en);
  var nospace = String(r.slug).replace(/[-_]+/g,"");
  var covers = (r.covers || []).join(" ");
  return norm(String(r.zh)+" "+String(r.en)+" "+String(r.slug)+" "+nospace+" "+ab+" "+String(r.variant)+" "+covers);
}}
function esc(s){{ return String(s).replace(/&/g,"&amp;").replace(/</g,"&lt;").replace(/>/g,"&gt;").replace(/"/g,"&quot;"); }}
function card(r){{
  var dlcLabel = r.dlc ? "Abyssal Terrors DLC" : "本体";
  var coversTxt = (r.covers || []).join(" + ");
  var sub = r.slug+" · "+r.variant+" · "+coversTxt+" · 取证 "+r.published;
  var ava = r.img
    ? '<div class="ava"><span>🥔</span><img loading="lazy" alt="'+esc(r.en)+'" src="'+esc(r.img)+'" referrerpolicy="no-referrer" onerror="this.remove()"></div>'
    : '<div class="ava"><span>🥔</span></div>';
  var right = '<span class="tag ok">● 可点</span><div class="links"><a href="'+esc(r.guide)+'">看攻略</a></div>';
  return '<div class="card" data-slug="'+esc(r.slug)+'" data-variant="'+esc(r.variant)+'" data-dlc="'+(r.dlc ? "abyssal" : "")+'" data-playable="'+(r.playable ? "1" : "0")+'" data-sha="'+esc(r.sha)+'">'
    + ava
    + '<div class="nm">'+esc(r.zh)+" ("+esc(r.en)+")<small>"+esc(sub)+' · SHA <code title="'+esc(r.sha)+'">'+esc(String(r.sha).slice(0,8))+"</code></small>"
    + '<small>视频：<a href="'+esc(r.videoUrl)+'" target="_blank" rel="noopener">'+esc(r.videoTitle)+"</a></small></div>"
    + '<div class="right">'+right+"</div></div>";
}}
function render(){{
  var kw = norm(q.value.trim()), list = ROSTER.filter(function(r){{
    if (dlc.value === "base" && r.dlc) return false;
    if (dlc.value === "abyssal" && r.dlc !== "abyssal") return false;
    if (playable.checked && !r.playable) return false;
    if (kw && hay(r).indexOf(kw) < 0) return false;
    return true;
  }});
  var playableCount = ROSTER.filter(function(r){{ return r.playable; }}).length;
  count.textContent = "共 " + ROSTER.length + " 个角色，当前可点 " + playableCount + " 个，当前命中 " + list.length + " 个";
  if (!list.length) {{ grid.innerHTML = '<div class="empty">没有命中，换个关键词或把筛选放宽（如选“全部”）。</div>'; return; }}
  grid.innerHTML = list.map(card).join("");
}}
q.addEventListener("input", render); dlc.addEventListener("change", render); playable.addEventListener("change", render);
render();
</script>
<!-- GENERATED by scripts/build_new_index.py: do not edit, rebuild from G work guide.json + data/roster.json + data/wiki-cache.json -->
</body>
</html>
"""
    out_path.parent.mkdir(parents=True, exist_ok=True)
    out_path.write_text(page, encoding="utf-8")
    print(f"SUCCESS: new index: {out_path.resolve()} (cards: {len(entries)})")
    return out_path


def main() -> None:
    parser = argparse.ArgumentParser(description="新链索引页生成器 (Issue #73): 五角色 guide 一页可达 (旧版视觉 + 新链数据)")
    parser.add_argument("--work-root", default="G:/brotato-work", help="G 盘工作区根目录")
    parser.add_argument("--out", default="docs/new_index.html", help="输出 HTML 路径")
    args = parser.parse_args()

    repo = _repo_root()
    work_root = Path(args.work_root)
    if not work_root.is_absolute():
        work_root = (repo / args.work_root).resolve()
    out_path = Path(args.out)
    if not out_path.is_absolute():
        out_path = (repo / args.out).resolve()
    if not work_root.is_dir():
        fail(f"缺件即 fail: work-root 不存在: {work_root}")
    build(work_root, out_path, repo)


if __name__ == "__main__":
    main()
