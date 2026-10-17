"""交叉表构建器 (#17): 字幕x术语命中表机器 gate.

扫描 `data/subs/<slug>.en-orig.vtt` (自动字幕, 仅取证) x 39 术语 + 注册表武器/道具名,
逐个命中计数并附原句, 输出 `data/mentions/<slug>.json` (本单定).

格式 (本单定):
{
  "slug": "<slug>",
  "vtt": "data/subs/<slug>.en-orig.vtt",
  "video_id": "<from builds source.video_id if present>",
  "generated_by": "scripts/build_mentions.py",
  "terms": {"Speed": {"count": 1, "quotes": ["原句..."]}, ... 39 全量},
  "weapons": {"Wrench": {"count": 1, "quotes": [...]}, ...},
  "items": {"Turret": {...}, ...}
}

用法:
  python scripts/build_mentions.py --slug engineer
  python scripts/build_mentions.py --all
  --data-dir / --subs-dir / --mentions-dir 供测试隔离 (默认 data/ data/subs/ data/mentions/).

匹配注意 (#14 回归):
- Speed 只认移动速度, `attack speed` 不得污染 (负向前瞻排除 attack/structure/enemy/burning).
- Engineering 只认 `engineering`, 不认角色名 `engineer`.
- Range 用词边界, 不吞 `ranged`.
- 宁可多 warn 不可漏: 通用词 (damage/speed/range) 按词边界计, 复合提及双计.
"""

from __future__ import annotations

import argparse
import csv
import json
import re
import sys
from pathlib import Path


def load_terms(data_dir: Path) -> list[str]:
    path = data_dir / "terms.csv"
    with path.open(encoding="utf-8") as f:
        rows = list(csv.DictReader(f))
    return [str(r.get("en", "")).strip() for r in rows if r.get("en")]


def load_registry_names(data_dir: Path) -> tuple[list[str], list[str]]:
    path = data_dir / "wiki-cache.json"
    reg = json.loads(path.read_text(encoding="utf-8"))
    weapons: list[str] = []
    items: list[str] = []
    if isinstance(reg, dict):
        w = reg.get("weapons")
        if isinstance(w, dict):
            weapons = sorted(str(k) for k in w.keys())
        it = reg.get("items")
        if isinstance(it, dict):
            items = sorted(str(k) for k in it.keys())
    return (weapons, items)


def _wordnames_to_pattern(name: str) -> str:
    """注册表名兜底 pattern: 空格转 \\s+, 首尾词边界, 尾允复数."""
    esc = re.escape(name.strip().lower())
    esc = esc.replace(r"\ ", r"\s+")
    return r"\b" + esc + r"\w*\b"


# 39 术语别名 (小写正则, IGNORECASE 编译).
# 设计原则: 高召回 (漏检=重演 #14), 精度只在已证误报处收紧
# (Speed 排 attack/structure/enemy/burning, Range 不吞 ranged).
TERM_PATTERNS: dict[str, list[str]] = {
    "Max HP": [r"\bmax\s*hp\b", r"\bmax\s*health\b", r"\bmaximum\s*hp\b", r"\bmaximum\s*health\b"],
    "HP Regeneration": [r"\bhp\s*regen\w*\b", r"\bhealth\s*regen\w*\b", r"\bregen\b", r"\bregeneration\b"],
    "Life Steal": [r"\blife\s*steal\b", r"\blifesteal\b", r"\blife[\s\-]*steal\b"],
    "Damage": [r"\bdamage\b"],
    "Melee Damage": [r"\bmelee\b"],
    "Ranged Damage": [r"\branged\b"],
    "Elemental Damage": [r"\belemental\b"],
    "Attack Speed": [r"\battack\s*speed\b"],
    "Crit Chance": [r"\bcrit\b", r"\bcritical\b", r"\bcrit\s*chance\b", r"\bcrit\s*rate\b"],
    "Engineering": [r"\bengineering\b"],
    "Range": [r"\brange\b"],
    "Armor": [r"\barmor\b", r"\barmour\b"],
    "Dodge": [r"\bdodg\w*\b"],
    "Speed": [
        r"\bmovespeed\b",
        r"\bmove\s*speed\b",
        r"\bmovement\s*speed\b",
        r"(?<!attack )(?<!structure )(?<!enemy )(?<!burning )\bspeed\b",
    ],
    "Luck": [r"\bluck\b", r"\blucky\b"],
    "Harvesting": [r"\bharvest\w*\b"],
    "Curse": [r"\bcurse\w*\b"],
    "Consumable Heal": [r"\bconsumable\b", r"\bheal\b", r"\bhealing\b"],
    "% Materials Healing": [r"\bmaterials?\s*healing\b", r"\bmats\s*healing\b"],
    "% XP Gain": [r"\bxp\b", r"\bexperience\b", r"\bxp\s*gain\b"],
    "% Pickup Range": [r"\bpickup\b", r"\bpick[\s\-]*up\b"],
    "% Items Price": [r"\bitems?\s*price\b"],
    "% Explosion Damage": [r"\bexplosion\s*damage\b", r"\bexplosion\b"],
    "% Explosion Size": [r"\bexplosion\s*size\b", r"\bexplosion\s*radius\b", r"\bexplosion\s*range\b"],
    "Bounces": [r"\bbounc\w*\b"],
    "Piercing": [r"\bpierc\w*\b"],
    "% Piercing Damage": [r"\bpiercing\s*damage\b"],
    "% Damage against Bosses": [r"\bboss\b", r"\bbosses\b"],
    "% Structure Attack Speed": [r"\bstructure\s*attack\b"],
    "Structure Range": [r"\bstructure\s*range\b"],
    "% Burning Speed": [r"\bburning\s*speed\b", r"\bburning\b"],
    "Burning Spread": [r"\bburning\s*spread\b", r"\bburn\s*spread\b"],
    "Knockback": [r"\bknockback\b", r"\bknock\s*back\b", r"\bknock\b"],
    "% Double Material Chance": [r"\bdouble\s*mats?\b", r"\bdouble\s*material\b"],
    "Free Rerolls": [r"\breroll\w*\b", r"\bfree\s*reroll\w*\b"],
    "Trees": [r"\btrees?\b"],
    "% Enemies": [r"\benemies\b"],
    "% Enemy Speed": [r"\benemy\s*speed\b", r"\benemy\b"],
    "% Reroll Price": [r"\breroll\s*price\b"],
}

WEAPON_PATTERNS: dict[str, list[str]] = {
    "SMG": [r"\bsmg\b"],
    "Pistol": [r"\bpistol\w*\b"],
    "Minigun": [r"\bminigun\b", r"\bmini\s*gun\b"],
    "Wrench": [r"\bwrench\w*\b"],
}

ITEM_PATTERNS: dict[str, list[str]] = {
    "Big Arms": [r"\bbig\s*arms\b"],
    "Improved Tools": [r"\bimproved\s*tools\b"],
    "Turret": [r"\bturret\w*\b"],
    "Coffee": [r"\bcoffee\b"],
}


def _compile(patterns: list[str]) -> list[re.Pattern[str]]:
    return [re.compile(p, re.IGNORECASE) for p in patterns]


def build_pattern_map(
    terms: list[str], weapons: list[str], items: list[str]
) -> dict[str, list[re.Pattern[str]]]:
    out: dict[str, list[re.Pattern[str]]] = {}
    for en in terms:
        pats = TERM_PATTERNS.get(en)
        if pats is None:
            pats = [_wordnames_to_pattern(en)]
        out[en] = _compile(pats)
    for en in weapons:
        pats = WEAPON_PATTERNS.get(en, [_wordnames_to_pattern(en)])
        out[f"weapon:{en}"] = _compile(pats)
    for en in items:
        pats = ITEM_PATTERNS.get(en, [_wordnames_to_pattern(en)])
        out[f"item:{en}"] = _compile(pats)
    return out


def parse_vtt(text: str) -> list[str]:
    """VTT 解析: 按空行分块, 丢时间戳/序号/头, 每块 join 为一句原句."""
    cues: list[str] = []
    # 统一换行, 按空行分块.
    blocks = re.split(r"\r?\n\s*\r?\n", text)
    for block in blocks:
        lines = [ln.strip() for ln in block.strip().splitlines()]
        # 去头: WEBVTT / NOTE / STYLE / REGION.
        if not lines:
            continue
        if lines[0].upper().startswith("WEBVTT"):
            lines = lines[1:]
        if not lines:
            continue
        if lines[0].upper().startswith(("NOTE", "STYLE", "REGION")):
            continue
        content: list[str] = []
        for ln in lines:
            if not ln:
                continue
            if "-->" in ln:
                continue
            if re.fullmatch(r"\d+", ln):
                continue
            # 去 HTML 标签.
            no_tag = re.sub(r"<[^>]+>", "", ln).strip()
            if no_tag:
                content.append(no_tag)
        if content:
            cue = " ".join(content).strip()
            # 长度截断防膨胀, 保留原句可审.
            if len(cue) > 500:
                cue = cue[:500]
            cues.append(cue)
    return cues


def scan_cues(
    cues: list[str], pattern_map: dict[str, list[re.Pattern[str]]]
) -> dict[str, tuple[int, list[str]]]:
    """每 key 计数 + 原句 (cap 10 句防膨胀)."""
    result: dict[str, tuple[int, list[str]]] = {}
    lowered = [c.lower() for c in cues]
    for key, pats in pattern_map.items():
        hits: list[str] = []
        for idx, low in enumerate(lowered):
            for pat in pats:
                if pat.search(low):
                    hits.append(cues[idx])
                    break
        result[key] = (len(hits), hits[:10])
    return result


def _variant_id_for_covers(covers: list[str]) -> str:
    return "-".join(str(c).strip().lower().replace(" ", "-") for c in covers)


def _load_variants(data_dir: Path, slug: str) -> tuple[list[dict[str, object]], list[str]]:
    """覆盖制变体加载: builds/<slug>.json 内 variants 数组, 旧单层废除."""
    build_path = data_dir / "builds" / f"{slug}.json"
    if not build_path.exists():
        return ([], [f"missing build data: {build_path}"])
    try:
        raw = json.loads(build_path.read_text(encoding="utf-8"))
    except Exception as exc:
        return ([], [f"build load fail {slug}: {exc}"])
    if not isinstance(raw, dict):
        return ([], [f"build must be dict: {slug}"])
    variants_raw = raw.get("variants")
    if not isinstance(variants_raw, list) or not variants_raw:
        return ([], [f"missing section data: variants (须为非空数组, 旧单层键废除): {slug}"])
    out: list[dict[str, object]] = [v for v in variants_raw if isinstance(v, dict)]
    if len(out) != len(variants_raw):
        return ([], [f"variants must be dicts: {slug}"])
    return (out, [])


def _vtt_for_variant(subs_dir: Path, slug: str, variant_id: str) -> Path:
    """每变体字幕: data/subs/<slug>__<variant>.en-orig.vtt; 单变体兼容旧 <slug>.en-orig.vtt."""
    per = subs_dir / f"{slug}__{variant_id}.en-orig.vtt"
    if per.exists():
        return per
    legacy = subs_dir / f"{slug}.en-orig.vtt"
    return legacy


def build_one_variant(
    slug: str, variant: dict[str, object], data_dir: Path, subs_dir: Path, mentions_dir: Path,
    terms: list[str], weapons: list[str], items: list[str],
) -> tuple[list[str], list[str]]:
    covers_raw = variant.get("covers")
    covers = [str(c) for c in covers_raw] if isinstance(covers_raw, list) else []
    vid = str(variant.get("id", "") or _variant_id_for_covers(covers))
    vtt_path = _vtt_for_variant(subs_dir, slug, vid)
    if not vtt_path.exists():
        per = subs_dir / f"{slug}__{vid}.en-orig.vtt"
        return ([f"missing subtitle: {per} (先按 SOP §4 每变体独立入库字幕)"], [])
    try:
        cues = parse_vtt(vtt_path.read_text(encoding="utf-8"))
    except Exception as exc:
        return ([f"vtt parse fail: {exc}"], [])
    pattern_map = build_pattern_map(terms, weapons, items)
    scanned = scan_cues(cues, pattern_map)
    src = variant.get("source")
    video_id = str(src.get("video_id")) if isinstance(src, dict) and isinstance(src.get("video_id"), str) else ""
    terms_out: dict[str, dict[str, object]] = {}
    for en in terms:
        count, quotes = scanned.get(en, (0, []))
        terms_out[en] = {"count": count, "quotes": quotes}
    weapons_out: dict[str, dict[str, object]] = {}
    for en in weapons:
        count, quotes = scanned.get(f"weapon:{en}", (0, []))
        weapons_out[en] = {"count": count, "quotes": quotes}
    items_out: dict[str, dict[str, object]] = {}
    for en in items:
        count, quotes = scanned.get(f"item:{en}", (0, []))
        items_out[en] = {"count": count, "quotes": quotes}
    # vtt 相对路径: per-variant 优先, legacy 回落保留原串.
    try:
        repo = Path(__file__).resolve().parent.parent
        vtt_rel = str(vtt_path.relative_to(repo))
    except Exception:
        vtt_rel = f"data/subs/{slug}__{vid}.en-orig.vtt"
    payload: dict[str, object] = {
        "slug": slug,
        "variant": vid,
        "covers": covers,
        "label": str(variant.get("label", "")),
        "vtt": vtt_rel.replace("\\", "/"),
        "video_id": video_id,
        "generated_by": "scripts/build_mentions.py",
        "terms": terms_out,
        "weapons": weapons_out,
        "items": items_out,
    }
    mentions_dir.mkdir(parents=True, exist_ok=True)
    out_path = mentions_dir / f"{slug}__{vid}.json"
    out_path.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    return ([], [])


def build_one(
    slug: str, data_dir: Path, subs_dir: Path, mentions_dir: Path, variant_id: str | None = None,
) -> tuple[list[str], list[str]]:
    errors: list[str] = []
    warns: list[str] = []
    try:
        terms = load_terms(data_dir)
    except Exception as exc:
        return ([f"terms load fail: {exc}"], [])
    if len(terms) != 39:
        return ([f"terms must be 39, got {len(terms)}"], [])
    try:
        weapons, items = load_registry_names(data_dir)
    except Exception as exc:
        return ([f"registry load fail: {exc}"], [])
    variants, v_errors = _load_variants(data_dir, slug)
    if v_errors:
        return (v_errors, [])
    targets = [v for v in variants if variant_id is None or str(v.get("id", "")) == variant_id]
    if variant_id is not None and not targets:
        return ([f"unknown variant: {slug}__{variant_id} (covers slug 化)"], [])
    for variant in targets:
        v_errors, _ = build_one_variant(slug, variant, data_dir, subs_dir, mentions_dir, terms, weapons, items)
        errors.extend(v_errors)
    return (errors, warns)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="构建字幕x术语交叉表 (#17 机器 gate)")
    group = parser.add_mutually_exclusive_group(required=True)
    group.add_argument("--slug", help="按角色构建, 如 --slug engineer")
    group.add_argument("--all", action="store_true", help="全量构建 (有字幕者)")
    parser.add_argument("--data-dir", default="data")
    parser.add_argument("--subs-dir", default="")
    parser.add_argument("--mentions-dir", default="")
    parser.add_argument("--variant", default="", help="单变体 id, 如 --variant ultimate (须与 --slug 同用)")
    args = parser.parse_args(argv)

    repo = Path(__file__).resolve().parent.parent
    data_dir = Path(args.data_dir)
    if not data_dir.is_absolute():
        data_dir = repo / data_dir
    subs_dir = Path(args.subs_dir) if args.subs_dir else data_dir / "subs"
    if not subs_dir.is_absolute():
        subs_dir = repo / subs_dir
    mentions_dir = Path(args.mentions_dir) if args.mentions_dir else data_dir / "mentions"
    if not mentions_dir.is_absolute():
        mentions_dir = repo / mentions_dir

    if args.slug:
        variant_arg = str(args.variant).strip() or None
        errors, _ = build_one(args.slug, data_dir, subs_dir, mentions_dir, variant_arg)
        if errors:
            for err in errors:
                print(f"FAIL: {err}", file=sys.stderr)
            return 1
        suffix = f"__{variant_arg}" if variant_arg else " (全变体)"
        print(f"built mentions --slug {args.slug}{suffix} -> {mentions_dir}")
        return 0

    # --all: 有 build 数据且有字幕者逐个构建, 缺字幕者跳过 warn (不 fail, 待补).
    builds_dir = data_dir / "builds"
    slugs = sorted(p.stem for p in builds_dir.glob("*.json")) if builds_dir.exists() else []
    failed = False
    for slug in slugs:
        # 覆盖制: 每变体缺字幕单独 warn 跳过, 不 fail 整单.
        variants, v_errors = _load_variants(data_dir, slug)
        if v_errors or not variants:
            print(f"WARN: missing build variants, skip {slug} (待补)")
            continue
        for variant in variants:
            vid = str(variant.get("id", ""))
            vtt_path = _vtt_for_variant(subs_dir, slug, vid)
            if not vtt_path.exists():
                print(f"WARN: missing subtitle, skip {slug}__{vid} (待补)")
                continue
            errors, _ = build_one(slug, data_dir, subs_dir, mentions_dir, vid)
            if errors:
                for err in errors:
                    print(f"FAIL [{slug}__{vid}]: {err}", file=sys.stderr)
                failed = True
    print(f"built mentions --all -> {mentions_dir}")
    return 1 if failed else 0


if __name__ == "__main__":
    raise SystemExit(main())
