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
    for section, required in (
        ("items", ("tier", "effects", "price", "unlock", "tags")),
        ("weapons", ("class", "stats", "special", "price", "unlock")),
    ):
        sec = reg.get(section)
        if not isinstance(sec, dict):
            errors.append(f"wiki-cache.json {section} must be a dict")
            continue
        for en, entry in sec.items():
            if not isinstance(entry, dict):
                errors.append(f"registry {section} entry broken: {en}")
                continue
            for url_field in ("page", "thumb"):
                value = entry.get(url_field)
                if not isinstance(value, str) or WIKI_BASE not in value:
                    errors.append(f"registry missing URL for {section}: {en} ({url_field})")
            if entry.get("dlc") not in (None, "", "abyssal"):
                errors.append(f"registry dlc must be null|abyssal, got {entry.get('dlc')} for {section}:{en}")
            for field in required:
                if field not in entry:
                    errors.append(f"registry {section} schema missing {field}: {en}")
            if section == "weapons" and isinstance(entry, dict):
                wstats = entry.get("stats")
                stat_list: list[object] = wstats if isinstance(wstats, list) else []
                for s in stat_list:
                    lvs = s.get("lv") if isinstance(s, dict) else None
                    lv_list: list[object] = lvs if isinstance(lvs, list) else []
                    if len(lv_list) != 4:
                        errors.append(f"registry weapons schema: {en} stat must have 4 levels")
                        break
                price = entry.get("price")
                price_list: list[object] = price if isinstance(price, list) else []
                if len(price_list) != 4:
                    errors.append(f"registry weapons schema: {en} price must have 4 levels")
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


def icon_html(thumb: object, en: str) -> str:
    """图标三件套同一渲染路径 (#12 复用, #15 武器道具共用): 有图挂热链, 无图占位。"""
    if isinstance(thumb, str) and thumb:
        return (
            f"<img class=\"sic\" alt=\"{esc(en)}\" width=\"20\" height=\"20\" "
            f"src=\"{esc(thumb)}\" loading=\"lazy\" "
            f"referrerpolicy=\"no-referrer\" onerror=\"this.remove()\"> "
        )
    return "<span class=\"sic none\" title=\"wiki 无专用图标\">◆</span> "


def term_text(en: str, terms_by_en: dict[str, dict[str, str]]) -> str:
    """术语中英对照 (#15): 有客户端简中即中文括号英文, 缺中文只发英文不自造。"""
    row = terms_by_en.get(en)
    if row is None:
        return en
    zh = str(row.get("zh", "")).strip()
    if zh:
        text = f"{zh} ({en})"
        if str(row.get("needs_review", "")).upper() == "TRUE":
            text += "※"
        return text
    return en


def effect_html(eff: dict[str, object], terms_by_en: dict[str, dict[str, str]]) -> str:
    """单条效果行: wiki 原样, 数值保留红绿语义, 术语名加对照。"""
    if "free" in eff:
        return esc(eff.get("free", ""))
    val_cls = "neg" if eff.get("neg") else "pos"
    out = ""
    if eff.get("pre"):
        out += esc(eff.get("pre", "")) + " "
    out += f"<span class=\"{val_cls}\">{esc(eff.get('val', ''))}</span>"
    term = eff.get("term")
    suf = str(eff.get("suf", ""))
    if term and not eff.get("pre") and isinstance(term, str):
        pct = "% " if suf.startswith("%") else ""
        out += " " + pct + esc(term_text(term, terms_by_en))
    elif suf:
        out += " " + esc(suf)
    return out


def kv_row(key_en: str, value_html: str, terms_by_en: dict[str, dict[str, str]]) -> str:
    """悬浮内键值行: 占满整行 grid (与 .th/.tm/.tf 同规则)。"""
    if key_en in terms_by_en:
        key = esc(term_text(key_en, terms_by_en))
    else:
        key = esc(key_en)
    return f"<span class=\"kv\"><span class=\"ke\">{key}</span><span class=\"kx\">{value_html}</span></span>"


def entry_name_html(en: str, entry: dict[str, object]) -> str:
    """条目名: 注册表中文 (en), 缺中文只发英文; 待校对加标只 warn。"""
    zh = str(entry.get("zh", "")).strip()
    pending = entry.get("needs_review") is True or str(entry.get("needs_review", "")).upper() == "TRUE"
    display = f"{zh} ({en})" if zh else en
    if pending:
        display += "※"
    badges = ""
    if entry.get("dlc") == "abyssal":
        badges += ' <span class="badge-dlc" title="Abyssal Terrors DLC 专属">DLC</span>'
    if pending:
        badges += ' <span class="badge-review" title="中文待客户端简中校对">待校对</span>'
    return f"{esc(display)}{badges}"


def item_tip(en: str, entry: dict[str, object], terms_by_en: dict[str, dict[str, str]]) -> str:
    """道具悬浮: Items 行 7 列原样 (名称/稀有度/效果/价格/上限/解锁/标签) 加对照。"""
    effs = entry.get("effects")
    eff_list: list[object] = effs if isinstance(effs, list) else []
    eff_html = "<br>".join(
        effect_html(e, terms_by_en) if isinstance(e, dict) else esc(e) for e in eff_list
    )
    tags = entry.get("tags")
    tag_list: list[object] = tags if isinstance(tags, list) else []
    tag_html = ", ".join(
        esc(term_text(str(t), terms_by_en)) if str(t) in terms_by_en else esc(t)
        for t in tag_list
    )
    rows = [
        kv_row("Effects", eff_html or "—", terms_by_en),
        kv_row("Base Price", esc(entry.get("price", "")) or "—", terms_by_en),
        kv_row("Limit", esc(entry.get("limit", "")) or "—", terms_by_en),
        kv_row("Unlocked By", esc(entry.get("unlock", "")) or "—", terms_by_en),
        kv_row("Tags", tag_html or "—", terms_by_en),
    ]
    return (
        f"<span class=\"tip\"><span class=\"th\">{esc(str(entry.get('tier', '')))}</span>"
        f"{''.join(rows)}"
        f"<span class=\"tf\">※ = 中文待客户端简中校对；英文为 wiki 原名</span></span>"
    )


def level_html(lv_entry: object) -> str:
    """单等级值: 等级色 w1-w4 (对照 wiki 白/蓝/紫/红); scaling 依据见表下 legend 行。"""
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
    return f"<span class=\"w{num}\">{inner}</span>"


def stat_label(key_en: str, terms_by_en: dict[str, dict[str, str]]) -> str:
    if key_en in terms_by_en:
        return esc(term_text(key_en, terms_by_en))
    return esc(key_en)


def weapon_tip(en: str, entry: dict[str, object], terms_by_en: dict[str, dict[str, str]]) -> str:
    """武器悬浮: Weapons List 转置 (行=属性, 列=Lv1-4) 加等级色与对照。"""
    stats = entry.get("stats")
    stat_list: list[object] = stats if isinstance(stats, list) else []
    head = "<tr><th></th><th>Lv1</th><th>Lv2</th><th>Lv3</th><th>Lv4</th></tr>"
    body: list[str] = []
    scales: list[str] = []
    for s in stat_list:
        if not isinstance(s, dict):
            continue
        lvs = s.get("lv")
        lv_list: list[object] = lvs if isinstance(lvs, list) else []
        for v in lv_list:
            if isinstance(v, dict) and v.get("s") and str(v.get("s")) not in scales:
                scales.append(str(v.get("s")))
        cells = [f"<td>{level_html(v)}</td>" for v in lv_list[:4]]
        while len(cells) < 4:
            cells.append("<td>—</td>")
        body.append(f"<tr><th>{stat_label(str(s.get('k', '')), terms_by_en)}</th>{''.join(cells)}</tr>")
    if scales:
        scale_html = ", ".join(esc(term_text(s, terms_by_en)) for s in scales)
        body.append(
            "<tr><th>Scaling</th><td colspan=\"4\" class=\"span\">"
            f"{scale_html}</td></tr>"
        )
    price = entry.get("price")
    price_list: list[object] = price if isinstance(price, list) else []
    pcells = [f"<td>{level_html(v)}</td>" for v in price_list[:4]]
    while len(pcells) < 4:
        pcells.append("<td>—</td>")
    body.append(f"<tr><th>Base Price</th>{''.join(pcells)}</tr>")
    for key in ("Special Effects", "Unlocked By"):
        field = "special" if key == "Special Effects" else "unlock"
        body.append(
            f"<tr><th>{esc(key)}</th><td colspan=\"4\" class=\"span\">"
            f"{esc(entry.get(field, '')) or '—'}</td></tr>"
        )
    table = f"<span class=\"tw\"><table class=\"wt\">{head}{''.join(body)}</table></span>"
    return (
        f"<span class=\"tip\"><span class=\"th\">{esc(str(entry.get('class', '')))}</span>"
        f"{table}"
        f"<span class=\"tf\">※ = 中文待客户端简中校对；英文为 wiki 原名</span></span>"
    )


def weapon_rows(
    weapons: list[dict[str, object]],
    reg: dict[str, object],
    terms_by_en: dict[str, dict[str, str]],
) -> tuple[str, list[str], list[str]]:
    """武器行: 注册表唯一源, 未知即 fail; 有条目则名可悬浮。返回 (html, errors, warns)。"""
    if not weapons:
        return ('<tr><td colspan="2"><span class="empty">作者未提及 — 待补口径</span></td></tr>', [], [])
    errors: list[str] = []
    warns: list[str] = []
    parts: list[str] = []
    for weapon in weapons:
        if not isinstance(weapon, dict):
            errors.append("武器条目结构错即 fail: need dict")
            continue
        name_en = str(weapon.get("name_en", "")).strip()
        entry = reg.get(name_en)
        if not isinstance(entry, dict):
            errors.append(f"未知武器即 fail: {name_en} (不在 weapons 注册表)")
            continue
        if entry.get("needs_review") is True or str(entry.get("needs_review", "")).upper() == "TRUE":
            warns.append(f"武器待校对: {name_en}（※），中文以客户端简中为准")
        note = weapon.get("note")
        note_html = esc(note) if isinstance(note, str) and note.strip() else (
            '<span class="empty">作者未提及</span>'
        )
        name_html = (
            f"<span class=\"has-tip gear\" tabindex=\"0\">{entry_name_html(name_en, entry)}"
            f"{weapon_tip(name_en, entry, terms_by_en)}</span>"
        )
        thumb = entry.get("thumb")
        parts.append(f"<tr><td>{icon_html(thumb, name_en)}{name_html}</td><td>{note_html}</td></tr>")
    return ("".join(parts), errors, warns)


def item_rows(
    items: list[dict[str, object]],
    reg: dict[str, object],
    terms_by_en: dict[str, dict[str, str]],
) -> tuple[str, list[str], list[str]]:
    """道具行: 注册表唯一源, 未知即 fail; 有条目则名可悬浮。返回 (html, errors, warns)。"""
    if not items:
        return ('<tr><td colspan="2"><span class="empty">作者未提及 — 待补口径</span></td></tr>', [], [])
    errors: list[str] = []
    warns: list[str] = []
    parts: list[str] = []
    for item in items:
        if not isinstance(item, dict):
            errors.append("道具条目结构错即 fail: need dict")
            continue
        name_en = str(item.get("name_en", "")).strip()
        entry = reg.get(name_en)
        if not isinstance(entry, dict):
            errors.append(f"未知道具即 fail: {name_en} (不在 items 注册表)")
            continue
        if entry.get("needs_review") is True or str(entry.get("needs_review", "")).upper() == "TRUE":
            warns.append(f"道具待校对: {name_en}（※），中文以客户端简中为准")
        reason = item.get("reason")
        reason_html = esc(reason) if isinstance(reason, str) and reason.strip() else (
            '<span class="empty">作者未提及</span>'
        )
        name_html = (
            f"<span class=\"has-tip gear\" tabindex=\"0\">{entry_name_html(name_en, entry)}"
            f"{item_tip(name_en, entry, terms_by_en)}</span>"
        )
        thumb = entry.get("thumb")
        parts.append(f"<tr><td>{icon_html(thumb, name_en)}{name_html}</td><td>{reason_html}</td></tr>")
    return ("".join(parts), errors, warns)


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
        f"<span class=\"tn\">{esc(t.get('en',''))}</span></span>"
        for t in shown
        if isinstance(t, dict)
    )
    more_html = f"<span class=\"tm\">等共 {len(tips)} 件，详见 wiki</span>" if more > 0 else ""
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
    # 图标: 主表 wiki 热链三件套, 次级统一占位 (同一渲染路径 icon_html)。
    thumb = reg_entry.get("thumb") if isinstance(reg_entry, dict) else None
    icon = icon_html(thumb, en)
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
    weapons_t1_rows: str,
    weapons_t2_rows: str,
    items_rows: str,
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
        "{{WEAPONS_T1_ROWS}}": weapons_t1_rows,
        "{{WEAPONS_T2_ROWS}}": weapons_t2_rows,
        "{{ITEMS_ROWS}}": items_rows,
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
    terms_by_en: dict[str, dict[str, str]] = {t["en"]: t for t in terms}
    reg_items = reg.get("items")
    reg_weapons = reg.get("weapons")
    items_map: dict[str, object] = reg_items if isinstance(reg_items, dict) else {}
    weapons_map: dict[str, object] = reg_weapons if isinstance(reg_weapons, dict) else {}
    weapons_t1_raw = data.get("weapons_t1")
    weapons_t2_raw = data.get("weapons_t2")
    items_raw = data.get("items")
    weapons_t1_rows, w1_errors, w1_warns = weapon_rows(
        weapons_t1_raw if isinstance(weapons_t1_raw, list) else [], weapons_map, terms_by_en
    )
    weapons_t2_rows, w2_errors, w2_warns = weapon_rows(
        weapons_t2_raw if isinstance(weapons_t2_raw, list) else [], weapons_map, terms_by_en
    )
    items_rows, item_errors, item_warns = item_rows(
        items_raw if isinstance(items_raw, list) else [], items_map, terms_by_en
    )
    gear_errors = w1_errors + w2_errors + item_errors
    if gear_errors:
        return (gear_errors, [])
    warns = check_acceptance(data)
    warns.extend(term_warns)
    warns.extend(w1_warns + w2_warns + item_warns)
    # 名录待校对只 warn。
    if str(entry.get("needs_review", "")).upper() == "TRUE" or entry.get("needs_review") is True:
        warns.append(f"名录中文待校对: {entry.get('id')}（※），以客户端简中为准")
    template = (templates_dir / "character.html").read_text(encoding="utf-8")
    rendered = render_character(
        entry, primary_rows, secondary_rows,
        weapons_t1_rows, weapons_t2_rows, items_rows,
        data, template, warns,
    )
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
