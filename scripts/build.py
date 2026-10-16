"""生产链骨架构建器 (#9): 单模板复用, 按角色与全量两种粒度生成纯静态页面.

源码唯一可改: data/roster.json + data/builds/<slug>.json
空壳: templates/character.html + templates/index.html
产物: docs/<slug>.html + docs/index.html (人不手改, 只改源码重构建)

机检:
- 缺段/改序即 fail (退出码 1)
- 缺验收线只 warn 加待补徽标但可发布 (退出码仍 0)
"""

from __future__ import annotations

import argparse
import html
import json
import sys
from pathlib import Path

# 10 段锁死顺序: 核心属性拆主次两表, 共 11 个 data-section。
# 与 #5 决议顺序一致, 不许增删改序。
SECTION_ORDER: list[str] = [
    "mechanism",
    "attrs-primary",
    "attrs-secondary",
    "weapons",
    "items",
    "phases",
    "upgrade",
    "shop",
    "pitfalls",
    "hard",
    "source",
]

# 构建数据必填顶层键: 缺键即结构 fail (缺段)。
REQUIRED_KEYS: list[str] = [
    "mechanism",
    "attrs_primary",
    "attrs_secondary",
    "weapons_t1",
    "weapons_t2",
    "items",
    "phases",
    "upgrade",
    "shop",
    "pitfalls",
    "hard",
    "source",
]

EXPECTED_WAVES: list[str] = ["W1-5", "W6-12", "W13-20"]


def esc(text: object) -> str:
    return html.escape(str(text), quote=True)


def rating_html(rating: object) -> str:
    if isinstance(rating, str) and rating in ("S", "A", "B", "C", "D", "F"):
        return f'<span class="rating rating-{esc(rating)}">{esc(rating)}</span>'
    return '<span class="rating rating-none" title="视频作者未提及，诚实空出">—</span>'


def attr_rows(attrs: list[dict[str, object]]) -> str:
    parts: list[str] = []
    for attr in attrs:
        name_zh = esc(attr.get("name_zh", ""))
        name_en = esc(attr.get("name_en", ""))
        rating = attr.get("rating")
        note = attr.get("note")
        note_html = esc(note) if isinstance(note, str) and note.strip() else (
            '<span class="empty">作者未提及</span>'
        )
        parts.append(
            "<tr><td>"
            f"{name_zh} ({name_en})"
            "</td>"
            f'<td class="rating-cell">{rating_html(rating)}</td>'
            f"<td>{note_html}</td></tr>"
        )
    if not parts:
        return '<tr><td colspan="3"><span class="empty">作者未提及 — 待补口径</span></td></tr>'
    return "".join(parts)


def weapon_rows(weapons: list[dict[str, object]]) -> str:
    if not weapons:
        return '<tr><td colspan="2"><span class="empty">作者未提及 — 待补口径</span></td></tr>'
    parts: list[str] = []
    for weapon in weapons:
        name_zh = esc(weapon.get("name_zh", ""))
        name_en = esc(weapon.get("name_en", ""))
        note = weapon.get("note")
        note_html = esc(note) if isinstance(note, str) and note.strip() else (
            '<span class="empty">作者未提及</span>'
        )
        parts.append(f"<tr><td><b>{name_zh} ({name_en})</b></td><td>{note_html}</td></tr>")
    return "".join(parts)


def item_rows(items: list[dict[str, object]]) -> str:
    if not items:
        return '<tr><td colspan="2"><span class="empty">作者未提及 — 待补口径</span></td></tr>'
    parts: list[str] = []
    for item in items:
        name_zh = esc(item.get("name_zh", ""))
        name_en = esc(item.get("name_en", ""))
        reason = item.get("reason")
        reason_html = esc(reason) if isinstance(reason, str) and reason.strip() else (
            '<span class="empty">作者未提及</span>'
        )
        parts.append(
            f"<tr><td><b>{name_zh} ({name_en})</b></td><td>{reason_html}</td></tr>"
        )
    return "".join(parts)


def phases_block(phases: list[dict[str, object]]) -> str:
    if not phases:
        return '<p><span class="empty">作者未提及 — 待补口径</span></p>'
    parts: list[str] = []
    for phase in phases:
        label = esc(phase.get("label", ""))
        waves = esc(phase.get("waves", ""))
        body = phase.get("body")
        body_html = esc(body) if isinstance(body, str) and body.strip() else (
            '<span class="empty">作者未提及</span>'
        )
        buy = phase.get("buy")
        buy_html = esc(buy) if isinstance(buy, str) and buy.strip() else ""
        buy_line = f"<br><span>买什么：{buy_html}</span>" if buy_html else ""
        # 首句括号波次范围: 保证 (W..) 出现在正文首句。
        parts.append(
            f"<h3>{label}（{waves}）</h3><p>（{waves}）{body_html}{buy_line}</p>"
        )
    return "".join(parts)


def source_block(source: dict[str, object]) -> str:
    title = esc(source.get("title", "待补"))
    url = esc(source.get("url", "#"))
    video_id = esc(source.get("video_id", "待补"))
    published = esc(source.get("published", "待补"))
    difficulty = esc(source.get("difficulty", "待补"))
    game_version = esc(source.get("game_version", "待补"))
    if not isinstance(source.get("url"), str) or not source.get("url"):
        url_display = '<span class="empty">作者未提及</span>'
    else:
        raw_url = str(source.get("url"))
        url_display = f'<a href="{esc(raw_url)}">{title}</a>'
    return (
        f"<p>主取材：{url_display}</p>"
        f"<p>视频 ID：<code>{video_id}</code> / 发布：{published} / 难度：{difficulty}</p>"
        f"<p>适用版本：{game_version}（发布日期 + 游戏版本双标注）</p>"
        "<p>转述非搬运，只留可复现骨架。</p>"
    )


def check_structure_data(data: dict[str, object]) -> list[str]:
    """结构机检: 缺必填键即 fail。返回错误列表, 为空即通过。"""
    errors: list[str] = []
    for key in REQUIRED_KEYS:
        if key not in data:
            errors.append(f"missing section data: {key}")
    phases = data.get("phases")
    if "phases" in data:
        if not isinstance(phases, list):
            errors.append("missing section data: phases (need exactly 3: W1-5/W6-12/W13-20)")
        elif len(phases) != 3:  # noqa: PLR2004
            errors.append("missing section data: phases (need exactly 3: W1-5/W6-12/W13-20)")
    for table_key in ("attrs_primary", "attrs_secondary"):
        if table_key in data:
            table = data.get(table_key)
            if not isinstance(table, list) or len(table) == 0:
                errors.append(f"missing section data: {table_key} (need >=1 row)")
    return errors


def check_acceptance(data: dict[str, object]) -> list[str]:
    """验收线机检: 缺项只 warn, 不 fail。返回警告列表。"""
    warns: list[str] = []
    mechanism = data.get("mechanism")
    if not isinstance(mechanism, str) or not mechanism.strip():
        warns.append("acceptance: 机制一句话缺项")
    ratings: list[object] = []
    for table_key in ("attrs_primary", "attrs_secondary"):
        table = data.get(table_key)
        if isinstance(table, list):
            for row in table:
                if isinstance(row, dict):
                    ratings.append(row.get("rating"))
    if not any(r in ("S", "A") for r in ratings):
        warns.append("acceptance: 属性 S/A 无口径")
    weapons_t1 = data.get("weapons_t1")
    if not isinstance(weapons_t1, list) or len(weapons_t1) < 1:
        warns.append("acceptance: 武器 T1 至少 1 把缺项")
    items = data.get("items")
    if not isinstance(items, list) or len(items) < 3:  # noqa: PLR2004
        warns.append("acceptance: 关键道具至少 3 件缺项")
    phases = data.get("phases")
    phase_ok = (
        isinstance(phases, list)
        and len(phases) == 3  # noqa: PLR2004
        and all(
            isinstance(p, dict)
            and isinstance(p.get("body"), str)
            and str(p.get("body")).strip()
            and p.get("waves") in EXPECTED_WAVES
            for p in phases
        )
    )
    if not phase_ok:
        warns.append("acceptance: 阶段转向点 / 波次范围缺项")
    for key in ("upgrade", "shop"):
        value = data.get(key)
        if not isinstance(value, str) or not value.strip():
            warns.append(f"acceptance: {key} Top3 缺项")
    source = data.get("source")
    if not isinstance(source, dict):
        warns.append("acceptance: 取材版本缺项")
    else:
        for field in ("url", "video_id", "published", "difficulty", "game_version"):
            value = source.get(field)
            if not isinstance(value, str) or not value.strip():
                warns.append(f"acceptance: 取材 {field} 缺项")
                break
    return warns


def check_structure_html(html_text: str) -> list[str]:
    """产物结构机检: 11 个 data-section 齐全且顺序正确, 否则 fail。"""
    import re

    found = re.findall(r'data-section="([^"]+)"', html_text)
    if found != SECTION_ORDER:
        return [
            f"section order mismatch: expected {SECTION_ORDER}, got {found}",
        ]
    return []


def render_character(
    roster_entry: dict[str, object],
    data: dict[str, object],
    template: str,
    warns: list[str],
) -> str:
    zh = esc(roster_entry.get("zh", ""))
    en = esc(roster_entry.get("en", ""))
    pending = (
        ' <span class="badge-pending">待补口径</span>' if warns else ""
    )
    mechanism = data.get("mechanism")
    mechanism_html = (
        esc(mechanism)
        if isinstance(mechanism, str) and mechanism.strip()
        else '<span class="empty">作者未提及 — 待补口径</span>'
    )
    upgrade = data.get("upgrade")
    upgrade_html = (
        esc(upgrade)
        if isinstance(upgrade, str) and upgrade.strip()
        else '<span class="empty">作者未提及 — 待补口径</span>'
    )
    shop = data.get("shop")
    shop_html = (
        esc(shop)
        if isinstance(shop, str) and shop.strip()
        else '<span class="empty">作者未提及 — 待补口径</span>'
    )
    hard = data.get("hard")
    hard_html = (
        esc(hard)
        if isinstance(hard, str) and hard.strip()
        else '<span class="empty">作者未提及 — 待补口径</span>'
    )
    pitfalls = data.get("pitfalls")
    if isinstance(pitfalls, list) and pitfalls:
        pitfalls_html = "".join(
            f"<li>{esc(p) if isinstance(p, str) and p.strip() else '<span class=\"empty\">作者未提及</span>'}</li>"
            for p in pitfalls
        )
    else:
        pitfalls_html = '<li><span class="empty">作者未提及 — 待补口径</span></li>'

    attrs_primary = data.get("attrs_primary")
    attrs_secondary = data.get("attrs_secondary")
    weapons_t1 = data.get("weapons_t1")
    weapons_t2 = data.get("weapons_t2")
    items = data.get("items")
    phases = data.get("phases")
    source = data.get("source")

    replacements: dict[str, str] = {
        "{{PAGE_TITLE}}": f"{roster_entry.get('zh', '')} ({roster_entry.get('en', '')}) · 土豆兄弟攻略",
        "{{ZH}}": zh,
        "{{EN}}": en,
        "{{PENDING_BADGE}}": pending,
        "{{MECHANISM}}": mechanism_html,
        "{{ATTRS_PRIMARY_ROWS}}": attr_rows(
            attrs_primary if isinstance(attrs_primary, list) else []
        ),
        "{{ATTRS_SECONDARY_ROWS}}": attr_rows(
            attrs_secondary if isinstance(attrs_secondary, list) else []
        ),
        "{{WEAPONS_T1_ROWS}}": weapon_rows(
            weapons_t1 if isinstance(weapons_t1, list) else []
        ),
        "{{WEAPONS_T2_ROWS}}": weapon_rows(
            weapons_t2 if isinstance(weapons_t2, list) else []
        ),
        "{{ITEMS_ROWS}}": item_rows(items if isinstance(items, list) else []),
        "{{PHASES_BLOCK}}": phases_block(phases if isinstance(phases, list) else []),
        "{{UPGRADE}}": upgrade_html,
        "{{SHOP}}": shop_html,
        "{{PITFALLS_ITEMS}}": pitfalls_html,
        "{{HARD}}": hard_html,
        "{{SOURCE_BLOCK}}": source_block(source if isinstance(source, dict) else {}),
    }
    out = template
    for token, value in replacements.items():
        out = out.replace(token, value)
    return out


def render_index(
    roster: list[dict[str, object]],
    built_slugs: set[str],
    template: str,
) -> str:
    parts: list[str] = []
    for entry in roster:
        slug = str(entry.get("id", ""))
        zh = esc(entry.get("zh", ""))
        en = esc(entry.get("en", ""))
        if slug in built_slugs:
            parts.append(
                '<div class="card"><div class="ava">🥔</div>'
                f'<div class="nm">{zh} ({en})<small>本体 · 可点</small></div>'
                f'<div class="right"><span class="tag ok">● 可点</span>'
                f'<div class="links"><a href="./{esc(slug)}.html">看攻略</a></div>'
                "</div></div>"
            )
        else:
            parts.append(
                '<div class="card"><div class="ava">🥔</div>'
                f'<div class="nm">{zh} ({en})<small>待填充</small></div>'
                '<div class="right"><span class="tag">待填充</span></div></div>'
            )
    count_line = f"共 {len(roster)} 个角色，当前可点 {len(built_slugs)} 个"
    out = template.replace("{{INDEX_ITEMS}}", "".join(parts))
    return out.replace("{{INDEX_COUNT}}", esc(count_line))


def load_json(path: Path) -> object:
    return json.loads(path.read_text(encoding="utf-8"))


def build_slug(
    slug: str,
    data_dir: Path,
    templates_dir: Path,
    out_dir: Path,
) -> tuple[list[str], list[str]]:
    """构建单个角色。返回 (errors, warns)。errors 非空则 fail。"""
    roster_raw = load_json(data_dir / "roster.json")
    roster: list[dict[str, object]] = (
        roster_raw if isinstance(roster_raw, list) else []
    )
    entry = next((r for r in roster if r.get("id") == slug), None)
    if entry is None:
        return ([f"unknown slug: {slug}"], [])
    build_path = data_dir / "builds" / f"{slug}.json"
    if not build_path.exists():
        return ([f"missing build data: {build_path}"], [])
    data_raw = load_json(build_path)
    data: dict[str, object] = data_raw if isinstance(data_raw, dict) else {}
    errors = check_structure_data(data)
    if errors:
        return (errors, [])
    warns = check_acceptance(data)
    template = (templates_dir / "character.html").read_text(encoding="utf-8")
    rendered = render_character(entry, data, template, warns)
    html_errors = check_structure_html(rendered)
    if html_errors:
        return (html_errors, warns)
    out_dir.mkdir(parents=True, exist_ok=True)
    (out_dir / f"{slug}.html").write_text(rendered, encoding="utf-8")
    return ([], warns)


def build_index(
    data_dir: Path,
    templates_dir: Path,
    out_dir: Path,
) -> None:
    roster_raw = load_json(data_dir / "roster.json")
    roster: list[dict[str, object]] = (
        roster_raw if isinstance(roster_raw, list) else []
    )
    built = {
        p.stem
        for p in (data_dir / "builds").glob("*.json")
        if (p.stem in {str(r.get("id")) for r in roster})
    }
    template = (templates_dir / "index.html").read_text(encoding="utf-8")
    rendered = render_index(roster, built, template)
    out_dir.mkdir(parents=True, exist_ok=True)
    (out_dir / "index.html").write_text(rendered, encoding="utf-8")


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="构建单角色页与索引页 (#9 骨架)")
    group = parser.add_mutually_exclusive_group(required=True)
    group.add_argument("--slug", help="按角色构建, 如 --slug cyborg")
    group.add_argument("--all", action="store_true", help="全量构建")
    parser.add_argument("--data-dir", default="data")
    parser.add_argument("--templates-dir", default="templates")
    parser.add_argument("--out-dir", default="docs")
    args = parser.parse_args(argv)

    repo = Path(__file__).resolve().parent.parent
    data_dir = Path(args.data_dir)
    if not data_dir.is_absolute():
        data_dir = repo / data_dir
    templates_dir = Path(args.templates_dir)
    if not templates_dir.is_absolute():
        templates_dir = repo / templates_dir
    out_dir = Path(args.out_dir)
    if not out_dir.is_absolute():
        out_dir = repo / out_dir

    if args.slug:
        errors, warns = build_slug(args.slug, data_dir, templates_dir, out_dir)
        if errors:
            for err in errors:
                print(f"FAIL: {err}", file=sys.stderr)
            return 1
        for warn in warns:
            print(f"WARN: {warn}")
        if warns:
            print("WARN: 待补口径徽标已注入, 仍可发布")
        build_index(data_dir, templates_dir, out_dir)
        print(f"built --slug {args.slug} -> {out_dir}")
        return 0

    # --all: 逐个构建 roster 中有 build 数据的角色, 无数据的仅索引置灰。
    roster_raw = load_json(data_dir / "roster.json")
    roster: list[dict[str, object]] = (
        roster_raw if isinstance(roster_raw, list) else []
    )
    failed = False
    for entry in roster:
        slug = str(entry.get("id", ""))
        build_path = data_dir / "builds" / f"{slug}.json"
        if not build_path.exists():
            continue
        errors, warns = build_slug(slug, data_dir, templates_dir, out_dir)
        if errors:
            for err in errors:
                print(f"FAIL [{slug}]: {err}", file=sys.stderr)
            failed = True
        for warn in warns:
            print(f"WARN [{slug}]: {warn}")
    build_index(data_dir, templates_dir, out_dir)
    print(f"built --all -> {out_dir}")
    return 1 if failed else 0


if __name__ == "__main__":
    raise SystemExit(main())
