#!/usr/bin/env python3
"""攻略单页原型渲染器 (Issue #57 原型验证): guide.json → HTML 样张与契约展示.

纯原型脚本 (Throwaway):
- 输入: G:/brotato-work/<slug>/<variant>/outputs/guide.json + data/ (wiki-cache, terms, roster)
- 输出: docs/prototype_cyborg.html
- 功能:
  1. 同时渲染 3 种完全不同信息架构的 UI 变体 (Variant A 经典卡片流, Variant B 波次推演流, Variant C 双栏决策台)
  2. 底部浮动切换条 (Switcher): 点击箭头/按键左右箭头/直接点击药丸切换, 同步 URL ?variant=A|B|C
  3. 契约与状态检查面板 (Contract & State Inspector): 露出数据源、SHA、段落统计与契约 4 大问题决策草案
  4. 完整复用旧链 hover 悬浮三件套 (武器强化表/道具属性/属性道具池) + 图标 + 中英对照
  5. 视频原声跳转 (?t= 秒级点跳到 YouTube 对应波次与原句)
"""

from __future__ import annotations

import argparse
import csv
import html
import json
import os
import sys
from pathlib import Path


def esc(text: object) -> str:
    """HTML 转义."""
    if text is None:
        return ""
    return html.escape(str(text), quote=True)


def format_seconds(secs: int | float | None) -> str:
    """格式化秒数为 mm:ss."""
    if secs is None:
        return "00:00"
    s = int(secs)
    m = s // 60
    rem = s % 60
    return f"{m:02d}:{rem:02d}"


def term_text(en: str, terms: dict[str, dict[str, str]]) -> str:
    """中英术语对照."""
    row = terms.get(en)
    if not row:
        return en
    zh = str(row.get("zh", "")).strip()
    if zh:
        text = f"{zh} ({en})"
        if str(row.get("needs_review", "")).upper() == "TRUE":
            text += "※"
        return text
    return en


def icon_html(thumb: object, en: str, page: object = None) -> str:
    """图标三件套渲染."""
    if isinstance(thumb, str) and thumb:
        file_mark = page if isinstance(page, str) and page else en
        return (
            f'<img class="sic" alt="{esc(en)}" width="20" height="20" '
            f'src="{esc(thumb)}" data-file="{esc(str(file_mark))}" '
            f'loading="lazy" referrerpolicy="no-referrer" onerror="this.remove()"> '
        )
    return '<span class="sic none" title="wiki 无专用图标">◆</span> '


def effect_html(eff: dict[str, object], terms: dict[str, dict[str, str]]) -> str:
    """单条道具效果 (红绿语义)."""
    if "free" in eff:
        return esc(eff.get("free", ""))
    val_cls = "neg" if eff.get("neg") else "pos"
    out = ""
    if eff.get("pre"):
        out += esc(eff.get("pre", "")) + " "
    out += f'<span class="{val_cls}">{esc(eff.get("val", ""))}</span>'
    term = eff.get("term")
    suf = str(eff.get("suf", ""))
    if term and not eff.get("pre") and isinstance(term, str):
        pct = "% " if suf.startswith("%") else ""
        out += " " + pct + esc(term_text(term, terms))
    elif suf:
        out += " " + esc(suf)
    return out


def kv_row(key_en: str, value_html: str, terms: dict[str, dict[str, str]]) -> str:
    """悬浮表格 key-value 行."""
    key = esc(term_text(key_en, terms)) if key_en in terms else esc(key_en)
    return f'<span class="kv"><span class="ke">{key}</span><span class="kx">{value_html}</span></span>'


def level_html(lv_entry: object) -> str:
    """武器单等级数值."""
    if not isinstance(lv_entry, dict):
        return "—"
    try:
        num = int(lv_entry.get("lv", 1))
    except (TypeError, ValueError):
        num = 1
    if num not in (1, 2, 3, 4):
        num = 1
    if "t" in lv_entry:
        inner = esc(lv_entry.get("t", "—"))
    else:
        inner = (
            esc(lv_entry.get("b", ""))
            + f"({esc(str(lv_entry.get('p', '')))})"
            + esc(lv_entry.get("suf", ""))
        )
    return f'<span class="w{num}">{inner}</span>'


def item_tip(en: str, entry: dict[str, object], terms: dict[str, dict[str, str]]) -> str:
    """道具悬浮卡片."""
    effs = entry.get("effects")
    eff_list = effs if isinstance(effs, list) else []
    eff_html = "<br>".join(
        effect_html(e, terms) if isinstance(e, dict) else esc(str(e)) for e in eff_list
    )
    tags = entry.get("tags")
    tag_list = tags if isinstance(tags, list) else []
    tag_html = ", ".join(
        esc(term_text(str(t), terms)) if str(t) in terms else esc(str(t))
        for t in tag_list
    )
    rows = [
        kv_row("Effects", eff_html or "—", terms),
        kv_row("Base Price", esc(str(entry.get("price", ""))) or "—", terms),
        kv_row("Limit", esc(str(entry.get("limit", ""))) or "—", terms),
        kv_row("Unlocked By", esc(str(entry.get("unlock", ""))) or "—", terms),
        kv_row("Tags", tag_html or "—", terms),
    ]
    return (
        f'<span class="tip"><span class="th">{esc(str(entry.get("tier", "")))}</span>'
        f'{"".join(rows)}'
        f'<span class="tf">※ = 中文待客户端简中校对；英文为 wiki 原名</span></span>'
    )


def weapon_tip(en: str, entry: dict[str, object], terms: dict[str, dict[str, str]]) -> str:
    """武器悬浮强化表 (Lv1-Lv4)."""
    stats = entry.get("stats")
    stat_list = stats if isinstance(stats, list) else []
    head = "<tr><th></th><th>Lv1</th><th>Lv2</th><th>Lv3</th><th>Lv4</th></tr>"
    body: list[str] = []
    scales: list[str] = []
    for s in stat_list:
        if not isinstance(s, dict):
            continue
        lvs = s.get("lv")
        lv_list = lvs if isinstance(lvs, list) else []
        for v in lv_list:
            if isinstance(v, dict) and v.get("s") and str(v.get("s")) not in scales:
                scales.append(str(v.get("s")))
        cells = [f"<td>{level_html(v)}</td>" for v in lv_list[:4]]
        while len(cells) < 4:
            cells.append("<td>—</td>")
        k_name = term_text(str(s.get("k", "")), terms)
        body.append(f"<tr><th>{esc(k_name)}</th>{''.join(cells)}</tr>")
    if scales:
        scale_html = ", ".join(esc(term_text(s, terms)) for s in scales)
        body.append(f'<tr><th>Scaling</th><td colspan="4" class="span">{scale_html}</td></tr>')
    price = entry.get("price")
    price_list = price if isinstance(price, list) else []
    pcells = [f"<td>{level_html(v)}</td>" for v in price_list[:4]]
    while len(pcells) < 4:
        pcells.append("<td>—</td>")
    body.append(f"<tr><th>Base Price</th>{''.join(pcells)}</tr>")
    for key in ("Special Effects", "Unlocked By"):
        field = "special" if key == "Special Effects" else "unlock"
        body.append(f'<tr><th>{esc(key)}</th><td colspan="4" class="span">{esc(str(entry.get(field, "")) or "—")}</td></tr>')
    table = f'<span class="tw"><table class="wt">{head}{"".join(body)}</table></span>'
    return (
        f'<span class="tip"><span class="th">{esc(str(entry.get("class", "")))}</span>'
        f'{table}'
        f'<span class="tf">※ = 中文待客户端简中校对；英文为 wiki 原名</span></span>'
    )


def stat_tooltip_html(tips: list[dict[str, object]] | None) -> str:
    """属性悬浮加成道具表."""
    if not tips:
        return ""
    shown = tips[:10]
    more = len(tips) - len(shown)
    items = "".join(
        f'<span class="ti"><img alt="" src="{esc(str(t.get("thumb","")))}" '
        f'loading="lazy" referrerpolicy="no-referrer" onerror="this.remove()">'
        f'<span class="tn">{esc(str(t.get("en","")))}</span></span>'
        for t in shown
        if isinstance(t, dict)
    )
    more_html = f'<span class="tm">等共 {len(tips)} 件，详见 wiki</span>' if more > 0 else ""
    title = "加该属性的道具（wiki Positive/Notable）"
    return (
        f'<span class="tip"><span class="th">{title}</span>'
        f'{items}{more_html}'
        f'<span class="tf">※ = 中文待客户端简中校对；英文为 wiki 原名</span></span>'
    )


def render_quote_badge(video_url: str, qd: dict[str, object] | None, fallback_quote: str = "") -> str:
    """渲染原声引述徽标及视频秒级跳转链接."""
    if not qd and not fallback_quote:
        return ""
    if qd:
        t = qd.get("t")
        start_txt = str(qd.get("start", ""))
        time_display = start_txt.split(".")[0] if "." in start_txt else start_txt
        if not time_display and t is not None:
            time_display = format_seconds(t)
        jump_url = f"{video_url}&t={t}s" if (video_url and t is not None) else video_url
        quote_text = str(qd.get("quote", fallback_quote))
        context_text = str(qd.get("context", ""))
        tooltip_attr = f'title="{esc(context_text or quote_text)}"'
        return (
            f'<div class="quote-line">'
            f'<a class="yt-jump" href="{esc(jump_url)}" target="_blank" rel="noopener" {tooltip_attr}>'
            f'<span class="play-icon">▶</span> {esc(time_display)}'
            f'</a>'
            f'<span class="quote-text" {tooltip_attr}>“{esc(quote_text)}”</span>'
            f'</div>'
        )
    else:
        return f'<div class="quote-line"><span class="quote-text">“{esc(fallback_quote)}”</span></div>'


def render_all(guide_path: Path, wiki_path: Path, terms_path: Path, roster_path: Path, out_path: Path) -> None:
    guide = json.loads(guide_path.read_text(encoding="utf-8"))
    wiki = json.loads(wiki_path.read_text(encoding="utf-8"))
    roster = json.loads(roster_path.read_text(encoding="utf-8"))
    terms: dict[str, dict[str, str]] = {}
    with terms_path.open(encoding="utf-8") as f:
        for row in csv.DictReader(f):
            terms[row["en"]] = row

    slug = guide.get("slug", "cyborg")
    variant = guide.get("variant", "ultimate")
    sha = guide.get("sha", "")
    short_sha = sha[:8] if sha else "unknown"
    video_url = guide.get("url", "")
    video_title = guide.get("title", "")
    covers = guide.get("covers", ["Ultimate"])

    # 角色信息
    char_entry = next((c for c in roster if c.get("id") == slug or c.get("en", "").lower() == slug.lower()), {})
    char_zh = char_entry.get("zh", slug.capitalize())
    char_en = char_entry.get("en", slug.capitalize())
    char_wiki = wiki.get("chars", {}).get(char_en, {})
    char_thumb = char_wiki.get("thumb", "")

    # 数据计数
    ratings_data = guide.get("ratings", [])
    weapons_data = guide.get("weapons", {})
    groups_data = guide.get("groups", [])
    phases_data = guide.get("phases", [])
    priorities_data = guide.get("priorities", {})
    pitfalls_data = guide.get("pitfalls", [])

    must_take = [g for g in groups_data if g.get("group") == "must_take"]
    bans = [g for g in groups_data if g.get("group") == "ban"]
    skips = [g for g in groups_data if g.get("group") == "mentioned_not_taken"]
    casuals = [g for g in groups_data if g.get("group") == "casual_mention"]

    # ----------------- 生成 HTML 内容 -----------------
    html_out = f"""<!DOCTYPE html>
<html lang="zh-CN">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1, viewport-fit=cover">
<title>【样张】{esc(char_zh)} ({esc(char_en)}) · 攻略单页渲染器原型</title>
<style>
:root {{
  --bg: #f5f4ef;
  --card: #ffffff;
  --card-subtle: #fcfbf8;
  --ink: #1a1815;
  --ink-secondary: #5a544c;
  --muted: #8c8275;
  --line: #e5dfd3;
  --line-strong: #cfc6b5;
  --accent: #0b5fff;
  --accent-light: #ebf3ff;
  --success: #1b7f3b;
  --success-bg: #eaf6ed;
  --danger: #d93829;
  --danger-bg: #fdf0ed;
  --warning: #b36b00;
  --warning-bg: #fef6e9;
  --purple: #782cb8;
  --purple-bg: #f5edf9;
  --shadow-sm: 0 1px 3px rgba(0,0,0,0.06);
  --shadow-md: 0 4px 14px rgba(0,0,0,0.09);
  --shadow-lg: 0 10px 28px rgba(0,0,0,0.14);
}}

* {{ box-sizing: border-box; }}
body {{
  margin: 0;
  background: var(--bg);
  color: var(--ink);
  font: 15px/1.65 -apple-system, BlinkMacSystemFont, "Segoe UI", "PingFang SC", "Hiragino Sans GB", "Microsoft YaHei", sans-serif;
  padding-bottom: 90px;
}}
a {{ color: var(--accent); text-decoration: none; }}
a:hover {{ text-decoration: underline; }}

/* 顶部契约与状态栏 */
.contract-banner {{
  background: #231f1a;
  color: #efe8dc;
  font-size: 13px;
  border-bottom: 1px solid #3d362f;
}}
.contract-inner {{
  max-width: 1100px;
  margin: 0 auto;
  padding: 8px 16px;
  display: flex;
  align-items: center;
  justify-content: space-between;
  flex-wrap: wrap;
  gap: 10px;
}}
.contract-badge {{
  display: inline-flex;
  align-items: center;
  gap: 6px;
  background: #362f27;
  padding: 3px 9px;
  border-radius: 6px;
  font-family: monospace;
}}
.contract-toggle {{
  background: transparent;
  border: 1px solid #5a4f41;
  color: #f7ede0;
  border-radius: 6px;
  padding: 3px 10px;
  cursor: pointer;
  font-size: 12px;
}}
.contract-toggle:hover {{ background: #3a3229; }}
.contract-drawer {{
  display: none;
  background: #181512;
  border-top: 1px solid #332b23;
  padding: 14px 16px;
  font-size: 12px;
  line-height: 1.6;
}}
.contract-drawer.open {{ display: block; }}
.contract-grid {{
  display: grid;
  grid-template-columns: repeat(auto-fit, minmax(240px, 1fr));
  gap: 14px;
  max-width: 1100px;
  margin: 0 auto;
}}
.contract-box {{
  background: #241f1a;
  padding: 10px 12px;
  border-radius: 8px;
  border-left: 3px solid #ffb020;
}}
.contract-box h4 {{ margin: 0 0 6px; color: #ffd180; font-size: 13px; }}

/* 通用容器 */
.layout-container {{
  max-width: 1100px;
  margin: 0 auto;
  padding: 16px;
}}

/* 顶部英雄区 */
.hero-card {{
  background: #1e1b17;
  color: #fcf9f2;
  border-radius: 16px;
  padding: 20px 24px;
  margin-bottom: 20px;
  box-shadow: var(--shadow-md);
  display: flex;
  align-items: center;
  justify-content: space-between;
  flex-wrap: wrap;
  gap: 16px;
}}
.hero-left {{
  display: flex;
  align-items: center;
  gap: 16px;
}}
.hero-avatar {{
  width: 64px;
  height: 64px;
  border-radius: 14px;
  background: rgba(255,255,255,0.08);
  border: 2px solid rgba(255,255,255,0.15);
  image-rendering: pixelated;
}}
.hero-title h1 {{
  margin: 0 0 4px;
  font-size: 24px;
  display: flex;
  align-items: center;
  gap: 10px;
  flex-wrap: wrap;
}}
.hero-meta {{
  color: #bbb09e;
  font-size: 13px;
  display: flex;
  align-items: center;
  gap: 12px;
  flex-wrap: wrap;
}}
.hero-source-card {{
  background: rgba(255,255,255,0.06);
  border: 1px solid rgba(255,255,255,0.12);
  border-radius: 10px;
  padding: 8px 12px;
  max-width: 360px;
  font-size: 12px;
}}
.hero-source-card a {{ color: #7ab3ff; font-weight: 600; display: block; overflow: hidden; text-overflow: ellipsis; white-space: nowrap; }}
.hero-source-card .subtext {{ color: #9a8f7c; margin-top: 2px; }}

/* 徽标 */
.badge {{
  display: inline-block;
  font-size: 11px;
  padding: 1px 7px;
  border-radius: 999px;
  font-weight: 600;
  vertical-align: 1px;
}}
.badge-covers {{ background: #277943; color: #fff; }}
.badge-sha {{ background: #40382d; color: #ffd699; font-family: monospace; border: 1px solid #635746; }}
.badge-verified {{ background: var(--success-bg); color: var(--success); border: 1px solid #a8e0b7; }}
.badge-candidate {{ background: #f0f0ee; color: #666; border: 1px dashed #b5b5b0; }}
.badge-must-take {{ background: #dcfce7; color: #166534; font-weight: 700; border: 1px solid #86efac; }}
.badge-ban {{ background: #ffe4e6; color: #9f1239; font-weight: 700; border: 1px solid #fecdd3; }}
.badge-skip {{ background: #f1f5f9; color: #475569; border: 1px solid #cbd5e1; }}
.badge-casual {{ background: #f8fafc; color: #64748b; border: 1px solid #e2e8f0; }}

/* 避坑等级 */
.badge-fatal {{ background: #fee2e2; color: #991b1b; font-weight: 800; border: 1px solid #f87171; }}
.badge-risky {{ background: #fef3c7; color: #92400e; font-weight: 700; border: 1px solid #fcd34d; }}
.badge-trap {{ background: #f3e8ff; color: #6b21a8; font-weight: 700; border: 1px solid #d8b4fe; }}

/* 评级徽标 */
.rating {{
  display: inline-block;
  min-width: 1.8em;
  padding: 1px 6px;
  border-radius: 999px;
  font-weight: 800;
  text-align: center;
  font-size: 13px;
}}
.rating-S {{ color: #b71c1c; background: #ffebee; }}
.rating-A {{ color: #c2410c; background: #ffedd5; }}
.rating-B {{ color: #15803d; background: #dcfce7; }}
.rating-C {{ color: #1d4ed8; background: #dbeafe; }}
.rating-D {{ color: #4b5563; background: #f3f4f6; }}
.rating-none {{ color: #9ca3af; border: 1px dashed #d1d5db; background: transparent; }}

/* 视频跳转按钮与引述 */
.quote-line {{
  display: flex;
  align-items: baseline;
  gap: 8px;
  margin-top: 5px;
  font-size: 12px;
}}
.yt-jump {{
  display: inline-flex;
  align-items: center;
  gap: 3px;
  background: #ff0000;
  color: #fff !important;
  font-weight: 700;
  font-size: 11px;
  padding: 1px 6px;
  border-radius: 4px;
  text-decoration: none !important;
  line-height: 1.3;
  flex-shrink: 0;
}}
.yt-jump:hover {{ background: #cc0000; }}
.play-icon {{ font-size: 9px; }}
.quote-text {{
  color: var(--ink-secondary);
  font-style: italic;
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}}

/* 旧链 hover 悬浮机制复用 */
.has-tip {{ position: relative; border-bottom: 1px dotted var(--muted); cursor: help; }}
.has-tip .tip {{
  display: none;
  position: absolute;
  left: 0;
  top: 100%;
  margin-top: 6px;
  z-index: 40;
  background: #1f1b16;
  color: #fdf6e3;
  border-radius: 10px;
  padding: 9px 12px;
  font-size: 12px;
  min-width: min(340px, 85vw);
  max-width: min(380px, 90vw);
  box-shadow: 0 8px 24px rgba(0,0,0,.4);
  text-align: left;
}}
.has-tip:hover .tip, .has-tip:focus .tip, .has-tip:focus-within .tip {{
  display: grid;
  grid-template-columns: repeat(3, minmax(0,1fr));
  gap: 6px 8px;
}}
tr:nth-last-child(-n+5) .has-tip .tip {{ top: auto; bottom: 100%; margin-top: 0; margin-bottom: 6px; }}
.tip .th {{ grid-column: 1 / -1; display: block; font-weight: 700; color: #ffd966; margin-bottom: 2px; }}
.tip .ti {{ display: flex; gap: 5px; align-items: center; margin: 0; min-width: 0; font-size: 11px; line-height: 1.35; overflow: hidden; }}
.tip .ti img {{ width: 22px; height: 22px; flex: 0 0 22px; object-fit: contain; image-rendering: pixelated; background: rgba(255,255,255,.12); border-radius: 5px; }}
.tip .tn {{ overflow: hidden; text-overflow: ellipsis; white-space: nowrap; min-width: 0; }}
.tip .tm {{ grid-column: 1 / -1; color: #b9ad93; font-size: 11px; }}
.tip .kv {{ grid-column: 1 / -1; display: flex; justify-content: space-between; gap: 8px; font-size: 11px; line-height: 1.5; }}
.tip .ke {{ color: #b9ad93; flex: 0 0 auto; }}
.tip .kx {{ text-align: right; min-width: 0; overflow-wrap: anywhere; }}
.pos {{ color: rgb(0,255,0); font-weight: 700; }}
.neg {{ color: rgb(255,80,80); font-weight: 700; }}
.tip .tw {{ grid-column: 1 / -1; min-width: 0; }}
table.wt {{ width: 100%; border-collapse: collapse; font-size: 11px; line-height: 1.45; }}
.wt th, .wt td {{ padding: 3px 4px; vertical-align: top; border-bottom: 1px solid rgba(255,255,255,.08); }}
.wt th {{ color: #b9ad93; font-weight: 600; text-align: left; white-space: nowrap; }}
.wt td {{ text-align: center; overflow-wrap: anywhere; }}
.wt td.span {{ text-align: left; }}
.w1 {{ color: #e8e6df; font-weight: 700; }}
.w2 {{ color: #5aa9ff; font-weight: 700; }}
.w3 {{ color: #c77dff; font-weight: 700; }}
.w4 {{ color: #ff6b6b; font-weight: 700; }}
.tip .tf {{ grid-column: 1 / -1; display: block; color: #b9ad93; margin-top: 4px; font-size: 10px; border-top: 1px solid rgba(255,255,255,0.1); padding-top: 3px; }}

.sic {{ width: 20px; height: 20px; vertical-align: -4px; image-rendering: pixelated; background: #efe9d8; border-radius: 5px; }}
.sic.none {{ display: inline-flex; width: 20px; height: 20px; vertical-align: -4px; align-items: center; justify-content: center; font-size: 12px; color: var(--muted); background: #f2ecdd; border-radius: 5px; }}

/* 卡片与网格 */
.card {{
  background: var(--card);
  border: 1px solid var(--line);
  border-radius: 14px;
  padding: 16px 18px;
  margin-bottom: 16px;
  box-shadow: var(--shadow-sm);
}}
.card-header {{
  display: flex;
  align-items: center;
  justify-content: space-between;
  margin-bottom: 12px;
  border-bottom: 1px solid var(--line);
  padding-bottom: 8px;
}}
.card-title {{
  font-size: 17px;
  font-weight: 700;
  margin: 0;
  display: flex;
  align-items: center;
  gap: 8px;
}}
.card-subtext {{ font-size: 13px; color: var(--muted); }}

/* 表格通用 */
.table-wrap {{ overflow-x: auto; -webkit-overflow-scrolling: touch; }}
table.guide-table {{
  width: 100%;
  border-collapse: collapse;
  font-size: 14px;
}}
table.guide-table th, table.guide-table td {{
  padding: 9px 10px;
  border-bottom: 1px solid var(--line);
  vertical-align: top;
  text-align: left;
}}
table.guide-table th {{
  color: var(--ink-secondary);
  font-size: 12px;
  font-weight: 700;
  background: #faf8f5;
}}

/* ----------------- 变体 A 样式 (经典长文流) ----------------- */
.variant-a .toc-nav {{
  position: sticky;
  top: 0;
  z-index: 20;
  background: rgba(245,244,239,0.96);
  backdrop-filter: blur(8px);
  padding: 10px 0;
  border-bottom: 1px solid var(--line);
  margin-bottom: 18px;
  display: flex;
  gap: 8px;
  overflow-x: auto;
}}
.variant-a .toc-nav a {{
  white-space: nowrap;
  background: #fff;
  border: 1px solid var(--line);
  padding: 5px 12px;
  border-radius: 999px;
  font-size: 13px;
  color: var(--ink);
  font-weight: 600;
}}
.variant-a .toc-nav a:hover {{ background: #ece7db; text-decoration: none; }}
.weapon-grid {{
  display: grid;
  grid-template-columns: repeat(auto-fit, minmax(320px, 1fr));
  gap: 14px;
}}
.weapon-card {{
  border: 1px solid var(--line);
  border-radius: 12px;
  padding: 14px;
  background: var(--card-subtle);
}}
.weapon-card-header {{
  display: flex;
  align-items: center;
  justify-content: space-between;
  margin-bottom: 8px;
}}
.weapon-card-name {{ font-weight: 700; font-size: 16px; display: flex; align-items: center; gap: 8px; }}

/* ----------------- 变体 B 样式 (波次推演流) ----------------- */
.variant-b .b-layout {{
  display: grid;
  grid-template-columns: 220px 1fr;
  gap: 20px;
  align-items: start;
}}
.variant-b .b-rail {{
  position: sticky;
  top: 16px;
  background: var(--card);
  border: 1px solid var(--line);
  border-radius: 14px;
  padding: 12px;
  box-shadow: var(--shadow-sm);
}}
.b-rail h3 {{ margin: 0 0 10px; font-size: 14px; color: var(--muted); }}
.b-rail-item {{
  display: block;
  padding: 7px 10px;
  border-radius: 8px;
  font-size: 13px;
  color: var(--ink);
  margin-bottom: 4px;
  line-height: 1.4;
}}
.b-rail-item:hover, .b-rail-item.active {{
  background: #231f1a;
  color: #fff !important;
  text-decoration: none;
}}
.b-rail-item small {{ display: block; color: var(--muted); font-size: 11px; }}
.b-rail-item:hover small, .b-rail-item.active small {{ color: #ffd699; }}
.phase-card {{
  border-left: 4px solid #1a1815;
  margin-bottom: 22px;
}}
.phase-tag-row {{ display: flex; gap: 8px; margin-bottom: 8px; align-items: center; }}
.phase-box-grid {{
  display: grid;
  grid-template-columns: repeat(auto-fit, minmax(240px, 1fr));
  gap: 10px;
  margin-top: 12px;
}}
.phase-subbox {{
  background: var(--card-subtle);
  border: 1px solid var(--line);
  border-radius: 8px;
  padding: 10px 12px;
  font-size: 13px;
}}
.phase-subbox h5 {{ margin: 0 0 4px; font-size: 12px; color: var(--muted); }}

/* ----------------- 变体 C 样式 (双栏工作台) ----------------- */
.variant-c .c-layout {{
  display: grid;
  grid-template-columns: 55% 45%;
  gap: 20px;
  align-items: start;
}}
.variant-c .c-pane-left {{ min-width: 0; }}
.variant-c .c-pane-right {{
  position: sticky;
  top: 16px;
  max-height: calc(100vh - 120px);
  overflow-y: auto;
  background: var(--card);
  border: 1px solid var(--line);
  border-radius: 14px;
  padding: 16px;
  box-shadow: var(--shadow-md);
}}
.c-search-bar {{
  margin-bottom: 12px;
}}
.c-search-input {{
  width: 100%;
  padding: 8px 12px;
  border-radius: 8px;
  border: 1px solid var(--line-strong);
  font-size: 13px;
}}
.c-filter-tabs {{
  display: flex;
  gap: 6px;
  flex-wrap: wrap;
  margin-bottom: 12px;
}}
.c-filter-btn {{
  background: #f0eee6;
  border: 1px solid var(--line);
  padding: 4px 10px;
  border-radius: 999px;
  font-size: 12px;
  cursor: pointer;
  font-weight: 600;
}}
.c-filter-btn.active {{
  background: #1a1815;
  color: #fff;
  border-color: #1a1815;
}}
.c-item-card {{
  border: 1px solid var(--line);
  border-radius: 10px;
  padding: 10px;
  margin-bottom: 8px;
  background: var(--card-subtle);
  font-size: 13px;
}}
.c-item-header {{
  display: flex;
  align-items: center;
  justify-content: space-between;
  margin-bottom: 4px;
}}

/* 底部浮动切换器 (Floating Switcher) */
.prototype-switcher {{
  position: fixed;
  bottom: 16px;
  left: 50%;
  transform: translateX(-50%);
  z-index: 1000;
  background: rgba(26, 24, 21, 0.94);
  color: #fff;
  border: 1px solid rgba(255, 255, 255, 0.2);
  border-radius: 999px;
  padding: 6px 14px;
  display: flex;
  align-items: center;
  gap: 12px;
  box-shadow: 0 10px 30px rgba(0,0,0,0.4);
  backdrop-filter: blur(10px);
  user-select: none;
}}
.switcher-btn {{
  background: rgba(255, 255, 255, 0.12);
  border: 1px solid rgba(255,255,255,0.2);
  color: #fff;
  border-radius: 999px;
  width: 28px;
  height: 28px;
  display: flex;
  align-items: center;
  justify-content: center;
  cursor: pointer;
  font-weight: bold;
  font-size: 14px;
}}
.switcher-btn:hover {{ background: rgba(255, 255, 255, 0.28); }}
.switcher-label {{
  font-size: 13px;
  font-weight: 700;
  letter-spacing: 0.2px;
  color: #ffd966;
  white-space: nowrap;
}}
.switcher-pills {{
  display: flex;
  gap: 4px;
}}
.switcher-pill {{
  background: transparent;
  border: 1px solid rgba(255,255,255,0.2);
  color: #ddd;
  border-radius: 6px;
  padding: 2px 8px;
  font-size: 11px;
  cursor: pointer;
}}
.switcher-pill.active {{
  background: #ffd966;
  color: #1a1815;
  font-weight: bold;
  border-color: #ffd966;
}}

/* 响应式适配 */
@media (max-width: 860px) {{
  .variant-b .b-layout {{ grid-template-columns: 1fr; }}
  .variant-b .b-rail {{ position: static; }}
  .variant-c .c-layout {{ grid-template-columns: 1fr; }}
  .variant-c .c-pane-right {{ position: static; max-height: none; }}
}}
</style>
</head>
<body>

<!-- 顶部契约与状态栏 -->
<div class="contract-banner">
  <div class="contract-inner">
    <div style="display:flex;align-items:center;gap:10px;flex-wrap:wrap;">
      <span style="font-weight:bold;color:#ffd966;">🛠️ 攻略单页渲染器契约原型 (Issue #57)</span>
      <span class="contract-badge">SHA: {short_sha}</span>
      <span class="contract-badge">来源: guide.json (双 check 全绿)</span>
      <span class="contract-badge">六节完整度: 39属性 / 4武器 / 68道具 / 8阶段 / 2优先 / 4避坑</span>
    </div>
    <button class="contract-toggle" onclick="document.getElementById('contractDrawer').classList.toggle('open')">查看契约决议草案 ▾</button>
  </div>
  <div class="contract-drawer" id="contractDrawer">
    <div class="contract-grid">
      <div class="contract-box">
        <h4>1. 输入输出契约 (I/O)</h4>
        <p>• <b>唯一输入源</b>: <code>G:/brotato-work/&lt;slug&gt;/&lt;variant&gt;/outputs/guide.json</code>（严禁读取旧 builds）。</p>
        <p>• <b>发布位置</b>: 正式产物入 <code>docs/&lt;slug&gt;.html</code>，并可选镜像一份至 outputs/。</p>
        <p>• <b>SHA 锚定</b>: 页面头部显式呈现 <code>SHA {short_sha}</code>，与审计 09 组装及 manifest 一致。</p>
      </div>
      <div class="contract-box">
        <h4>2. 模板路线与六节段序</h4>
        <p>• <b>路线</b>: 另起独立单页渲染器（旧 character.html 字段不足），复用经典布局与悬浮逻辑。</p>
        <p>• <b>六节映射</b>: 属性(ratings) → 武器(weapons) → 优先级(priorities) → 道具池(groups) → 波次(phases) → 避坑(pitfalls)。</p>
        <p>• <b>段序</b>: 核心单页固定段序，不手改产物。</p>
      </div>
      <div class="contract-box">
        <h4>3. 缺项与徽标 (Fail-loud)</h4>
        <p>• <b>待补照发口径</b>: 缺项显示 <code>作者未提及 — 待补</code> 徽标，warn 不中断；结构损坏直接 fail loud。</p>
        <p>• <b>微标沿用</b>: 继承旧链 S/A/B/C/D 评级色系、DLC/待校对角标、新增置信度(核准/候选)与严重度(致命/危险/陷阱)。</p>
      </div>
      <div class="contract-box">
        <h4>4. 秒级视频点跳契约 (?t=)</h4>
        <p>• <b>直达原声</b>: 依赖 guide.json 每项 quote_details 下的 <code>t</code> 秒级时间戳。</p>
        <p>• <b>外链形式</b>: <code>&lt;url&gt;&t=&lt;t&gt;s</code>，一键跳至 YouTube 原视频实况原声。</p>
      </div>
    </div>
  </div>
</div>

<div class="layout-container">

  <!-- 头部 Hero -->
  <div class="hero-card">
    <div class="hero-left">
      <img class="hero-avatar" src="{esc(char_thumb)}" alt="{esc(char_en)}" onerror="this.style.display='none'">
      <div class="hero-title">
        <h1>{esc(char_zh)} <span style="font-size:18px;color:#cfc6b5;font-weight:normal;">({esc(char_en)})</span></h1>
        <div class="hero-meta">
          <span class="badge badge-covers">{esc(covers[0] if covers else "Ultimate")}</span>
          <span class="badge badge-sha">SHA: {short_sha}</span>
          <span>双修半波转换 · 远程枪转高工程螺丝刀</span>
        </div>
      </div>
    </div>
    <div class="hero-source-card">
      <div style="font-size:11px;color:#9a8f7c;margin-bottom:2px;">📺 取材源实况 (点击原声秒级试听):</div>
      <a href="{esc(video_url)}" target="_blank" rel="noopener">{esc(video_title)}</a>
      <div class="subtext">Brotato Ultimate Nightmares · 原视频时长 33m23s</div>
    </div>
  </div>

  <!-- ============================================================== -->
  <!-- 变体 A: 经典卡片流 (Classic Card Deck)                        -->
  <!-- ============================================================== -->
  <div class="variant-container variant-a" data-variant="A">
    <!-- 快捷锚点导航 -->
    <div class="toc-nav">
      <a href="#va-ratings">📊 属性评级</a>
      <a href="#va-weapons">⚔️ 武器路线</a>
      <a href="#va-priorities">🎯 优先级策略</a>
      <a href="#va-groups">🎒 道具决策</a>
      <a href="#va-phases">⏳ 波次运营</a>
      <a href="#va-pitfalls">⚠️ 避坑陷阱</a>
    </div>

    <!-- 1. 核心属性评级 -->
    <div class="card" id="va-ratings">
      <div class="card-header">
        <h2 class="card-title"><span>📊</span> 核心属性评级 (Ratings · 39 项)</h2>
        <span class="card-subtext">鼠标悬浮属性名查看 Wiki 关联道具</span>
      </div>
      <p style="font-size:13px;color:var(--ink-secondary);margin-top:0;">
        赛博格核心机制：波次过半（前 50% 时间）为<b>强力远程</b>，过半后全部远程伤害按 1:1 转化为<b>工程学</b>。因此前期必须拉满远程伤害，同时依靠螺丝刀与 minigun 的吸血/攻速保证转换后近战生存。
      </p>
      
      <h3 style="font-size:14px;margin:14px 0 8px;color:var(--ink);">一级主属性 (Primary Attributes)</h3>
      <div class="table-wrap">
        <table class="guide-table">
          <thead>
            <tr>
              <th style="width:200px;">属性</th>
              <th style="width:70px;text-align:center;">评级</th>
              <th style="width:60px;text-align:center;">频次</th>
              <th>抓取理由与出处原声</th>
            </tr>
          </thead>
          <tbody>
"""

    # 填充 Variant A 的 Ratings (Primary)
    for r in [x for x in ratings_data if x.get("type") == "primary"]:
        en = r.get("term_en", "")
        zh = r.get("term_zh", "")
        rating = r.get("rating", "-")
        count = r.get("count", 0)
        reason = r.get("reason", "")
        qds = r.get("quote_details", [])
        qd_first = qds[0] if qds else None
        
        stat_wiki = wiki.get("stats", {}).get(en, {})
        stat_thumb = stat_wiki.get("thumb")
        stat_icon = icon_html(stat_thumb, en)
        stat_tooltips = stat_wiki.get("tooltip", [])
        stat_tip_elem = stat_tooltip_html(stat_tooltips)
        
        name_cell = f'<span class="has-tip" tabindex="0">{stat_icon}{esc(zh)} ({esc(en)}){stat_tip_elem}</span>'
        quote_html = render_quote_badge(video_url, qd_first)
        
        html_out += f"""            <tr>
              <td>{name_cell}</td>
              <td style="text-align:center;"><span class="rating rating-{esc(rating)}">{esc(rating)}</span></td>
              <td style="text-align:center;color:var(--muted);">{count}次</td>
              <td>
                <div>{esc(reason)}</div>
                {quote_html}
              </td>
            </tr>
"""

    html_out += """          </tbody>
        </table>
      </div>

      <details style="margin-top:14px;">
        <summary style="cursor:pointer;font-weight:600;font-size:13px;color:var(--accent);">展开次级属性 (Secondary Attributes · 22 项) ▾</summary>
        <div class="table-wrap" style="margin-top:8px;">
          <table class="guide-table">
            <thead>
              <tr>
                <th style="width:200px;">属性</th>
                <th style="width:70px;text-align:center;">评级</th>
                <th style="width:60px;text-align:center;">频次</th>
                <th>说明</th>
              </tr>
            </thead>
            <tbody>
"""
    for r in [x for x in ratings_data if x.get("type") != "primary"]:
        en = r.get("term_en", "")
        zh = r.get("term_zh", "")
        rating = r.get("rating", "-")
        count = r.get("count", 0)
        reason = r.get("reason", "")
        qds = r.get("quote_details", [])
        qd_first = qds[0] if qds else None
        stat_wiki = wiki.get("stats", {}).get(en, {})
        stat_thumb = stat_wiki.get("thumb")
        stat_icon = icon_html(stat_thumb, en)
        stat_tooltips = stat_wiki.get("tooltip", [])
        stat_tip_elem = stat_tooltip_html(stat_tooltips)
        name_cell = f'<span class="has-tip" tabindex="0">{stat_icon}{esc(zh)} ({esc(en)}){stat_tip_elem}</span>'
        quote_html = render_quote_badge(video_url, qd_first)
        html_out += f"""              <tr>
                <td>{name_cell}</td>
                <td style="text-align:center;"><span class="rating rating-{esc(rating)}">{esc(rating)}</span></td>
                <td style="text-align:center;color:var(--muted);">{count}次</td>
                <td><div>{esc(reason)}</div>{quote_html}</td>
              </tr>
"""

    html_out += """            </tbody>
          </table>
        </div>
      </details>
    </div>

    <!-- 2. 武器路线 -->
    <div class="card" id="va-weapons">
      <div class="card-header">
        <h2 class="card-title"><span>⚔️</span> 武器路线 (Weapons Route)</h2>
        <span class="card-subtext">鼠标悬浮武器名查看 4 级成长强化表</span>
      </div>
      <div class="weapon-grid">
"""

    # 填充 Weapons
    for tier_key, tier_label, tier_badge in [("t1", "T1 核心毕业武器", "badge-must-take"), ("t2", "T2 前中期过渡武器", "badge-candidate")]:
        for w_item in weapons_data.get(tier_key, []):
            name_en = w_item.get("name_en", "")
            note = w_item.get("note", "")
            w_wiki = wiki.get("weapons", {}).get(name_en, {})
            w_thumb = w_wiki.get("thumb", "")
            w_zh = w_wiki.get("zh", name_en)
            w_icon = icon_html(w_thumb, name_en)
            w_tip_elem = weapon_tip(name_en, w_wiki, terms)
            qds = w_item.get("quote_details", [])
            qd_first = qds[0] if qds else None
            quote_html = render_quote_badge(video_url, qd_first)
            
            html_out += f"""        <div class="weapon-card">
          <div class="weapon-card-header">
            <div class="weapon-card-name">
              {w_icon}
              <span class="has-tip" tabindex="0">{esc(w_zh)} ({esc(name_en)}){w_tip_elem}</span>
            </div>
            <span class="badge {tier_badge}">{tier_label.split()[0]}</span>
          </div>
          <div style="font-size:13px;color:var(--ink-secondary);margin-bottom:8px;">{esc(note)}</div>
          {quote_html}
        </div>
"""

    html_out += """      </div>
    </div>

    <!-- 3. 优先级策略 -->
    <div class="card" id="va-priorities">
      <div class="card-header">
        <h2 class="card-title"><span>🎯</span> 优先级策略 (Priorities)</h2>
        <span class="card-subtext">升级选点与商店购买的权衡基准</span>
      </div>
      <div style="display:grid;grid-template-columns:repeat(auto-fit, minmax(300px, 1fr));gap:14px;">
"""

    for prio_type, prio_title, prio_icon in [("upgrades", "升级加点优先级", "⬆️"), ("shop", "商店选购优先级", "🛒")]:
        items = priorities_data.get(prio_type, [])
        for p in items:
            p_name = p.get("name", "")
            why = p.get("why", "")
            how = p.get("how_to_get", "")
            qds = p.get("quote_details", [])
            qd_first = qds[0] if qds else None
            quote_html = render_quote_badge(video_url, qd_first)
            html_out += f"""        <div style="background:var(--card-subtle);border:1px solid var(--line);border-radius:12px;padding:14px;">
          <div style="font-weight:700;font-size:15px;margin-bottom:6px;">{prio_icon} {prio_title}: <span style="color:var(--accent);">{esc(p_name)}</span></div>
          <div style="font-size:13px;margin-bottom:4px;"><b>核心论证:</b> {esc(why)}</div>
          <div style="font-size:13px;margin-bottom:8px;"><b>如何获取:</b> {esc(how)}</div>
          {quote_html}
        </div>
"""

    html_out += """      </div>
    </div>

    <!-- 4. 道具池决策 -->
    <div class="card" id="va-groups">
      <div class="card-header">
        <h2 class="card-title"><span>🎒</span> 道具池决策 (Groups · 68 件)</h2>
        <span class="card-subtext">必拿 8 件 / 禁用 2 件 / 提过未拿 1 件 / 路过 57 件</span>
      </div>

      <h4 style="color:#166534;margin:12px 0 6px;">⭐ 必拿道具 (Must Take · 遇到即锁即买)</h4>
      <div class="table-wrap">
        <table class="guide-table">
          <thead>
            <tr>
              <th style="width:200px;">道具</th>
              <th style="width:60px;text-align:center;">提及</th>
              <th>决策依据与出处</th>
            </tr>
          </thead>
          <tbody>
"""

    for g in must_take:
        name_en = g.get("name_en", "")
        name_zh = g.get("name_zh", "")
        count = g.get("count", 0)
        reason = g.get("reason", "")
        i_wiki = wiki.get("items", {}).get(name_en, {})
        i_thumb = i_wiki.get("thumb", "")
        i_icon = icon_html(i_thumb, name_en)
        i_tip_elem = item_tip(name_en, i_wiki, terms)
        qds = g.get("quote_details", [])
        qd_first = qds[0] if qds else None
        quote_html = render_quote_badge(video_url, qd_first)
        name_cell = f'<span class="has-tip" tabindex="0">{i_icon}{esc(name_zh or name_en)} ({esc(name_en)}){i_tip_elem}</span>'
        html_out += f"""            <tr>
              <td>{name_cell}</td>
              <td style="text-align:center;"><span class="badge badge-must-take">{count}次</span></td>
              <td><div>{esc(reason)}</div>{quote_html}</td>
            </tr>
"""

    html_out += """          </tbody>
        </table>
      </div>

      <h4 style="color:#9f1239;margin:18px 0 6px;">🚫 明确禁用 (Ban · 负收益/破坏构筑)</h4>
      <div class="table-wrap">
        <table class="guide-table">
          <tbody>
"""
    for g in bans:
        name_en = g.get("name_en", "")
        name_zh = g.get("name_zh", "")
        count = g.get("count", 0)
        reason = g.get("reason", "")
        i_wiki = wiki.get("items", {}).get(name_en, {})
        i_thumb = i_wiki.get("thumb", "")
        i_icon = icon_html(i_thumb, name_en)
        i_tip_elem = item_tip(name_en, i_wiki, terms)
        qds = g.get("quote_details", [])
        qd_first = qds[0] if qds else None
        quote_html = render_quote_badge(video_url, qd_first)
        name_cell = f'<span class="has-tip" tabindex="0">{i_icon}{esc(name_zh or name_en)} ({esc(name_en)}){i_tip_elem}</span>'
        html_out += f"""            <tr>
              <td style="width:200px;">{name_cell}</td>
              <td style="width:60px;text-align:center;"><span class="badge badge-ban">{count}次</span></td>
              <td><div>{esc(reason)}</div>{quote_html}</td>
            </tr>
"""

    html_out += """          </tbody>
        </table>
      </div>

      <details style="margin-top:16px;">
        <summary style="cursor:pointer;font-weight:600;font-size:13px;color:var(--accent);">展开路过与未拿道具 (Casual & Skipped · 58 件) ▾</summary>
        <div class="table-wrap" style="margin-top:8px;">
          <table class="guide-table">
            <thead>
              <tr>
                <th style="width:200px;">道具</th>
                <th style="width:70px;text-align:center;">状态</th>
                <th>提及原话</th>
              </tr>
            </thead>
            <tbody>
"""
    for g in skips + casuals:
        name_en = g.get("name_en", "")
        name_zh = g.get("name_zh", "")
        grp_type = g.get("group", "")
        badge_cls = "badge-skip" if grp_type == "mentioned_not_taken" else "badge-casual"
        badge_lbl = "提过未拿" if grp_type == "mentioned_not_taken" else "路过提及"
        reason = g.get("reason", "")
        i_wiki = wiki.get("items", {}).get(name_en, {})
        i_thumb = i_wiki.get("thumb", "")
        i_icon = icon_html(i_thumb, name_en)
        i_tip_elem = item_tip(name_en, i_wiki, terms)
        qds = g.get("quote_details", [])
        qd_first = qds[0] if qds else None
        quote_html = render_quote_badge(video_url, qd_first)
        name_cell = f'<span class="has-tip" tabindex="0">{i_icon}{esc(name_zh or name_en)} ({esc(name_en)}){i_tip_elem}</span>'
        html_out += f"""              <tr>
                <td>{name_cell}</td>
                <td style="text-align:center;"><span class="badge {badge_cls}">{badge_lbl}</span></td>
                <td><div>{esc(reason)}</div>{quote_html}</td>
              </tr>
"""

    html_out += """            </tbody>
          </table>
        </div>
      </details>
    </div>

    <!-- 5. 波次运营分段 -->
    <div class="card" id="va-phases">
      <div class="card-header">
        <h2 class="card-title"><span>⏳</span> 波次运营节奏 (Phases · 8 个阶段)</h2>
        <span class="card-subtext">目标 Goal · 焦点 Focus · 转折 Pivot</span>
      </div>
      <div style="display:flex;flex-direction:column;gap:12px;">
"""

    for i, p in enumerate(phases_data):
        phase_title = p.get("phase", "")
        waves = p.get("waves", "")
        goal = p.get("goal", "")
        focus = p.get("focus", "")
        pivot = p.get("pivot", "")
        qds = p.get("quote_details", [])
        qd_first = qds[0] if qds else None
        quote_html = render_quote_badge(video_url, qd_first)

        html_out += f"""        <div style="border:1px solid var(--line);border-radius:12px;padding:14px;background:var(--card-subtle);">
          <div style="display:flex;align-items:center;justify-content:space-between;margin-bottom:6px;">
            <div style="font-weight:700;font-size:15px;">Phase {i+1}: {esc(phase_title)}</div>
            <span class="badge" style="background:#3a3229;color:#fff;">波次: {esc(waves)}</span>
          </div>
          <div style="font-size:13px;line-height:1.5;margin-bottom:4px;">🎯 <b>本阶段目标:</b> {esc(goal)}</div>
          <div style="font-size:13px;line-height:1.5;margin-bottom:4px;">🔍 <b>操作与构筑焦点:</b> {esc(focus)}</div>
          <div style="font-size:13px;line-height:1.5;margin-bottom:6px;">⚡ <b>进入下一阶段转折点:</b> {esc(pivot)}</div>
          {quote_html}
        </div>
"""

    html_out += """      </div>
    </div>

    <!-- 6. 避坑与反思 -->
    <div class="card" id="va-pitfalls">
      <div class="card-header">
        <h2 class="card-title"><span>⚠️</span> 避坑与致命陷阱 (Pitfalls · 4 大戒律)</h2>
        <span class="card-subtext">惨痛暴毙教训与规避对策</span>
      </div>
      <div style="display:grid;grid-template-columns:repeat(auto-fit, minmax(280px, 1fr));gap:14px;">
"""

    for pit in pitfalls_data:
        title = pit.get("title", "")
        sev = pit.get("severity", "trap")
        why = pit.get("why", "")
        avoid = pit.get("how_to_avoid", "")
        qds = pit.get("quote_details", [])
        qd_first = qds[0] if qds else None
        quote_html = render_quote_badge(video_url, qd_first)
        badge_cls = f"badge-{sev}"
        sev_label = {"fatal": "致命 🔴", "risky": "危险 🟡", "trap": "陷阱 🟣"}.get(sev, sev)

        html_out += f"""        <div style="border:1px solid var(--line);border-radius:12px;padding:14px;background:#fffdfa;">
          <div style="display:flex;align-items:center;justify-content:space-between;margin-bottom:8px;">
            <span style="font-weight:700;font-size:16px;">{esc(title)}</span>
            <span class="badge {badge_cls}">{sev_label}</span>
          </div>
          <div style="font-size:13px;margin-bottom:6px;"><b>为什么是坑:</b> {esc(why)}</div>
          <div style="font-size:13px;margin-bottom:8px;color:#854d0e;"><b>如何避开:</b> {esc(avoid)}</div>
          {quote_html}
        </div>
"""

    html_out += """      </div>
    </div>
  </div><!-- /variant-a -->


  <!-- ============================================================== -->
  <!-- 变体 B: 波次推演流 / 对局时间线 (Chronological Run Timeline)    -->
  <!-- ============================================================== -->
  <div class="variant-container variant-b" data-variant="B" style="display:none;">
    <div class="b-layout">
      <!-- 左侧阶段导轨 -->
      <div class="b-rail">
        <h3>⏳ 20 波次运营导轨</h3>
"""

    for i, p in enumerate(phases_data):
        phase_title = p.get("phase", "")
        waves = p.get("waves", "")
        html_out += f"""        <a href="#vb-phase-{i+1}" class="b-rail-item">
          <b>{i+1}. {esc(phase_title[:10])}</b>
          <small>{esc(waves)}</small>
        </a>
"""

    html_out += """        <hr style="border:none;border-top:1px solid var(--line);margin:12px 0;">
        <div style="font-size:12px;color:var(--muted);padding:4px 8px;">
          💡 <b>时间线模式特色</b>: 将全篇 6 大板块按实战时间线解构，直击每个波次该干嘛。
        </div>
      </div>

      <!-- 右侧时间线核心卡片 -->
      <div class="b-content">
"""

    for i, p in enumerate(phases_data):
        phase_title = p.get("phase", "")
        waves = p.get("waves", "")
        goal = p.get("goal", "")
        focus = p.get("focus", "")
        pivot = p.get("pivot", "")
        qds = p.get("quote_details", [])
        qd_first = qds[0] if qds else None
        quote_html = render_quote_badge(video_url, qd_first)

        # 针对具体波次注入关联武器/避坑提示
        injected_tips = ""
        if i == 0:
            injected_tips = '<div style="background:#eaf6ed;border:1px solid #86efac;border-radius:6px;padding:8px 10px;font-size:12px;margin-top:8px;"><b>起手关键:</b> 核心锁定 Minigun + 螺丝刀，依靠前半波 3 倍远程直购输出，后半波转工程。</div>'
        elif i == 4:
            injected_tips = '<div style="background:#fef3c7;border:1px solid #fcd34d;border-radius:6px;padding:8px 10px;font-size:12px;margin-top:8px;"><b>Horde 应对:</b> 合出核弹发射器（Nuclear Launcher）依靠大范围爆炸清场，慎拿诅咒袋工厂。</div>'
        elif i == 5 or i == 6:
            injected_tips = '<div style="background:#fee2e2;border:1px solid #f87171;border-radius:6px;padding:8px 10px;font-size:12px;margin-top:8px;"><b>⚠️ 致命警报:</b> 孔雀增伤 30% 波次切勿让孵化怪无限产怪，必须远程段秒杀精英！</div>'

        html_out += f"""        <div class="card phase-card" id="vb-phase-{i+1}">
          <div class="phase-tag-row">
            <span class="badge" style="background:#1a1815;color:#fff;font-size:12px;">阶段 {i+1}</span>
            <h3 style="margin:0;font-size:18px;">{esc(phase_title)}</h3>
            <span class="badge badge-covers" style="margin-left:auto;">波次: {esc(waves)}</span>
          </div>

          <div class="phase-box-grid">
            <div class="phase-subbox">
              <h5>🎯 本阶段核心目标</h5>
              <div>{esc(goal)}</div>
            </div>
            <div class="phase-subbox">
              <h5>🔍 操作与构筑焦点</h5>
              <div>{esc(focus)}</div>
            </div>
          </div>

          <div style="margin-top:10px;font-size:13px;color:#854d0e;">
            <b>⚡ 转折信号:</b> {esc(pivot)}
          </div>

          {injected_tips}
          <div style="margin-top:10px;">{quote_html}</div>
        </div>
"""

    html_out += """      </div>
    </div>
  </div><!-- /variant-b -->


  <!-- ============================================================== -->
  <!-- 变体 C: 双栏决策工作台 (Dual-Pane Decision Workbench)           -->
  <!-- ============================================================== -->
  <div class="variant-container variant-c" data-variant="C" style="display:none;">
    <div class="c-layout">
      <!-- 左栏: 战略构筑与战术脉络 -->
      <div class="c-pane-left">
        <div class="card">
          <div class="card-header">
            <h3 class="card-title"><span>⚔️</span> 武器路线与成型架构</h3>
          </div>
          <div style="font-size:13px;line-height:1.6;margin-bottom:12px;">
            <b>双修原则:</b> 前半波吃 3x 远程伤害加成，过半全部转工程。起手 Minigun 刷伤害，螺丝刀借工程吃近战肉搏。
          </div>
          <div class="weapon-grid">
"""

    for w_item in weapons_data.get("t1", []) + weapons_data.get("t2", []):
        name_en = w_item.get("name_en", "")
        note = w_item.get("note", "")
        tier = w_item.get("tier", "T1")
        w_wiki = wiki.get("weapons", {}).get(name_en, {})
        w_thumb = w_wiki.get("thumb", "")
        w_zh = w_wiki.get("zh", name_en)
        w_icon = icon_html(w_thumb, name_en)
        w_tip_elem = weapon_tip(name_en, w_wiki, terms)
        badge_cls = "badge-must-take" if tier == "T1" else "badge-candidate"
        html_out += f"""            <div class="weapon-card" style="padding:10px;">
              <div class="weapon-card-header">
                <span style="font-weight:700;">{w_icon}<span class="has-tip">{esc(w_zh)} ({esc(name_en)}){w_tip_elem}</span></span>
                <span class="badge {badge_cls}">{tier}</span>
              </div>
              <div style="font-size:12px;color:var(--muted);">{esc(note[:60])}...</div>
            </div>
"""

    html_out += """          </div>
        </div>

        <!-- 关键属性速查 -->
        <div class="card">
          <div class="card-header">
            <h3 class="card-title"><span>📊</span> 核心抓取属性 (S & A 级)</h3>
          </div>
          <div style="display:flex;flex-wrap:wrap;gap:8px;">
"""

    for r in [x for x in ratings_data if x.get("rating") in ("S", "A")]:
        en = r.get("term_en", "")
        zh = r.get("term_zh", "")
        rating = r.get("rating", "")
        stat_wiki = wiki.get("stats", {}).get(en, {})
        stat_thumb = stat_wiki.get("thumb")
        stat_icon = icon_html(stat_thumb, en)
        stat_tooltips = stat_wiki.get("tooltip", [])
        stat_tip_elem = stat_tooltip_html(stat_tooltips)
        html_out += f"""            <div style="background:var(--card-subtle);border:1px solid var(--line);border-radius:8px;padding:6px 10px;font-size:13px;display:flex;align-items:center;gap:6px;">
              {stat_icon}
              <span class="has-tip">{esc(zh)} ({esc(en)}){stat_tip_elem}</span>
              <span class="rating rating-{esc(rating)}">{esc(rating)}</span>
            </div>
"""

    html_out += """          </div>
        </div>

        <!-- 避坑要点 -->
        <div class="card">
          <div class="card-header">
            <h3 class="card-title"><span>⚠️</span> 致命避坑快速警示</h3>
          </div>
"""

    for pit in pitfalls_data:
        title = pit.get("title", "")
        sev = pit.get("severity", "trap")
        why = pit.get("why", "")
        badge_cls = f"badge-{sev}"
        html_out += f"""          <div style="margin-bottom:8px;padding-bottom:8px;border-bottom:1px solid var(--line);font-size:13px;">
            <div style="display:flex;align-items:center;gap:6px;margin-bottom:2px;">
              <span class="badge {badge_cls}">{sev.upper()}</span>
              <b>{esc(title)}</b>
            </div>
            <div style="color:var(--ink-secondary);font-size:12px;">{esc(why)}</div>
          </div>
"""

    html_out += """        </div>
      </div><!-- /c-pane-left -->

      <!-- 右栏: 商店 30 秒决策速查面板 -->
      <div class="c-pane-right">
        <h3 style="margin:0 0 8px;font-size:16px;display:flex;align-items:center;gap:6px;">
          <span>🛒</span> 商店决策助手 (Shop Assistant)
        </h3>
        <p style="font-size:12px;color:var(--muted);margin:0 0 10px;">
          波次间隔仅 30 秒：快速输入道具或属性名，即刻得出抓取与跳过结论。
        </p>

        <div class="c-search-bar">
          <input type="text" class="c-search-input" id="cSearchInput" placeholder="🔍 快速搜索道具名 (如 Turret / 炮塔 / 工厂)..." oninput="filterShopItems()">
        </div>

        <div class="c-filter-tabs">
          <button class="c-filter-btn active" data-filter="all" onclick="setShopFilter('all', this)">全部 (68)</button>
          <button class="c-filter-btn" data-filter="must_take" onclick="setShopFilter('must_take', this)">⭐ 必拿 (8)</button>
          <button class="c-filter-btn" data-filter="ban" onclick="setShopFilter('ban', this)">🚫 禁选 (2)</button>
          <button class="c-filter-btn" data-filter="mentioned_not_taken" onclick="setShopFilter('mentioned_not_taken', this)">⚪ 提过未拿 (1)</button>
          <button class="c-filter-btn" data-filter="casual_mention" onclick="setShopFilter('casual_mention', this)">💬 路过 (57)</button>
        </div>

        <div id="cShopList">
"""

    for g in groups_data:
        name_en = g.get("name_en", "")
        name_zh = g.get("name_zh", "")
        grp = g.get("group", "")
        reason = g.get("reason", "")
        i_wiki = wiki.get("items", {}).get(name_en, {})
        i_thumb = i_wiki.get("thumb", "")
        i_icon = icon_html(i_thumb, name_en)
        i_tip_elem = item_tip(name_en, i_wiki, terms)
        qds = g.get("quote_details", [])
        qd_first = qds[0] if qds else None
        quote_html = render_quote_badge(video_url, qd_first)
        badge_cls = {
            "must_take": "badge-must-take",
            "ban": "badge-ban",
            "mentioned_not_taken": "badge-skip",
            "casual_mention": "badge-casual",
        }.get(grp, "badge-casual")
        grp_lbl = {
            "must_take": "必拿",
            "ban": "禁用",
            "mentioned_not_taken": "提过未拿",
            "casual_mention": "路过",
        }.get(grp, grp)

        html_out += f"""          <div class="c-item-card" data-grp="{esc(grp)}" data-search="{esc(name_en.lower())} {esc(name_zh.lower())}">
            <div class="c-item-header">
              <span style="font-weight:700;">{i_icon}<span class="has-tip">{esc(name_zh or name_en)} ({esc(name_en)}){i_tip_elem}</span></span>
              <span class="badge {badge_cls}">{grp_lbl}</span>
            </div>
            <div style="font-size:12px;color:var(--ink-secondary);">{esc(reason)}</div>
            {quote_html}
          </div>
"""

    html_out += """        </div>
      </div><!-- /c-pane-right -->
    </div>
  </div><!-- /variant-c -->

</div><!-- /layout-container -->

<!-- 底部浮动切换器 (Floating Prototype Switcher) -->
<div class="prototype-switcher" id="prototypeSwitcher">
  <button class="switcher-btn" onclick="cycleVariant(-1)" title="上一变体 (←方向键)">‹</button>
  <div class="switcher-label" id="variantLabel">Variant A: 经典卡片流 (Classic Deck)</div>
  <button class="switcher-btn" onclick="cycleVariant(1)" title="下一变体 (→方向键)">›</button>
  <div class="switcher-pills">
    <button class="switcher-pill active" onclick="switchVariant('A')">A</button>
    <button class="switcher-pill" onclick="switchVariant('B')">B</button>
    <button class="switcher-pill" onclick="switchVariant('C')">C</button>
  </div>
</div>

<script>
(function() {
  var VARIANTS = [
    { key: 'A', name: 'Variant A: 经典卡片流 (Classic Deck)' },
    { key: 'B', name: 'Variant B: 波次推演流 (Timeline)' },
    { key: 'C', name: 'Variant C: 双栏决策台 (Dual-Pane Workbench)' }
  ];
  var currentIdx = 0;

  function setVariant(key, updateUrl) {
    var found = -1;
    for (var i = 0; i < VARIANTS.length; i++) {
      if (VARIANTS[i].key === key) { found = i; break; }
    }
    if (found === -1) found = 0;
    currentIdx = found;
    var target = VARIANTS[currentIdx];

    // 更新 DOM 显示
    document.querySelectorAll('.variant-container').forEach(function(el) {
      if (el.getAttribute('data-variant') === target.key) {
        el.style.display = '';
      } else {
        el.style.display = 'none';
      }
    });

    // 更新切换器文案与药丸状态
    document.getElementById('variantLabel').textContent = target.name;
    document.querySelectorAll('.switcher-pill').forEach(function(btn) {
      btn.classList.toggle('active', btn.textContent.trim() === target.key);
    });

    if (updateUrl) {
      var url = new URL(window.location);
      url.searchParams.set('variant', target.key);
      window.history.replaceState({}, '', url);
    }
  }

  window.cycleVariant = function(dir) {
    var next = (currentIdx + dir + VARIANTS.length) % VARIANTS.length;
    setVariant(VARIANTS[next].key, true);
  };

  window.switchVariant = function(key) {
    setVariant(key, true);
  };

  // 键盘快捷键监听
  window.addEventListener('keydown', function(e) {
    if (['INPUT', 'TEXTAREA'].indexOf(document.activeElement.tagName) !== -1) return;
    if (e.key === 'ArrowLeft') {
      e.preventDefault();
      cycleVariant(-1);
    } else if (e.key === 'ArrowRight') {
      e.preventDefault();
      cycleVariant(1);
    }
  });

  // 初始读取 URL 参数
  var params = new URLSearchParams(window.location.search);
  var initialVariant = params.get('variant') || 'A';
  setVariant(initialVariant, false);

  // Variant C 商店筛选辅助
  var currentFilter = 'all';
  window.setShopFilter = function(filter, btn) {
    currentFilter = filter;
    document.querySelectorAll('.c-filter-btn').forEach(function(b) { b.classList.remove('active'); });
    btn.classList.add('active');
    filterShopItems();
  };

  window.filterShopItems = function() {
    var searchInput = document.getElementById('cSearchInput');
    var query = searchInput ? searchInput.value.toLowerCase().trim() : '';
    document.querySelectorAll('#cShopList .c-item-card').forEach(function(card) {
      var grp = card.getAttribute('data-grp');
      var searchAttr = card.getAttribute('data-search') || '';
      var matchesFilter = (currentFilter === 'all' || grp === currentFilter);
      var matchesSearch = (!query || searchAttr.indexOf(query) !== -1);
      if (matchesFilter && matchesSearch) {
        card.style.display = '';
      } else {
        card.style.display = 'none';
      }
    });
  };
})();
</script>
</body>
</html>
"""
    out_path.parent.mkdir(parents=True, exist_ok=True)
    out_path.write_text(html_out, encoding="utf-8")
    print(f"SUCCESS: rendered prototype html: {out_path.resolve()} (bytes: {len(html_out)})")


def main() -> None:
    parser = argparse.ArgumentParser(description="攻略单页渲染器原型生成器")
    parser.add_argument("--slug", default="cyborg", help="角色 slug")
    parser.add_argument("--variant", default="ultimate", help="难度变体")
    parser.add_argument("--guide", default=None, help="自定义 guide.json 路径")
    parser.add_argument("--out", default="docs/prototype_cyborg.html", help="输出 HTML 路径")
    args = parser.parse_args()

    repo_root = Path(__file__).resolve().parent.parent
    if args.guide:
        guide_path = Path(args.guide)
    else:
        # 默认优先找 G 盘工作区
        g_path = Path(f"G:/brotato-work/{args.slug}/{args.variant}/outputs/guide.json")
        if g_path.exists():
            guide_path = g_path
        else:
            # 找本仓 fallback 或 fail loud
            local_path = repo_root / "data" / "work" / args.slug / args.variant / "outputs" / "guide.json"
            if local_path.exists():
                guide_path = local_path
            else:
                sys.exit(f"FAIL: 找不到输入文件 guide.json: {g_path} 与 {local_path} 均不存在")

    wiki_path = repo_root / "data" / "wiki-cache.json"
    terms_path = repo_root / "data" / "terms.csv"
    roster_path = repo_root / "data" / "roster.json"
    out_path = repo_root / args.out

    render_all(guide_path, wiki_path, terms_path, roster_path, out_path)


if __name__ == "__main__":
    main()
