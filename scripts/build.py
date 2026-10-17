"""生产链构建器 (#10): 名录 64 + 术语 17+22 单源重渲染.

源码唯一可改: data/roster.json + data/terms.csv + data/wiki-cache.json + data/builds/<slug>.json
空壳: templates/character.html + templates/index.html (A 长文式)
产物: docs/<slug>.html + docs/index.html (人不手改, 只改源码重构建)

机检:
- 缺段/改序/术语对不上/角标缺失/注册表缺 URL 即 fail (退出码 1)
- 缺验收线/待校对只 warn 加徽标但可发布 (退出码仍 0)
"""

from __future__ import annotations

import argparse
import csv
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
# #10 起 attrs_primary/secondary 由集中数据重渲染, 单角色包只给 ratings 口径。
REQUIRED_KEYS: list[str] = [
    "mechanism",
    "ratings",
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

# 单源基线: 主 17 + 次级 22, wiki 原序, 旧次级 3 口径作废。
EXPECTED_PRIMARY: list[str] = [
    "Max HP",
    "HP Regeneration",
    "Life Steal",
    "Damage",
    "Melee Damage",
    "Ranged Damage",
    "Elemental Damage",
    "Attack Speed",
    "Crit Chance",
    "Engineering",
    "Range",
    "Armor",
    "Dodge",
    "Speed",
    "Luck",
    "Harvesting",
    "Curse",
]

EXPECTED_SECONDARY: list[str] = [
    "Consumable Heal",
    "% Materials Healing",
    "% XP Gain",
    "% Pickup Range",
    "% Items Price",
    "% Explosion Damage",
    "% Explosion Size",
    "Bounces",
    "Piercing",
    "% Piercing Damage",
    "% Damage against Bosses",
    "% Structure Attack Speed",
    "Structure Range",
    "% Burning Speed",
    "Burning Spread",
    "Knockback",
    "% Double Material Chance",
    "Free Rerolls",
    "Trees",
    "% Enemies",
    "% Enemy Speed",
    "% Reroll Price",
]

WIKI_BASE = "https://brotato.wiki.spellsandguns.com"


def esc(text: object) -> str:
    return html.escape(str(text), quote=True)


def rating_html(rating: object) -> str:
    if isinstance(rating, str) and rating in ("S", "A", "B", "C", "D", "F"):
        return f'<span class="rating rating-{esc(rating)}">{esc(rating)}</span>'
    return '<span class="rating rating-none" title="视频作者未提及，诚实空出">—</span>'


def load_roster(data_dir: Path) -> list[dict[str, object]]:
    raw = json.loads((data_dir / "roster.json").read_text(encoding="utf-8"))
    if not isinstance(raw, list):
        raise ValueError("roster.json must be a list")
    out: list[dict[str, object]] = [r for r in raw if isinstance(r, dict)]
    return out


def validate_roster(roster: list[dict[str, object]]) -> list[str]:
    errors: list[str] = []
    if len(roster) != 64:
        errors.append(f"roster must be 64, got {len(roster)} (名录 64 齐全)")
        return errors
    abyssal = [r for r in roster if r.get("dlc") == "abyssal"]
    if len(abyssal) != 14:
        errors.append(f"roster abyssal DLC must be 14, got {len(abyssal)}")
    ids = [str(r.get("id", "")) for r in roster]
    if len(set(ids)) != 64:
        errors.append("roster ids must be unique (64)")
    ens = [str(r.get("en", "")) for r in roster]
    if len(set(ens)) != 64:
        errors.append("roster en must be unique (64)")
    for r in roster:
        dlc = r.get("dlc")
        if dlc not in (None, "abyssal"):
            # 允许未来 DLC (如 primal) 走追加, 但基线 64 只许 null/abyssal。
            # 若出现非基线 dlc, 视为追加未校对, 交 check_updates 细查, 此处先 fail 提示走追加。
            errors.append(f"roster dlc must be null|abyssal in baseline 64, got {dlc} for {r.get('id')}")
            break
        if not r.get("id") or not r.get("en") or "zh" not in r:
            errors.append(f"roster entry missing id/en/zh: {r}")
            break
    return errors


def load_terms(data_dir: Path) -> list[dict[str, str]]:
    path = data_dir / "terms.csv"
    with path.open(encoding="utf-8") as f:
        rows = list(csv.DictReader(f))
    # 规范化: 去空白
    out: list[dict[str, str]] = []
    for r in rows:
        out.append({k: (v.strip() if isinstance(v, str) else "") for k, v in r.items()})
    return out


def validate_terms(terms: list[dict[str, str]]) -> list[str]:
    errors: list[str] = []
    primary = [r for r in terms if r.get("type") == "primary"]
    secondary = [r for r in terms if r.get("type") == "secondary"]
    if len(primary) != 17 or len(secondary) != 22:
        # 旧口径识别: 次级 3 行即旧次级 3 口径作废。
        if len(secondary) == 3:
            errors.append("旧次级 3 口径作废，按全量 22 执行 (secondary must be 22, got 3)")
        else:
            errors.append(
                f"terms must be primary 17 + secondary 22, got {len(primary)}+{len(secondary)}"
            )
        return errors
    if [r["en"] for r in primary] != EXPECTED_PRIMARY:
        errors.append(f"primary order mismatch: expected {EXPECTED_PRIMARY}")
    if [r["en"] for r in secondary] != EXPECTED_SECONDARY:
        errors.append("secondary order mismatch: expected wiki secondary order (消耗品治疗到重随价格)")
    # DLC 角标源: Curse 与 % Reroll Price 必须 abyssal, 其余非 abyssal。
    by_en = {r["en"]: r for r in terms}
    for dlc_en in ("Curse", "% Reroll Price"):
        row = by_en.get(dlc_en)
        if row is None:
            errors.append(f"missing DLC term: {dlc_en}")
        elif row.get("dlc") != "abyssal":
            errors.append(f"DLC badge missing for {dlc_en}: dlc must be abyssal")
    for r in terms:
        if r["en"] not in ("Curse", "% Reroll Price") and r.get("dlc") == "abyssal":
            errors.append(f"unexpected DLC badge for {r['en']}")
            break
    return errors


def load_registry(data_dir: Path) -> dict[str, object]:
    path = data_dir / "wiki-cache.json"
    return json.loads(path.read_text(encoding="utf-8"))  # type: ignore[no-any-return]


def validate_registry(reg: dict[str, object], terms: list[dict[str, str]]) -> list[str]:
    errors: list[str] = []
    if not isinstance(reg.get("stats"), dict):
        return ["wiki-cache.json stats must be a dict"]
    stats = reg["stats"]
    assert isinstance(stats, dict)
    for t in terms:
        en = t["en"]
        entry = stats.get(en)
        if not isinstance(entry, dict):
            errors.append(f"registry missing URL for term: {en}")
            continue
        is_secondary = t.get("type") == "secondary"
        thumb = entry.get("thumb")
        missing = entry.get("missing")
        if is_secondary:
            if thumb and not missing:
                errors.append(f"secondary {en} must use placeholder (wiki 无专用图标)")
        else:
            if not isinstance(thumb, str) or not thumb:
                errors.append(f"registry missing URL for primary term: {en}")
            elif WIKI_BASE not in thumb:
                errors.append(f"registry thumb must be wiki hotlink for {en}")
    return errors


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


def tooltip_html(tips: list[dict[str, object]] | None, is_primary: bool) -> str:
    if not tips:
        return ""
    # 条目多时只列前 10, 余数计数 (原型已验证)。
    shown = tips[:10]
    more = len(tips) - len(shown)
    items = "".join(
        f"<span class=\"ti\"><img alt=\"\" src=\"{esc(t.get('thumb',''))}\" "
        f"loading=\"lazy\" referrerpolicy=\"no-referrer\" onerror=\"this.remove()\">"
        f"{esc(t.get('en',''))}</span>"
        for t in shown
        if isinstance(t, dict)
    )
    more_html = f"<span class=\"ti\">等共 {len(tips)} 件，详见 wiki</span>" if more > 0 else ""
    title = "加该属性的道具（wiki，主属性为单属性页 Positive，次级为 Notable Items）"
    return (
        f"<span class=\"tip\"><span class=\"th\">{title}</span>"
        f"{items}{more_html}"
        f"<span class=\"tf\">※ = 中文待客户端简中校对；英文为 wiki 原名</span></span>"
    )


def term_row(
    term: dict[str, str],
    rating: object,
    note: object,
    reg_entry: dict[str, object] | None,
) -> str:
    zh = str(term.get("zh", ""))
    en = str(term.get("en", ""))
    dlc = str(term.get("dlc", ""))
    needs = str(term.get("needs_review", ""))
    pending = needs.upper() == "TRUE"
    # 写法: 中文 (English) + DLC 角标 + 待校对标记, 不自造翻译。
    display = f"{zh} ({en})"
    if pending:
        display += "※"
    badges = ""
    if dlc == "abyssal":
        badges += ' <span class="badge-dlc" title="Abyssal Terrors DLC 专属">DLC</span>'
    if pending:
        badges += ' <span class="badge-review" title="中文待客户端简中校对">待校对</span>'
    # 图标: 主表 wiki 热链三件套, 次级统一占位。
    if reg_entry and isinstance(reg_entry.get("thumb"), str) and reg_entry.get("thumb"):
        thumb = str(reg_entry.get("thumb"))
        icon = (
            f"<img class=\"sic\" alt=\"{esc(en)}\" width=\"20\" height=\"20\" "
            f"src=\"{esc(thumb)}\" loading=\"lazy\" "
            f"referrerpolicy=\"no-referrer\" onerror=\"this.remove()\"> "
        )
    else:
        icon = "<span class=\"sic none\" title=\"wiki 无专用图标\">◆</span> "
    # 悬浮: 有 tooltip 则 hover, 诅咒无 Positive 区则无悬浮。
    tips = reg_entry.get("tooltip") if isinstance(reg_entry, dict) else None
    tip_list: list[dict[str, object]] | None = tips if isinstance(tips, list) else None
    name_inner = f"{esc(display)}{badges}"
    if tip_list:
        is_primary = term.get("type") == "primary"
        name_html = (
            f"<span class=\"has-tip\" tabindex=\"0\">{name_inner}"
            f"{tooltip_html(tip_list, is_primary)}</span>"
        )
    else:
        name_html = name_inner
    rating_cell = rating_html(rating)
    if isinstance(note, str) and note.strip():
        note_html = esc(note)
    else:
        note_html = '<span class="empty">作者未提及</span>'
    return f"<tr><td>{icon}{name_html}</td><td class=\"rating-cell\">{rating_cell}</td><td>{note_html}</td></tr>"


def build_term_tables(
    terms: list[dict[str, str]],
    ratings: dict[str, object],
    reg: dict[str, object],
) -> tuple[str, str, list[str], list[str]]:
    """集中数据重渲染两表。返回 (主表行, 次级表行, errors, warns)。"""
    errors: list[str] = []
    warns: list[str] = []
    stats = reg.get("stats")
    reg_map: dict[str, object] = stats if isinstance(stats, dict) else {}
    # 术语对不上即 fail: ratings 出现未知英文。
    term_ens = {t["en"] for t in terms}
    for r_en in ratings.keys():
        if r_en not in term_ens:
            errors.append(f"术语对不上即 fail: 未知术语 {r_en} (not in terms.csv)")
    if errors:
        return ("", "", errors, warns)
    primary_terms = [t for t in terms if t.get("type") == "primary"]
    secondary_terms = [t for t in terms if t.get("type") == "secondary"]
    # 待校对只 warn 加标。
    pending_count = sum(1 for t in terms if str(t.get("needs_review", "")).upper() == "TRUE")
    if pending_count:
        warns.append(f"术语待校对 {pending_count} 项（※），中文以客户端简中为准")
    primary_rows: list[str] = []
    for term in primary_terms:
        en = term["en"]
        entry = ratings.get(en)
        rating: object = None
        note: object = None
        if isinstance(entry, dict):
            rating = entry.get("rating")
            note = entry.get("note")
        reg_entry = reg_map.get(en)
        rd: dict[str, object] | None = reg_entry if isinstance(reg_entry, dict) else None
        primary_rows.append(term_row(term, rating, note, rd))
    secondary_rows: list[str] = []
    for term in secondary_terms:
        en = term["en"]
        entry = ratings.get(en)
        rating2: object = None
        note2: object = None
        if isinstance(entry, dict):
            rating2 = entry.get("rating")
            note2 = entry.get("note")
        reg_entry2 = reg_map.get(en)
        rd2: dict[str, object] | None = reg_entry2 if isinstance(reg_entry2, dict) else None
        secondary_rows.append(term_row(term, rating2, note2, rd2))
    return ("".join(primary_rows), "".join(secondary_rows), errors, warns)


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
    ratings = data.get("ratings")
    if "ratings" in data and not isinstance(ratings, dict):
        errors.append("missing section data: ratings (need dict en->rating/note)")
    return errors


def check_acceptance(data: dict[str, object]) -> list[str]:
    """验收线机检: 缺项只 warn, 不 fail。返回警告列表。"""
    warns: list[str] = []
    mechanism = data.get("mechanism")
    if not isinstance(mechanism, str) or not mechanism.strip():
        warns.append("acceptance: 机制一句话缺项")
    ratings = data.get("ratings")
    found_sa = False
    if isinstance(ratings, dict):
        for v in ratings.values():
            if isinstance(v, dict) and v.get("rating") in ("S", "A"):
                found_sa = True
                break
    if not found_sa:
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
    primary_rows: str,
    secondary_rows: str,
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
        "{{ATTRS_PRIMARY_ROWS}}": primary_rows,
        "{{ATTRS_SECONDARY_ROWS}}": secondary_rows,
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
        dlc = entry.get("dlc")
        dlc_label = "Abyssal Terrors DLC" if dlc == "abyssal" else "本体"
        if slug in built_slugs:
            parts.append(
                '<div class="card"><div class="ava">🥔</div>'
                f'<div class="nm">{zh} ({en})<small>{dlc_label} · 可点</small></div>'
                f'<div class="right"><span class="tag ok">● 可点</span>'
                f'<div class="links"><a href="./{esc(slug)}.html">看攻略</a></div>'
                "</div></div>"
            )
        else:
            parts.append(
                '<div class="card"><div class="ava">🥔</div>'
                f'<div class="nm">{zh} ({en})<small>{dlc_label} · 待填充</small></div>'
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
    try:
        roster = load_roster(data_dir)
    except Exception as exc:
        return ([f"roster load fail: {exc}"], [])
    roster_errors = validate_roster(roster)
    if roster_errors:
        return (roster_errors, [])
    try:
        terms = load_terms(data_dir)
    except Exception as exc:
        return ([f"terms load fail: {exc}"], [])
    terms_errors = validate_terms(terms)
    if terms_errors:
        return (terms_errors, [])
    try:
        reg = load_registry(data_dir)
    except Exception as exc:
        return ([f"registry load fail: {exc}"], [])
    reg_errors = validate_registry(reg, terms)
    if reg_errors:
        return (reg_errors, [])
    entry = next((r for r in roster if r.get("id") == slug), None)
    if entry is None:
        return ([f"unknown slug: {slug} (Mod 拒收: 无名录无 Steam App 无 wiki 主表)"], [])
    build_path = data_dir / "builds" / f"{slug}.json"
    if not build_path.exists():
        return ([f"missing build data: {build_path}"], [])
    data_raw = load_json(build_path)
    data: dict[str, object] = data_raw if isinstance(data_raw, dict) else {}
    errors = check_structure_data(data)
    if errors:
        return (errors, [])
    ratings_raw = data.get("ratings")
    ratings: dict[str, object] = ratings_raw if isinstance(ratings_raw, dict) else {}
    primary_rows, secondary_rows, term_errors, term_warns = build_term_tables(terms, ratings, reg)
    if term_errors:
        return (term_errors, [])
    warns = check_acceptance(data)
    warns.extend(term_warns)
    # 名录待校对只 warn。
    if str(entry.get("needs_review", "")).upper() == "TRUE" or entry.get("needs_review") is True:
        warns.append(f"名录中文待校对: {entry.get('id')}（※），以客户端简中为准")
    template = (templates_dir / "character.html").read_text(encoding="utf-8")
    rendered = render_character(entry, primary_rows, secondary_rows, data, template, warns)
    html_errors = check_structure_html(rendered)
    if html_errors:
        return (html_errors, warns)
    # 角标缺失即 fail: 渲染后必须含 DLC 角标 (Curse 与重随价格)。
    if "badge-dlc" not in rendered or "Curse" not in rendered or "Reroll Price" not in rendered:
        return (["DLC badge missing in rendered page (角标缺失即 fail)"], warns)
    out_dir.mkdir(parents=True, exist_ok=True)
    (out_dir / f"{slug}.html").write_text(rendered, encoding="utf-8")
    return ([], warns)


def build_index(
    data_dir: Path,
    templates_dir: Path,
    out_dir: Path,
) -> None:
    roster = load_roster(data_dir)
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
    parser = argparse.ArgumentParser(description="构建单角色页与索引页 (#10 单源)")
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
            print("WARN: 待补口径/待校对徽标已注入, 仍可发布")
        build_index(data_dir, templates_dir, out_dir)
        print(f"built --slug {args.slug} -> {out_dir}")
        return 0

    # --all: 逐个构建 roster 中有 build 数据的角色, 无数据的仅索引置灰。
    roster = load_roster(data_dir)
    # 全量前先校验单源基线一次, 基线错即全量 fail。
    try:
        terms = load_terms(data_dir)
    except Exception as exc:
        print(f"FAIL: terms load fail: {exc}", file=sys.stderr)
        return 1
    terms_errors = validate_terms(terms)
    if terms_errors:
        for err in terms_errors:
            print(f"FAIL: {err}", file=sys.stderr)
        return 1
    roster_errors = validate_roster(roster)
    if roster_errors:
        for err in roster_errors:
            print(f"FAIL: {err}", file=sys.stderr)
        return 1
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
