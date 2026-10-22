#!/usr/bin/env python3
"""新链索引页生成器 (Issue #73): 五角色 guide 一页可达.

Deterministic-first + No silent fallback:
- 输入 (只认这三件, 不手写):
  `<work-root>/<slug>/<variant>/outputs/guide.json` (slug/variant/covers/sha/url/title)
  `<work-root>/<slug>/<variant>/inputs/meta.json` (published 取证日期)
  `<work-root>/<slug>/<variant>/inputs/manifest.json` (sha 对拍: guide.sha 须命中 sources[].sha1)
  另要求 `<work-root>/<slug>/<variant>/outputs/guide.html` 存在 (所链目标, 缺即死链 -> fail loud).
- 输出: 单文件 HTML (默认 `docs/new_index.html`; 旧索引页碰都不碰, 随旧链退役沿 #51 时机).
- 缺任一单任一件即 fail loud (exit 1, `FAIL:` 指明缺件, 不写半成品, 不静默缺卡).
- 全部字段现场读出组装; 同输入同代码必同字节 (幂等, 页内无 wall-clock).
- 链接: out 与目标同盘则相对 href (产物 bundle 可点), 跨盘 (D: repo -> G: work)
  则回退 `file://` 绝对 URI (由 --work-root 派生, 代码内无硬编码盘符).
- 测试读 G 盘 (`--work-root G:/brotato-work`), 正式随产物发布 (沿 standing).

固定五单 (增减须改码 + 改测, 发现式扫描一律不做):
  cyborg/ultimate, doctor/nightmare, engineer/ultimate, one-armed/ultimate, ranger/ultimate.

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
from typing import NoReturn

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


def _load_json(path: Path, what: str) -> object:
    if not path.is_file():
        fail(f"缺件即 fail: {what} 不存在: {path}")
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except json.JSONDecodeError as e:
        fail(f"格式错即 fail: {what} 非法 JSON: {path} ({e})")
    raise AssertionError("unreachable")  # fail() raises


def _href_for(out_path: Path, target: Path) -> str:
    """out 同盘 -> 相对 href; 跨盘 (D:->G:) -> file:// 绝对 URI."""
    out_abs = out_path.resolve()
    tgt_abs = target.resolve()
    try:
        rel = os.path.relpath(str(tgt_abs), str(out_abs.parent))
        return rel.replace(os.sep, "/")
    except ValueError:
        return tgt_abs.as_uri()


def _card(
    slug: str,
    variant: str,
    covers: list[str],
    sha: str,
    published: str,
    title: str,
    url: str,
    guide_href: str,
    guide_rel: str,
) -> str:
    covers_txt = " + ".join(covers)
    return (
        f'<article class="card" data-slug="{html.escape(slug, quote=True)}" '
        f'data-variant="{html.escape(variant, quote=True)}">\n'
        f'  <h2>{html.escape(slug)} <small>{html.escape(variant)}</small></h2>\n'
        f'  <p>难度：<span class="badge">{html.escape(covers_txt)}</span></p>\n'
        f"  <p>SHA：<code>{html.escape(sha)}</code></p>\n"
        f"  <p>取证日期：<code>{html.escape(published)}</code></p>\n"
        f'  <p>视频：<a href="{html.escape(url, quote=True)}" target="_blank" '
        f'rel="noopener">{html.escape(title)}</a></p>\n'
        f'  <p><a class="go" href="{html.escape(guide_href, quote=True)}">看攻略 →</a></p>\n'
        f'  <p class="src">产物：{html.escape(guide_rel)}</p>\n'
        "</article>\n"
    )


def build(work_root: Path, out_path: Path) -> Path:
    """组装五卡索引; 任一缺件/错键即 fail loud, 成功才写盘 (不写半成品)."""
    cards: list[str] = []
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
        assert isinstance(guide, dict)
        if guide.get("slug") != slug or guide.get("variant") != variant:
            fail(
                f"错位即 fail: {slug}/{variant} guide.json slug/variant 为 "
                f"{guide.get('slug')!r}/{guide.get('variant')!r}"
            )
        covers = guide.get("covers")
        if not isinstance(covers, list) or not covers or not all(isinstance(c, str) and c for c in covers):
            fail(f"格式错即 fail: {slug}/{variant} guide.json covers 须为非空字符串数组")
        assert isinstance(covers, list)
        sha = guide.get("sha")
        if not isinstance(sha, str) or not _SHA_RE.match(sha):
            fail(f"格式错即 fail: {slug}/{variant} guide.json sha 须为 40 位 hex")
        assert isinstance(sha, str)
        url = guide.get("url")
        title = guide.get("title")
        if not isinstance(url, str) or not url.startswith("https://"):
            fail(f"格式错即 fail: {slug}/{variant} guide.json url 须为 https 链接")
        if not isinstance(title, str) or not title.strip():
            fail(f"格式错即 fail: {slug}/{variant} guide.json title 缺失")
        assert isinstance(url, str) and isinstance(title, str)

        if not isinstance(meta, dict) or not isinstance(meta.get("published"), str):
            fail(f"格式错即 fail: {slug}/{variant} meta.json published 缺失")
        assert isinstance(meta, dict)
        published = str(meta.get("published"))
        if not _DATE_RE.match(published):
            fail(f"格式错即 fail: {slug}/{variant} meta.json published 须为 YYYY-MM-DD, got {published!r}")

        if not isinstance(manifest, dict):
            fail(f"格式错即 fail: {slug}/{variant} manifest.json 须为对象")
        assert isinstance(manifest, dict)
        sources = manifest.get("sources")
        src_list: list[object] = sources if isinstance(sources, list) else []
        if sha not in {s.get("sha1") for s in src_list if isinstance(s, dict)}:
            fail(f"对不上即 fail: {slug}/{variant} guide.sha {sha[:8]} 未命中 manifest sources[].sha1")

        guide_href = _href_for(out_path, guide_html_path)
        try:
            guide_rel = (guide_html_path.resolve().relative_to(work_root.resolve())).as_posix()
        except ValueError:
            guide_rel = f"{slug}/{variant}/outputs/guide.html"
        cards.append(_card(slug, variant, list(covers), sha, published, title, url, guide_href, guide_rel))

    page = f"""<!DOCTYPE html>
<html lang="zh-CN">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1, viewport-fit=cover">
<title>新链攻略索引 · 五角色一页可达</title>
<style>
:root {{ --bg:#f7f5ef; --card:#fff; --ink:#1f1b16; --muted:#7a7166; --line:#e7e0d2; --acc:#0b5fff; }}
* {{ box-sizing:border-box; }}
body {{ margin:0; background:var(--bg); color:var(--ink); font:16px/1.65 -apple-system,"PingFang SC","Microsoft YaHei",sans-serif; }}
.wrap {{ max-width:720px; margin:0 auto; padding:16px 14px 80px; }}
header h1 {{ font-size:22px; margin:14px 0 4px; }}
header p {{ color:var(--muted); margin:0 0 12px; font-size:14px; }}
.count {{ font-size:13px; color:var(--muted); margin:8px 2px; }}
.grid {{ display:grid; gap:10px; }}
.card {{ background:var(--card); border:1px solid var(--line); border-radius:12px; padding:12px 14px; }}
.card h2 {{ margin:0 0 6px; font-size:18px; }}
.card h2 small {{ font-weight:400; color:var(--muted); font-size:13px; }}
.card p {{ margin:4px 0; font-size:14px; }}
.badge {{ display:inline-block; font-size:12px; border:1px solid var(--line); border-radius:999px; padding:2px 8px; }}
code {{ font-family:monospace; font-size:13px; background:#f2eee4; padding:1px 6px; border-radius:6px; }}
a {{ color:var(--acc); }}
.go {{ display:inline-block; background:#1f1b16; color:#fff !important; border-radius:999px; padding:6px 14px; text-decoration:none; font-weight:700; }}
.src {{ color:var(--muted); font-size:12px; }}
.foot {{ margin-top:16px; font-size:13px; color:var(--muted); }}
</style>
</head>
<body>
<div class="wrap">
<header>
<h1>新链攻略索引 · 五角色一页可达</h1>
<p>确定性组装：五卡字段全从各 outputs/guide.json + inputs/meta.json 现场读出，不手写；缺一单即整页 fail。</p>
</header>
<div class="count">共 {len(cards)} 单，全部可点</div>
<div class="grid">
{"".join(cards)}</div>
<div class="foot"><p>构建产物，人不手改，只改源码重构建。旧索引页不动（随旧链退役，沿 #51 时机）。</p></div>
</div>
<!-- GENERATED by scripts/build_new_index.py: do not edit, rebuild from G work guide.json -->
</body>
</html>
"""
    out_path.parent.mkdir(parents=True, exist_ok=True)
    out_path.write_text(page, encoding="utf-8")
    print(f"SUCCESS: new index: {out_path.resolve()} (cards: {len(cards)})")
    return out_path


def main() -> None:
    parser = argparse.ArgumentParser(description="新链索引页生成器 (Issue #73): 五角色 guide 一页可达")
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
    build(work_root, out_path)


if __name__ == "__main__":
    main()
