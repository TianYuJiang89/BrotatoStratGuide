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

# #13 取材与巡检徽标:Top3 加双标注检查。
# 难度只认三档;娱乐局 (综述/花活) 永不作主候选;低于保底线永不作主引用。
ALLOWED_DIFFICULTIES: tuple[str, ...] = ("Danger 5", "Nightmare", "Ultimate")
# 娱乐/综述 markers (小写子串):标题命中即视为娱乐局, 进 Top3 即 fail。
# Tier List 综述 + Challenge/Random/Batomon 花活只作上限补充, 不作主引用。
ENTERTAINMENT_MARKERS: tuple[str, ...] = (
    "tier list",
    "tier-list",
    "challenge",
    "batomon",
    "random-random",
    "random random",
)
# 抽取只做两件 (元数据 + 自动字幕):出现以下键即重转写/画面多模态, fail。
FORBIDDEN_EXTRACTION_KEYS: tuple[str, ...] = (
    "frames",
    "multimodal",
    "full_text",
    "full-transcript",
    "manual_transcript",
)
# 版本漂移锚点 (#13):取材发布日期早于此即挂待重审 (人工触发复核)。
# 2026-09-01 早于 demo 2026-10-15/17 (干净), 晚于 2025 夹具 (待重审)。
LAST_MAJOR_UPDATE: str = "2026-09-01"
# 占位标记:值含任一即视为待补 (诚实空出, warn 不 fail)。
PLACEHOLDER_MARKERS: tuple[str, ...] = ("占位", "待补", "待写", "demo-placeholder", "TODO")

# 覆盖制 (#20 决议: A 胜出 + 动态诚实标签, #21 先改后做).
# variants 数组内每变体 covers+label, tab 由证据驱动, 旧单层键与固定三 key 废除.
DIFFICULTY_RANK: dict[str, int] = {"Danger 5": 1, "Nightmare": 2, "Ultimate": 3}


def _slugify_difficulty(value: str) -> str:
    """档位 slug 化: Danger 5->danger-5, Nightmare->nightmare, Ultimate->ultimate."""
    return str(value).strip().lower().replace(" ", "-")


def variant_id_for_covers(covers: list[str]) -> str:
    """variant-id 为 covers slug 化 (高->低排序后 join, 如 ultimate-nightmare)."""
    ranked = sorted(covers, key=lambda c: DIFFICULTY_RANK.get(str(c), 0), reverse=True)
    return "-".join(_slugify_difficulty(c) for c in ranked)


def _sorted_covers(covers: list[str]) -> list[str]:
    return sorted([str(c) for c in covers], key=lambda c: DIFFICULTY_RANK.get(c, 0), reverse=True)


def validate_variants(data: dict[str, object]) -> tuple[list[dict[str, object]], list[str]]:
    """覆盖制结构校验: variants 非空数组, 每变体 covers/label/id/10段齐全.

    返回 (sorted_variants, errors). 排序按最高难度高->低.
    """
    errors: list[str] = []
    raw = data.get("variants")
    if not isinstance(raw, list) or not raw:
        return ([], ["missing section data: variants (须为非空数组, 旧单层键废除)"])
    seen_ids: set[str] = set()
    seen_covers: set[str] = set()
    parsed: list[dict[str, object]] = []
    for idx, item in enumerate(raw):
        if not isinstance(item, dict):
            errors.append(f"missing section data: variants[{idx}] need dict")
            continue
        covers_raw = item.get("covers")
        if not isinstance(covers_raw, list) or not covers_raw:
            errors.append(f"missing section data: variants[{idx}].covers 须为非空数组")
            continue
        covers = [str(c) for c in covers_raw]
        for c in covers:
            if c not in ALLOWED_DIFFICULTIES:
                errors.append(f"取材难度只认三档即 fail: variants[{idx}].covers {c!r}")
        if _sorted_covers(covers) != covers:
            errors.append(f"variants[{idx}].covers 须高->低排序: {covers}")
        label = item.get("label")
        expected_label = " + ".join(covers)
        if label != expected_label:
            errors.append(f"variants[{idx}].label 须为全名 covers join: got {label!r}, want {expected_label!r}")
        vid = item.get("id")
        expected_id = variant_id_for_covers(covers)
        if vid != expected_id:
            errors.append(f"variants[{idx}].id 须为 covers slug 化: got {vid!r}, want {expected_id!r}")
        if isinstance(vid, str):
            if vid in seen_ids:
                errors.append(f"variants id 重复即 fail: {vid}")
            seen_ids.add(vid)
        key = "+".join(covers)
        if key in seen_covers:
            errors.append(f"variants covers 重复即 fail: {key}")
        seen_covers.add(key)
        for key2 in REQUIRED_KEYS:
            if key2 not in item:
                errors.append(f"missing section data: variants[{idx}].{key2}")
        parsed.append(item)
    # 旧单层键残留即 fail (废除).
    for legacy in REQUIRED_KEYS:
        if legacy in data:
            errors.append(f"旧单层键废除即 fail: 顶层含 {legacy} (须只用 variants 数组)")
            break

    def _variant_rank(v: dict[str, object]) -> int:
        covers_raw = v.get("covers")
        covers_list: list[object] = covers_raw if isinstance(covers_raw, list) else []
        best = 0
        for c in covers_list:
            rank = DIFFICULTY_RANK.get(str(c), 0)
            if rank > best:
                best = rank
        return best

    parsed_sorted = sorted(parsed, key=_variant_rank, reverse=True)
    return (parsed_sorted, errors)

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
WIKI_CHARACTERS_PAGE = "https://brotato.wiki.spellsandguns.com/wiki/Characters"
WIKI_STATS_PAGE = "https://brotato.wiki.spellsandguns.com/wiki/Stats"
WIKI_HOME = "https://brotato.wiki.spellsandguns.com/"
CC_BY_SA = "https://creativecommons.org/licenses/by-sa/4.0/"
VIDEO_CHANNEL = "https://www.youtube.com/@Cephalopocalypse"

# 应急开关 (#12): 平时 False 即 wiki 热链, --use-local-assets 时 src 切相对路径。
# 每个 CLI 进程内恒定, 测试只走 CLI 故无跨进程污染。
_USE_LOCAL_ASSETS = False


def local_slug(en: str) -> str:
    """应急文件名 (#12): 全小写短横线, 与名录 id 同键风格.

    Max HP→max-hp, % Reroll Price→reroll-price, SMG→smg。
    thumb URL 原样抄 wiki (含大小写与 %27 转义), 本地名只做应急相对路径。
    """
    import re

    s = str(en).lower().replace("%", "")
    s = re.sub(r"[^a-z0-9]+", "-", s).strip("-")
    return s or "unknown"


def local_icon_path(group: str, en: str) -> str:
    """应急相对路径 (#12): assets/<group>/<slug>.png, 平时不用, 切换时 src 换成它。"""
    return f"assets/{group}/{local_slug(en)}.png"


def set_use_local_assets(value: bool) -> None:
    """构建开关 (#12): --use-local-assets 一键切相对路径, 平时 False 只校验不下载。"""
    global _USE_LOCAL_ASSETS
    _USE_LOCAL_ASSETS = bool(value)


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


def abbr_for_en(en: str) -> str:
    """英文缩写 (#11): 首字母小写，空格/连字符/下划线切分。

    Beast Master→bm，One-Armed→oa，Well-Rounded→wr，Cyborg→c。
    缩写=英文首字母+slug 去分隔，与中文/英文同走 norm 子串模糊。
    """
    import re

    parts = re.split(r"[\s\-_]+", en)
    return "".join(p[0].lower() for p in parts if p)


def char_thumb(en: str, reg: dict[str, object]) -> str:
    """角色头像热链 (#11): 注册表 chars 唯一源，缺项回空由调用方占位。"""
    chars = reg.get("chars")
    if not isinstance(chars, dict):
        return ""
    entry = chars.get(en)
    if not isinstance(entry, dict):
        return ""
    thumb = entry.get("thumb")
    return thumb if isinstance(thumb, str) else ""


def validate_chars(reg: dict[str, object], roster: list[dict[str, object]]) -> list[str]:
    """头像注册表校验 (#11): 64 全量覆盖，热链 60px，否则 fail。"""
    errors: list[str] = []
    chars = reg.get("chars")
    if not isinstance(chars, dict):
        return ["wiki-cache.json chars must be a dict (头像唯一 URL 源)"]
    if len(chars) != 64:
        errors.append(f"chars must be 64, got {len(chars)} (头像覆盖 64)")
        return errors
    for r in roster:
        en = str(r.get("en", ""))
        entry = chars.get(en)
        if not isinstance(entry, dict):
            errors.append(f"registry missing avatar for char: {en}")
            continue
        thumb = entry.get("thumb")
        page = entry.get("page")
        if not isinstance(thumb, str) or WIKI_BASE not in thumb:
            errors.append(f"registry missing avatar thumb for char: {en}")
        elif "60px-" not in thumb:
            errors.append(f"registry avatar must be 60px thumbnail for char: {en}")
        if not isinstance(page, str) or WIKI_BASE not in page:
            errors.append(f"registry missing avatar page for char: {en}")
    return errors


def icon_html(thumb: object, en: str, page: object = None, local: object = None) -> str:
    """图标三件套同一渲染路径 (#12 复用, #15 武器道具共用): 有图挂热链, 无图占位。

    空壳引用只留一种: 替代文本 + 宽高 + 缩略图源 + 原文件标记 + 应急路径 +
    懒加载 + 无来源引用 + 失败移除。无图标用占位, 不挂空图。
    三处统一走同一函数: 属性主表 / 次级占位 / 武器 / 道具。
    次级本身无图标统一占位, 悬浮仍用热链 (调用方 tooltip 照常渲染)。
    应急开关: _USE_LOCAL_ASSETS 为真时 src 切相对路径, 否则 wiki 热链。
    """
    if isinstance(thumb, str) and thumb:
        file_mark = page if isinstance(page, str) and page else en
        local_path = local if isinstance(local, str) and local else ""
        src = local_path if (_USE_LOCAL_ASSETS and local_path) else thumb
        return (
            f"<img class=\"sic\" alt=\"{esc(en)}\" width=\"20\" height=\"20\" "
            f"src=\"{esc(src)}\" data-file=\"{esc(file_mark)}\" "
            f"data-local=\"{esc(local_path)}\" "
            f"loading=\"lazy\" "
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
            f"<span class=\"has-tip\" tabindex=\"0\">{entry_name_html(name_en, entry)}"
            f"{weapon_tip(name_en, entry, terms_by_en)}</span>"
        )
        thumb = entry.get("thumb")
        parts.append(f"<tr><td>{icon_html(thumb, name_en, entry.get('page'), local_icon_path('weapons', name_en))}{name_html}</td><td>{note_html}</td></tr>")
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
            f"<span class=\"has-tip\" tabindex=\"0\">{entry_name_html(name_en, entry)}"
            f"{item_tip(name_en, entry, terms_by_en)}</span>"
        )
        thumb = entry.get("thumb")
        parts.append(f"<tr><td>{icon_html(thumb, name_en, entry.get('page'), local_icon_path('items', name_en))}{name_html}</td><td>{reason_html}</td></tr>")
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


def _parse_iso_date(value: object) -> str | None:
    """严格 YYYY-MM-DD, 非法返回 None (门禁由调用方判 fail)。"""
    import re

    if not isinstance(value, str):
        return None
    if not re.fullmatch(r"\d{4}-\d{2}-\d{2}", value.strip()):
        return None
    return value.strip()


def _is_placeholder(value: object) -> bool:
    """占位/待补/待写/demo 标记即视为诚实空出 (warn, 不 fail)。"""
    if not isinstance(value, str) or not value.strip():
        return True
    lowered = value.strip().lower()
    return any(m in str(value) or m.lower() in lowered for m in PLACEHOLDER_MARKERS)


def _is_guide_title(title: object) -> bool:
    """有 Guide 后缀才算教学局, 否则注明实况复盘非教学局。"""
    return isinstance(title, str) and "guide" in title.lower()


def _has_entertainment(title: object) -> str | None:
    """标题命中娱乐/综述 marker 即返回命中词, 否则 None。"""
    if not isinstance(title, str):
        return None
    lowered = title.lower()
    for marker in ENTERTAINMENT_MARKERS:
        if marker in lowered:
            return marker
    return None


def _is_youtube_url(url: object) -> bool:
    return isinstance(url, str) and (
        url.startswith("https://www.youtube.com/")
        or url.startswith("https://youtube.com/")
        or url.startswith("https://youtu.be/")
    )


def _is_allowed_difficulty(value: object) -> bool:
    """覆盖制难度校验: 单档或合讲合并标签 (Ultimate + Nightmare) 均可, 每部分须在三档内."""
    if not isinstance(value, str):
        return False
    parts = [p.strip() for p in value.split("+")]
    if not parts:
        return False
    return all(p in ALLOWED_DIFFICULTIES for p in parts)


def check_source(source: object) -> tuple[list[str], list[str]]:
    """#13 取材门禁 (fail) + 验收线 (warn)。

    FAIL (门禁错即 fail, 烂页发不出去):
    - candidates > 3 (1 主 + 不超 2 补充)
    - 主/候选难度不在三档 (Danger 5/Nightmare/Ultimate)
    - 主/候选标题命中娱乐局 (Tier List/Challenge/Random/Batomon)
    - 主/候选缺链接 (非 YouTube) / 缺 video_id / 日期非法
    - 主候选不一致 (candidates 非空时 candidates[0] 须等于主五元组)
    - 抽取含 frames/multimodal 等重转写键
    WARN (缺项 warn 加徽标可发布):
    - candidates 空 (零命中诚实空缺待补)
    - 无字幕/未纠专名 (降级或待补, 不猜测)
    - 双标注缺项 (发布日期/游戏版本缺一)
    - 旧日期 (早于 LAST_MAJOR_UPDATE 即待重审)
    - resource_review 真 (资源待重审)
    """
    errors: list[str] = []
    warns: list[str] = []
    if not isinstance(source, dict):
        # 缺 source 键由结构机检报 fail, 此处仅验收 warn (双保险不重复 fail)。
        return (errors, ["acceptance: 取材版本缺项"])
    title = source.get("title")
    url = source.get("url")
    video_id = source.get("video_id")
    published = source.get("published")
    difficulty = source.get("difficulty")
    game_version = source.get("game_version")
    # --- 门禁:主引用 (覆盖制: 单档或合讲合并标签) ---
    if not _is_allowed_difficulty(difficulty):
        # 诚实空缺 (待补标题 + 占位 id) 允许 warn, 不 fail;其余非法难度 fail。
        honest_empty = _is_placeholder(video_id) or (isinstance(title, str) and "暂无可用主引用" in title)
        if not honest_empty:
            errors.append(f"取材难度只认三档即 fail: {difficulty!r} (须 Danger 5/Nightmare/Ultimate)")
    hit = _has_entertainment(title)
    if hit:
        errors.append(f"娱乐局永不作主引用即 fail: 标题命中 {hit!r}")
    if not _is_youtube_url(url):
        # 诚实空缺允许频道页占位, 其余非 YouTube 链接 fail。
        honest_channel = isinstance(url, str) and url.startswith("https://www.youtube.com/@")
        if not honest_channel:
            errors.append(f"取材链接错即 fail: {url!r} (须 YouTube watch/频道)")
    if not isinstance(video_id, str) or not video_id.strip():
        errors.append("取材 video_id 缺失即 fail")
    if _parse_iso_date(published) is None:
        # 非法日期为门禁错;但纯占位空值走验收 warn (与旧 check_acceptance 一致)。
        if isinstance(published, str) and published.strip() and not _is_placeholder(published):
            errors.append(f"取材发布日期非法即 fail: {published!r} (须 YYYY-MM-DD)")
    # --- 门禁:Top3 ---
    candidates = source.get("candidates")
    if candidates is None:
        # 旧数据无 candidates:走单主引用路径, 仅验收 warn (向后兼容 demo)。
        pass
    elif not isinstance(candidates, list):
        errors.append("取材 candidates 须为数组即 fail")
    else:
        if len(candidates) > 3:
            errors.append(f"取材 Top3 即 fail: 1 主 + 不超 2 补充, got {len(candidates)}")
        for idx, cand in enumerate(candidates):
            if not isinstance(cand, dict):
                errors.append(f"取材候选结构错即 fail: candidates[{idx}] need dict")
                continue
            c_title = cand.get("title")
            c_url = cand.get("url")
            c_vid = cand.get("video_id")
            c_pub = cand.get("published")
            c_diff = cand.get("difficulty")
            if not _is_allowed_difficulty(c_diff):
                errors.append(f"取材候选难度只认三档即 fail: candidates[{idx}] {c_diff!r}")
            c_hit = _has_entertainment(c_title)
            if c_hit:
                errors.append(f"娱乐局不进候选即 fail: candidates[{idx}] 命中 {c_hit!r}")
            if not _is_youtube_url(c_url):
                errors.append(f"取材候选链接错即 fail: candidates[{idx}] {c_url!r}")
            if not isinstance(c_vid, str) or not c_vid.strip():
                errors.append(f"取材候选 video_id 缺失即 fail: candidates[{idx}]")
            if _parse_iso_date(c_pub) is None:
                errors.append(f"取材候选日期非法即 fail: candidates[{idx}] {c_pub!r}")
            for field in ("title", "url", "video_id", "published", "difficulty"):
                if cand.get(field) is None:
                    errors.append(f"取材候选缺 {field} 即 fail: candidates[{idx}]")
        # 主候选一致:非空时 candidates[0] 五元组须等于主。
        if candidates and isinstance(candidates[0], dict):
            top = candidates[0]
            for field in ("title", "url", "video_id", "published", "difficulty"):
                if top.get(field) != source.get(field):
                    errors.append(f"取材主候选不一致即 fail: {field} 主 != candidates[0]")
                    break
    # --- 门禁:抽取只做两件 ---
    transcript = source.get("transcript")
    if isinstance(transcript, dict):
        for key in FORBIDDEN_EXTRACTION_KEYS:
            if key in transcript:
                errors.append(f"禁重转写画面多模态即 fail: transcript 含 {key!r}")
                break
    if errors:
        return (errors, warns)
    # --- 验收线 (warn 加徽标, 可发布) ---
    if isinstance(candidates, list) and len(candidates) == 0:
        warns.append("acceptance: Top3 零命中诚实空缺待补 (不降级引用娱乐局)")
    # 字幕有无:主 has_captions + transcript.captions 双看, 缺一即降级/待补。
    has_caps = source.get("has_captions")
    caps_status: object = transcript.get("captions") if isinstance(transcript, dict) else None
    if has_caps is not True or caps_status in (None, "none", "missing", False):
        # 旧 demo 无 transcript:同样 warn (与待补口径一致)。
        if has_caps is not True or caps_status != "auto":
            warns.append("acceptance: 无字幕降级/待补 (抽取仅元数据 + 自动字幕, 不猜测)")
    if isinstance(transcript, dict) and transcript.get("corrected") is not True:
        warns.append("acceptance: 专名未对照纠正待补 (须对照 Wiki 纠拼写)")
    elif not isinstance(transcript, dict):
        warns.append("acceptance: 抽取两件缺转写标注待补 (元数据 + 自动字幕 + 纠专名)")
    # 双标注:发布日期 + 游戏版本齐全, 占位即待补。
    if _is_placeholder(published) or _is_placeholder(game_version):
        warns.append("acceptance: 双标注缺项待补 (发布日期 + 游戏版本须齐全)")
    # 旧日期:早于大更新即待重审。
    parsed = _parse_iso_date(published)
    if parsed is not None and parsed < LAST_MAJOR_UPDATE:
        warns.append(f"acceptance: 取材日期 {parsed} 早于大更新 {LAST_MAJOR_UPDATE}, 命中待重审")
    # 资源 flag:人工触发 HEAD 失效后置 flag, 渲染资源待重审。
    if source.get("resource_review") is True:
        warns.append("acceptance: 资源失效命中资源待重审")
    return (errors, warns)


def source_badges(source: dict[str, object], warns: list[str]) -> str:
    """取材徽标 (#13):缺项待补 + 旧日期待重审 + 资源待重审。"""
    badges = ""
    needs_pending = any(
        kw in w for w in warns for kw in ("待补", "无字幕", "双标注", "零命中", "转写", "纠")
    )
    if needs_pending:
        badges += ' <span class="badge-pending">待补口径</span>'
    if any("待重审" in w and "资源" not in w for w in warns):
        badges += ' <span class="badge-recheck">待重审</span>'
    if isinstance(source.get("resource_review"), bool) and source.get("resource_review") is True:
        badges += ' <span class="badge-resource">资源待重审</span>'
    elif any("资源待重审" in w for w in warns):
        badges += ' <span class="badge-resource">资源待重审</span>'
    return badges


def candidate_row_html(cand: dict[str, object], label: str) -> str:
    """单候选行:标题链接 + 标识 + 日期 + 难度 + 字幕有无 + 教学局/实况。"""
    title = str(cand.get("title", "待补"))
    url = str(cand.get("url", "#"))
    video_id = str(cand.get("video_id", "待补"))
    published = str(cand.get("published", "待补"))
    difficulty = str(cand.get("difficulty", "待补"))
    has_caps = cand.get("has_captions")
    caps_text = "有自动字幕" if has_caps is True else "无字幕降级/待补"
    kind = "教学局" if _is_guide_title(title) else "实况复盘非教学局"
    return (
        f"<li data-candidate=\"{esc(label)}\">"
        f"{esc(label)}：<a href=\"{esc(url)}\">{esc(title)}</a> "
        f"<code>{esc(video_id)}</code> / 发布：{esc(published)} / 难度：{esc(difficulty)} / "
        f"{esc(caps_text)} / {esc(kind)}</li>"
    )


def source_block(source: dict[str, object]) -> str:
    title = esc(source.get("title", "待补"))
    video_id = esc(source.get("video_id", "待补"))
    published = esc(source.get("published", "待补"))
    difficulty = esc(source.get("difficulty", "待补"))
    game_version = esc(source.get("game_version", "待补"))
    if not isinstance(source.get("url"), str) or not source.get("url"):
        url_display = '<span class="empty">作者未提及</span>'
    else:
        raw_url = str(source.get("url"))
        url_display = f'<a href="{esc(raw_url)}">{title}</a>'
    # 主引用标注:教学局 vs 实况 + 字幕有无 + 双标注。
    main_kind = "教学局" if _is_guide_title(source.get("title")) else "实况复盘非教学局"
    main_caps = source.get("has_captions")
    main_caps_text = "有自动字幕" if main_caps is True else "无字幕降级/待补"
    candidates = source.get("candidates")
    if isinstance(candidates, list) and len(candidates) == 0:
        top_html = "<p>暂无可用主引用 — 待补口径，不编造娱乐局。</p>"
    elif isinstance(candidates, list) and candidates:
        items: list[str] = []
        for idx, cand in enumerate(candidates):
            if not isinstance(cand, dict):
                continue
            label = "主引用" if idx == 0 else f"补充{idx}"
            items.append(candidate_row_html(cand, label))
        top_html = f"<p>主取材：{url_display}</p><ul>{''.join(items)}</ul>"
    else:
        top_html = f"<p>主取材：{url_display}</p>"
    # 徽标:基于 warns 计算, source_block 无 warns 上下文时按数据直算。
    _, _warns = check_source(source)
    badges = source_badges(source if isinstance(source, dict) else {}, _warns)
    # 抽取说明:只做两件 + 纠专名状态。
    transcript = source.get("transcript") if isinstance(source, dict) else None
    if isinstance(transcript, dict) and transcript.get("captions") == "auto" \
            and transcript.get("corrected") is True:
        extract_line = "<p>抽取仅元数据 + 自动字幕，已对照 Wiki 纠专名；转述非搬运，只留可复现骨架。</p>"
    else:
        extract_line = "<p>抽取待补：仅元数据 + 自动字幕并对照纠专名，无字幕降级/待补，不猜测。</p>"
    return (
        f"{top_html}"
        f"<p>视频 ID：<code>{video_id}</code> / 发布：{published} / 难度：{difficulty} / "
        f"{esc(main_caps_text)} / {esc(main_kind)}{badges}</p>"
        f"<p>适用版本：{game_version}（发布日期 + 游戏版本双标注）</p>"
        f"{extract_line}"
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
    page = reg_entry.get("page") if isinstance(reg_entry, dict) else None
    if page is None and isinstance(reg_entry, dict):
        page = reg_entry.get("file")
    icon = icon_html(thumb, en, page, local_icon_path("stats", en))
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
    """结构机检: 覆盖制 variants 数组, 每变体 10 段齐全, 旧单层键废除."""
    variants, errors = validate_variants(data)
    if errors:
        return errors
    for idx, variant in enumerate(variants):
        phases = variant.get("phases")
        if not isinstance(phases, list) or len(phases) != 3:  # noqa: PLR2004
            errors.append("missing section data: " f"variants[{idx}].phases (need exactly 3: W1-5/W6-12/W13-20)")
        ratings = variant.get("ratings")
        if not isinstance(ratings, dict):
            errors.append(f"missing section data: variants[{idx}].ratings (need dict en->rating/note)")
    return errors


def check_acceptance_one(variant: dict[str, object]) -> list[str]:
    """单变体验收线机检: 缺项只 warn, 不 fail."""
    warns: list[str] = []
    mechanism = variant.get("mechanism")
    if not isinstance(mechanism, str) or not mechanism.strip():
        warns.append("acceptance: 机制一句话缺项")
    ratings = variant.get("ratings")
    found_sa = False
    if isinstance(ratings, dict):
        for v in ratings.values():
            if isinstance(v, dict) and v.get("rating") in ("S", "A"):
                found_sa = True
                break
    if not found_sa:
        warns.append("acceptance: 属性 S/A 无口径")
    weapons_t1 = variant.get("weapons_t1")
    if not isinstance(weapons_t1, list) or len(weapons_t1) < 1:
        warns.append("acceptance: 武器 T1 至少 1 把缺项")
    items = variant.get("items")
    if not isinstance(items, list) or len(items) < 3:  # noqa: PLR2004
        warns.append("acceptance: 关键道具至少 3 件缺项")
    phases = variant.get("phases")
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
        value = variant.get(key)
        if not isinstance(value, str) or not value.strip():
            warns.append(f"acceptance: {key} Top3 缺项")
    source = variant.get("source")
    if not isinstance(source, dict):
        warns.append("acceptance: 取材版本缺项")
    else:
        # #13:双标注/字幕/Top3 验收线由 check_source 统一判 warn。
        _, source_warns = check_source(source)
        warns.extend(source_warns)
        # 旧字段缺项仍直报 (向后兼容, 与 source_warns 去重由调用方合并)。
        for field in ("url", "video_id", "published", "difficulty", "game_version"):
            value = source.get(field)
            if not isinstance(value, str) or not value.strip():
                legacy = f"acceptance: 取材 {field} 缺项"
                if legacy not in warns:
                    warns.append(legacy)
                break
    return warns


def check_acceptance(data: dict[str, object]) -> list[str]:
    """覆盖线机检: 每变体验收线汇总, 缺项只 warn, 不 fail."""
    variants, errors = validate_variants(data)
    if errors:
        return []
    warns: list[str] = []
    for variant in variants:
        vid = str(variant.get("id", "?"))
        for w in check_acceptance_one(variant):
            warns.append(f"[{vid}] {w}" if w.startswith("acceptance:") else w)
    return warns


def check_structure_html(html_text: str) -> list[str]:
    """产物结构机检: 每变体 11 个 data-section 齐全且顺序正确, 否则 fail (覆盖制)."""
    import re

    found = re.findall(r'data-section="([^"]+)"', html_text)
    if not found:
        return [f"section order mismatch: expected {SECTION_ORDER}, got {found}"]
    if len(found) % len(SECTION_ORDER) != 0:
        return [f"section order mismatch: expected N x {SECTION_ORDER}, got {found}"]
    for i in range(0, len(found), len(SECTION_ORDER)):
        chunk = found[i:i + len(SECTION_ORDER)]
        if chunk != SECTION_ORDER:
            return [f"section order mismatch: expected {SECTION_ORDER}, got {chunk} (variant block {i // len(SECTION_ORDER)})",]
    return []


def footer_html(source: dict[str, object]) -> str:
    """页脚固定署名行 (#12 构建注入, 不手写).

    图标 © Blobfish + wiki 来源 + 文本许可链 + 原页链 (Characters/Stats) +
    机制译自 Wiki 与视频双链 + 转述非搬运 (不搬截图原片)。
    """
    video_url = source.get("url") if isinstance(source, dict) else None
    if isinstance(video_url, str) and video_url.startswith("http"):
        video_link = f'<a href="{esc(video_url)}">取材视频</a>'
    else:
        video_link = "取材视频待补"
    return (
        f"<p>图标 © Blobfish, via "
        f"<a href=\"{WIKI_HOME}\">Brotato Wiki</a>"
        f"低分辨率缩略图热链展示 (游戏资产原权保留, 文本 "
        f"<a href=\"{CC_BY_SA}\">CC BY-SA 4.0</a>) · "
        f"断网回落占位仍可读 · 未自托管分发高清 · "
        f"<a href=\"{WIKI_CHARACTERS_PAGE}\">原页: Characters</a> · "
        f"<a href=\"{WIKI_STATS_PAGE}\">原页: Stats</a></p>"
        f"<p>机制译自 Wiki 与视频双链: {video_link} · "
        f"<a href=\"{WIKI_STATS_PAGE}\">Wiki: Stats</a> · "
        f"<a href=\"{VIDEO_CHANNEL}\">视频来源站</a> · "
        f"转述非搬运, 不搬截图原片</p>"
        f"<p>构建产物, 人不手改, 只改源码重构建。</p>"
    )


def _variant_section_html(vid: str, section: str, title: str, inner: str) -> str:
    """单变体单段卡片: id 按变体后缀, data-section+data-variant 双标."""
    sec_id = f"s-{section}-{vid}"
    return (
        f'<section class="card" id="{esc(sec_id)}" '
        f'data-section="{esc(section)}" data-variant="{esc(vid)}">'
        f"<h2>{title}</h2>{inner}</section>"
    )


def build_variant_panel(
    variant: dict[str, object],
    terms: list[dict[str, str]],
    reg: dict[str, object],
    terms_by_en: dict[str, dict[str, str]],
    items_map: dict[str, object],
    weapons_map: dict[str, object],
) -> tuple[str, list[str], list[str]]:
    """单变体 11 段面板 inner. 返回 (html, errors, warns)."""
    vid = str(variant.get("id", ""))
    ratings_raw = variant.get("ratings")
    ratings: dict[str, object] = ratings_raw if isinstance(ratings_raw, dict) else {}
    primary_rows, secondary_rows, term_errors, term_warns = build_term_tables(terms, ratings, reg)
    if term_errors:
        return ("", term_errors, [])
    w1_raw = variant.get("weapons_t1")
    w2_raw = variant.get("weapons_t2")
    items_raw = variant.get("items")
    w1_rows, w1_errors, w1_warns = weapon_rows(
        w1_raw if isinstance(w1_raw, list) else [], weapons_map, terms_by_en
    )
    w2_rows, w2_errors, w2_warns = weapon_rows(
        w2_raw if isinstance(w2_raw, list) else [], weapons_map, terms_by_en
    )
    items_rows, item_errors, item_warns = item_rows(
        items_raw if isinstance(items_raw, list) else [], items_map, terms_by_en
    )
    gear_errors = w1_errors + w2_errors + item_errors
    if gear_errors:
        return ("", gear_errors, [])
    mechanism = variant.get("mechanism")
    mechanism_html = (
        esc(mechanism)
        if isinstance(mechanism, str) and mechanism.strip()
        else '<span class="empty">作者未提及 — 待补口径</span>'
    )
    upgrade = variant.get("upgrade")
    upgrade_html = (
        esc(upgrade)
        if isinstance(upgrade, str) and upgrade.strip()
        else '<span class="empty">作者未提及 — 待补口径</span>'
    )
    shop = variant.get("shop")
    shop_html = (
        esc(shop)
        if isinstance(shop, str) and shop.strip()
        else '<span class="empty">作者未提及 — 待补口径</span>'
    )
    hard = variant.get("hard")
    hard_html = (
        esc(hard)
        if isinstance(hard, str) and hard.strip()
        else '<span class="empty">作者未提及 — 待补口径</span>'
    )
    pitfalls = variant.get("pitfalls")
    if isinstance(pitfalls, list) and pitfalls:
        pitfalls_html = "".join(
            f"<li>{esc(p) if isinstance(p, str) and p.strip() else '<span class=\"empty\">作者未提及</span>'}</li>"
            for p in pitfalls
        )
    else:
        pitfalls_html = '<li><span class="empty">作者未提及 — 待补口径</span></li>'
    phases = variant.get("phases")
    source = variant.get("source")
    legend_primary = (
        '<p class="legend">图例：<span class="rating rating-S">S</span>'
        '<span class="rating rating-A">A</span><span class="rating rating-B">B</span>'
        '<span class="rating rating-C">C</span><span class="rating rating-D">D</span>'
        '<span class="rating rating-F">F</span><span class="rating rating-none">— 未提及</span>'
        ' · 评级只认视频作者口径，未提诚实空出 · 排序图标随 wiki Stats 原序 · '
        '<span class="badge-dlc">DLC</span>=深渊魔物专属 · ※=中文待客户端简中校对</p>'
    )
    legend_secondary = (
        '<p class="legend">次级 22 全量随 wiki 次级表原序（消耗品治疗到重随价格）'
        ' · wiki 本无专用图标统一 ◆ 占位 · 悬浮为 wiki Notable Items 热链 · ※待校对只 warn 加标</p>'
    )
    parts = [
        _variant_section_html(vid, "mechanism", "机制一句话", f"<p>{mechanism_html}</p>"),
        _variant_section_html(vid, "attrs-primary", "核心属性·主表",
            f"{legend_primary}<div class=\"table-wrap\"><table>"
            f"<tr><th>属性</th><th>评级</th><th>怎么看</th></tr>{primary_rows}</table></div>"),
        _variant_section_html(vid, "attrs-secondary", "核心属性·次级表",
            f"{legend_secondary}<div class=\"table-wrap\"><table>"
            f"<tr><th>属性</th><th>评级</th><th>怎么看</th></tr>{secondary_rows}</table></div>"),
        _variant_section_html(vid, "weapons", "武器分档",
            f"<h3>T1 主选</h3><div class=\"table-wrap gear-wrap\"><table>"
            f"<tr><th>武器</th><th>为什么 / 何时拿换</th></tr>{w1_rows}</table></div>"
            f"<h3>T2 备选过渡</h3><div class=\"table-wrap gear-wrap\"><table>"
            f"<tr><th>武器</th><th>为什么 / 何时拿换</th></tr>{w2_rows}</table></div>"),
        _variant_section_html(vid, "items", "关键道具",
            f"<div class=\"table-wrap gear-wrap\"><table>"
            f"<tr><th>道具</th><th>推荐理由</th></tr>{items_rows}</table></div>"),
        _variant_section_html(vid, "phases", "开局 / 中期 / 后期",
            phases_block(phases if isinstance(phases, list) else [])),
        _variant_section_html(vid, "upgrade", "升级优先级", f"<p>{upgrade_html}</p>"),
        _variant_section_html(vid, "shop", "商店优先级", f"<p>{shop_html}</p>"),
        _variant_section_html(vid, "pitfalls", "避坑", f"<ul>{pitfalls_html}</ul>"),
        _variant_section_html(vid, "hard", "高难特例", f"<p>{hard_html}</p>"),
        _variant_section_html(vid, "source", "取材与版本",
            source_block(source if isinstance(source, dict) else {})),
    ]
    warns = term_warns + w1_warns + w2_warns + item_warns
    return ("".join(parts), [], warns)


def toc_html(first_vid: str) -> str:
    """全局目录: 锚点指向首变体 (最高难度) 后缀 id, 无 JS 仍可读."""
    items = [
        ("mechanism", "机制一句话"),
        ("attrs-primary", "核心属性·主表"),
        ("attrs-secondary", "核心属性·次级表"),
        ("weapons", "武器分档"),
        ("items", "关键道具"),
        ("phases", "开局/中期/后期"),
        ("upgrade", "升级优先级"),
        ("shop", "商店优先级"),
        ("pitfalls", "避坑"),
        ("hard", "高难特例"),
        ("source", "取材与版本"),
    ]
    links = "".join(
        f'<a href="#s-{sec}-{esc(first_vid)}">{title}</a>' for sec, title in items
    )
    return f'<nav class="toc" aria-label="目录">{links}</nav>'


def variants_block_html(sorted_variants: list[dict[str, object]], panels: list[str]) -> tuple[str, str]:
    """覆盖制 tab 区: 单变体徽章 vs 多变体 tablist+panels. 返回 (tabs, panels_html)."""
    if len(sorted_variants) == 1:
        v = sorted_variants[0]
        label = str(v.get("label", ""))
        vid = str(v.get("id", ""))
        tabs = f'<span class="coverbadge">覆盖：{esc(label)}（单变体，无 tab 栏）</span>'
        body = (
            f'<div id="panel-{esc(vid)}" role="tabpanel" aria-live="polite" tabindex="0" '
            f'data-variant="{esc(vid)}" data-variant-label="{esc(label)}">{panels[0]}</div>'
        )
        return (tabs, body)
    btns: list[str] = []
    wrapped: list[str] = []
    for idx, v in enumerate(sorted_variants):
        label = str(v.get("label", ""))
        vid = str(v.get("id", ""))
        sel = "true" if idx == 0 else "false"
        tab = "0" if idx == 0 else "-1"
        btns.append(
            f'<button role="tab" id="tab-{esc(vid)}" aria-controls="panel-{esc(vid)}" '
            f'aria-selected="{sel}" tabindex="{tab}" data-d="{esc(label)}">{esc(label)}</button>'
        )
        hidden = "" if idx == 0 else ' hidden=""'
        wrapped.append(
            f'<div id="panel-{esc(vid)}" role="tabpanel" aria-labelledby="tab-{esc(vid)}" '
            f'tabindex="0" data-variant="{esc(vid)}" data-variant-label="{esc(label)}"{hidden}>'
            f"{panels[idx]}</div>"
        )
    tabs_html = f'<div class="seg" role="tablist" aria-label="难度覆盖（动态）">{"".join(btns)}</div>'
    return (tabs_html, "".join(wrapped))


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
    """兼容旧签名的覆盖制渲染: 旧行参忽略, 按 variants 重算每变体面板."""
    # 旧单层占位已废除, 此处仅为兼容旧调用保留签名, 实际按 variants 渲染.
    # 真实 per-variant 行在 build_slug 内已算好并经此函数组装 (见下).
    # 为保持 E2E seam 稳定, 本函数在 variants 模式下直接走新路径.
    raise NotImplementedError("render_character 旧签名已废除, 请用 render_character_variants")


def render_character_variants(
    roster_entry: dict[str, object],
    sorted_variants: list[dict[str, object]],
    panels: list[str],
    template: str,
    warns: list[str],
    footer_source: dict[str, object],
) -> str:
    zh = esc(roster_entry.get("zh", ""))
    en = esc(roster_entry.get("en", ""))
    pending = ' <span class="badge-pending">待补口径</span>' if warns else ""
    first_vid = str(sorted_variants[0].get("id", "")) if sorted_variants else ""
    tabs_html, panels_html = variants_block_html(sorted_variants, panels)
    replacements: dict[str, str] = {
        "{{PAGE_TITLE}}": f"{roster_entry.get('zh', '')} ({roster_entry.get('en', '')}) · 土豆兄弟攻略",
        "{{ZH}}": zh,
        "{{EN}}": en,
        "{{PENDING_BADGE}}": pending,
        "{{TOC}}": toc_html(first_vid),
        "{{VARIANT_TABS}}": tabs_html,
        "{{VARIANT_PANELS}}": panels_html,
        "{{FOOTER}}": footer_html(footer_source),
    }
    out = template
    for token, value in replacements.items():
        out = out.replace(token, value)
    return out


def index_card_html(
    slug: str,
    zh: str,
    en: str,
    dlc: object,
    thumb: str,
    playable: bool,
) -> str:
    """索引单卡 (#11): 头像热链+🥔占位回落，可点才有链，不点进空页。"""
    dlc_label = "Abyssal Terrors DLC" if dlc == "abyssal" else "本体"
    dlc_attr = "abyssal" if dlc == "abyssal" else ""
    playable_attr = "1" if playable else "0"
    if thumb:
        ava = (
            '<div class="ava"><span>🥔</span>'
            f'<img loading="lazy" alt="{esc(en)}" src="{esc(thumb)}" '
            'referrerpolicy="no-referrer" onerror="this.remove()">'
            "</div>"
        )
    else:
        ava = '<div class="ava"><span>🥔</span></div>'
    if playable:
        return (
            f'<div class="card" data-slug="{esc(slug)}" '
            f'data-dlc="{dlc_attr}" data-playable="{playable_attr}">'
            f"{ava}"
            f'<div class="nm">{esc(zh)} ({esc(en)})<small>{dlc_label} · 可点</small></div>'
            '<div class="right"><span class="tag ok">● 可点</span>'
            f'<div class="links"><a href="./{esc(slug)}.html">看攻略</a></div>'
            "</div></div>"
        )
    return (
        f'<div class="card" data-slug="{esc(slug)}" '
        f'data-dlc="{dlc_attr}" data-playable="{playable_attr}">'
        f"{ava}"
        f'<div class="nm">{esc(zh)} ({esc(en)})<small>{dlc_label} · 待填充</small></div>'
        '<div class="right"><span class="tag">待填充</span></div></div>'
    )


def render_index(
    roster: list[dict[str, object]],
    built_slugs: set[str],
    template: str,
    reg: dict[str, object] | None = None,
) -> str:
    """索引全能力 (#11): 搜索+筛选+仅看可点覆盖 64，计数+空状态，头像热链+占位。

    file 双击可跑：ROSTER 内联，无 fetch；首屏服务端直出 64 卡，无 JS 仍可读。
    搜索 norm：小写去空格/连字符/下划线子串，覆盖中文/英文/slug 去分隔/英文首字母缩写。
    """
    reg_map: dict[str, object] = reg if isinstance(reg, dict) else {}
    roster_json: list[dict[str, object]] = []
    parts: list[str] = []
    for entry in roster:
        slug = str(entry.get("id", ""))
        zh = str(entry.get("zh", ""))
        en = str(entry.get("en", ""))
        dlc = entry.get("dlc")
        thumb = char_thumb(en, reg_map) if reg_map else ""
        playable = slug in built_slugs
        roster_json.append(
            {
                "slug": slug,
                "zh": zh,
                "en": en,
                "dlc": dlc,
                "img": thumb,
                "playable": playable,
                "abbr": abbr_for_en(en),
            }
        )
        parts.append(index_card_html(slug, zh, en, dlc, thumb, playable))
    count_line = f"共 {len(roster)} 个角色，当前可点 {len(built_slugs)} 个，当前命中 {len(roster)} 个"
    out = template.replace("{{INDEX_ITEMS}}", "".join(parts))
    out = out.replace("{{INDEX_COUNT}}", esc(count_line))
    # ROSTER 内联 JSON：ensure_ascii=False 保中文可读，</ 转义防闭合 script。
    raw_json = json.dumps(roster_json, ensure_ascii=False)
    safe_json = raw_json.replace("</", "<\\/")
    return out.replace("{{ROSTER_JSON}}", safe_json)


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
    char_errors = validate_chars(reg, roster)
    if char_errors:
        return (char_errors, [])
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
    sorted_variants, _ = validate_variants(data)
    terms_by_en: dict[str, dict[str, str]] = {t["en"]: t for t in terms}
    reg_items = reg.get("items")
    reg_weapons = reg.get("weapons")
    items_map: dict[str, object] = reg_items if isinstance(reg_items, dict) else {}
    weapons_map: dict[str, object] = reg_weapons if isinstance(reg_weapons, dict) else {}
    panels: list[str] = []
    warns: list[str] = []
    for variant in sorted_variants:
        panel, p_errors, p_warns = build_variant_panel(
            variant, terms, reg, terms_by_en, items_map, weapons_map
        )
        if p_errors:
            return (p_errors, [])
        # #13 取材门禁每变体独立: 难度/娱乐/链接/Top3/抽取错即 fail.
        raw_source = variant.get("source")
        src_errors, _src_warns = check_source(raw_source)
        if src_errors:
            vid = str(variant.get("id", "?"))
            return ([f"[{vid}] {e}" for e in src_errors], _src_warns)
        warns.extend(p_warns)
        panels.append(panel)
    warns.extend(check_acceptance(data))
    # 名录待校对只 warn。
    if str(entry.get("needs_review", "")).upper() == "TRUE" or entry.get("needs_review") is True:
        warns.append(f"名录中文待校对: {entry.get('id')}（※），以客户端简中为准")
    template = (templates_dir / "character.html").read_text(encoding="utf-8")
    footer_src_raw = sorted_variants[0].get("source") if sorted_variants else {}
    footer_src: dict[str, object] = footer_src_raw if isinstance(footer_src_raw, dict) else {}
    rendered = render_character_variants(entry, sorted_variants, panels, template, warns, footer_src)
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
) -> list[str]:
    """构建索引页 (#11 全能力)。返回 errors，空即成功。"""
    try:
        roster = load_roster(data_dir)
    except Exception as exc:
        return [f"roster load fail: {exc}"]
    roster_errors = validate_roster(roster)
    if roster_errors:
        return roster_errors
    try:
        reg = load_registry(data_dir)
    except Exception as exc:
        return [f"registry load fail: {exc}"]
    # 索引头像单源：chars 缺项即 fail，不带图发不出去。
    char_errors = validate_chars(reg, roster)
    if char_errors:
        return char_errors
    built = {
        p.stem
        for p in (data_dir / "builds").glob("*.json")
        if (p.stem in {str(r.get("id")) for r in roster})
    }
    template = (templates_dir / "index.html").read_text(encoding="utf-8")
    if "{{ROSTER_JSON}}" not in template:
        return ["index template missing {{ROSTER_JSON}} (全能力需内联 ROSTER)"]
    rendered = render_index(roster, built, template, reg)
    out_dir.mkdir(parents=True, exist_ok=True)
    (out_dir / "index.html").write_text(rendered, encoding="utf-8")
    return []


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="构建单角色页与索引页 (#10 单源)")
    group = parser.add_mutually_exclusive_group(required=True)
    group.add_argument("--slug", help="按角色构建, 如 --slug cyborg")
    group.add_argument("--all", action="store_true", help="全量构建")
    parser.add_argument("--data-dir", default="data")
    parser.add_argument("--templates-dir", default="templates")
    parser.add_argument("--out-dir", default="docs")
    parser.add_argument("--use-local-assets", action="store_true",
                        help="应急自托管: 图标 src 切 assets/ 相对路径 (平时不用, 只校验不下载)")
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
    set_use_local_assets(args.use_local_assets)

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
        index_errors = build_index(data_dir, templates_dir, out_dir)
        if index_errors:
            for err in index_errors:
                print(f"FAIL: {err}", file=sys.stderr)
            return 1
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
    index_errors = build_index(data_dir, templates_dir, out_dir)
    if index_errors:
        for err in index_errors:
            print(f"FAIL: {err}", file=sys.stderr)
        failed = True
    print(f"built --all -> {out_dir}")
    return 1 if failed else 0


if __name__ == "__main__":
    raise SystemExit(main())
