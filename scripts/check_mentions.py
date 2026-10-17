"""交叉表机检 (#17 + #20 覆盖制): 字幕提到未定级 warn, 定级无命中挂名 warn, 只 warn 不 fail.

输入: `data/mentions/<slug>__<variant>.json` (每变体独立, build_mentions 产物) + `data/builds/<slug>.json` 内 variants.

- 提到未定级: terms/weapons/items 在字幕 count>0 但 builds 无定级 -> WARN.
- 定级无命中: builds 有定级 (S-F / 武器在列 / 道具在列) 但 count==0,
  且 note/reason 未注明出处 (标题/描述/chapters) -> WARN 疑为编.
  注明出处即视为标题/描述/chapters 口径, 不 warn.

只 warn 不 fail (退出码恒 0), 不动现有 check.py 门禁.
缺文件/结构错才 fail (退出码 1): 表不存在即 gate 未跑, 必须补.

用法:
  python scripts/check_mentions.py --slug engineer
  python scripts/check_mentions.py --all
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

VALID_RATINGS: tuple[str, ...] = ("S", "A", "B", "C", "D", "F")

# 注明出处关键词 (大小写不敏感): 标题/描述/chapters 任一即视为有出处.
SOURCE_KEYWORDS: tuple[str, ...] = (
    "标题",
    "描述",
    "出处",
    "chapter",
    "title",
    "description",
    "视频标题",
    "视频描述",
)


def _has_source(note: object) -> bool:
    if not isinstance(note, str) or not note.strip():
        return False
    lowered = note.lower()
    return any(kw.lower() in lowered for kw in SOURCE_KEYWORDS)


def _load_variant(data: dict[str, object], variant_id: str | None) -> tuple[dict[str, object] | None, list[str]]:
    variants_raw = data.get("variants")
    if not isinstance(variants_raw, list) or not variants_raw:
        return (None, ["missing section data: variants (须为非空数组, 旧单层键废除)"])
    if variant_id is None:
        # 单变体默认首个, 多变体须显式 --variant (调用方循环).
        first = variants_raw[0] if isinstance(variants_raw[0], dict) else None
        return (first, [] if first else ["variants[0] must be dict"])
    for v in variants_raw:
        if isinstance(v, dict) and str(v.get("id", "")) == variant_id:
            return (v, [])
    return (None, [f"unknown variant: __{variant_id}"])


def check_one_variant(
    slug: str, variant_id: str, variant: dict[str, object], mentions: dict[str, object],
) -> tuple[list[str], list[str]]:
    errors: list[str] = []
    warns: list[str] = []
    label = f"{slug}__{variant_id}"
    terms_m = mentions.get("terms")
    weapons_m = mentions.get("weapons")
    items_m = mentions.get("items")
    if not isinstance(terms_m, dict):
        return ([f"mentions terms must be dict: {label}"], [])
    ratings_raw = variant.get("ratings")
    ratings: dict[str, object] = ratings_raw if isinstance(ratings_raw, dict) else {}

    # --- 术语 ---
    for en, entry in terms_m.items():
        if not isinstance(entry, dict):
            continue
        count_raw = entry.get("count", 0)
        count = count_raw if isinstance(count_raw, int) else 0
        r_entry = ratings.get(en)
        has_rating = isinstance(r_entry, dict) and r_entry.get("rating") in VALID_RATINGS
        if count > 0 and not has_rating:
            quotes = r_entry if False else entry.get("quotes", [])
            sample = ""
            if isinstance(quotes, list) and quotes and isinstance(quotes[0], str):
                sample = quotes[0][:120]
            warns.append(
                f"WARN: {en} 字幕提到 {count} 次但未定级 (例: {sample})"
            )
        elif has_rating and count == 0:
            assert isinstance(r_entry, dict)
            rating = r_entry.get("rating")
            note = r_entry.get("note", "")
            if not _has_source(note):
                warns.append(
                    f"WARN: {en} 定级 {rating} 但字幕无命中且未注明出处 "
                    f"(疑为编, 须注明标题/描述/chapters)"
                )

    # --- 武器 (weapons_t1+t2 的 name_en 集合为定级, 每变体独立) ---
    present_weapons: dict[str, object] = {}
    for key in ("weapons_t1", "weapons_t2"):
        arr = variant.get(key)
        if isinstance(arr, list):
            for w in arr:
                if isinstance(w, dict) and isinstance(w.get("name_en"), str):
                    present_weapons[str(w.get("name_en"))] = w
    if isinstance(weapons_m, dict):
        for en, entry in weapons_m.items():
            if not isinstance(entry, dict):
                continue
            count_raw = entry.get("count", 0)
            count = count_raw if isinstance(count_raw, int) else 0
            in_build = en in present_weapons
            if count > 0 and not in_build:
                warns.append(f"WARN: 武器 {en} 字幕提到 {count} 次但未入库 (未定级)")
            elif in_build and count == 0:
                w_entry = present_weapons[en]
                note = w_entry.get("note", "") if isinstance(w_entry, dict) else ""
                if not _has_source(note):
                    warns.append(
                        f"WARN: 武器 {en} 已入库但字幕无命中且未注明出处 "
                        f"(疑为编, 须注明标题/描述/chapters)"
                    )

    # --- 道具 (items 的 name_en 集合为定级, 每变体独立) ---
    present_items: dict[str, object] = {}
    arr = variant.get("items")
    if isinstance(arr, list):
        for it in arr:
            if isinstance(it, dict) and isinstance(it.get("name_en"), str):
                present_items[str(it.get("name_en"))] = it
    if isinstance(items_m, dict):
        for en, entry in items_m.items():
            if not isinstance(entry, dict):
                continue
            count_raw = entry.get("count", 0)
            count = count_raw if isinstance(count_raw, int) else 0
            in_build = en in present_items
            if count > 0 and not in_build:
                warns.append(f"WARN: 道具 {en} 字幕提到 {count} 次但未入库 (未定级)")
            elif in_build and count == 0:
                i_entry = present_items[en]
                reason = i_entry.get("reason", "") if isinstance(i_entry, dict) else ""
                if not _has_source(reason):
                    warns.append(
                        f"WARN: 道具 {en} 已入库但字幕无命中且未注明出处 "
                        f"(疑为编, 须注明标题/描述/chapters)"
                    )
    return (errors, warns)


def check_one(
    slug: str, data_dir: Path, mentions_dir: Path, variant_id: str | None = None,
) -> tuple[list[str], list[str]]:
    """覆盖制机检: 每变体独立表 `data/mentions/<slug>__<variant>.json`, 只 warn 不 fail."""
    errors: list[str] = []
    warns: list[str] = []
    build_path = data_dir / "builds" / f"{slug}.json"
    if not build_path.exists():
        return ([f"missing build data: {build_path}"], [])
    try:
        data = json.loads(build_path.read_text(encoding="utf-8"))
    except Exception as exc:
        return ([f"build load fail {slug}: {exc}"], [])
    if not isinstance(data, dict):
        return ([f"build must be dict: {slug}"], [])
    variants_raw = data.get("variants")
    if not isinstance(variants_raw, list) or not variants_raw:
        return ([f"missing section data: variants (须为非空数组, 旧单层键废除): {slug}"], [])
    targets: list[dict[str, object]] = []
    for v in variants_raw:
        if not isinstance(v, dict):
            continue
        if variant_id is None or str(v.get("id", "")) == variant_id:
            targets.append(v)
    if variant_id is not None and not targets:
        return ([f"unknown variant: {slug}__{variant_id}"], [])
    for variant in targets:
        vid = str(variant.get("id", ""))
        mentions_path = mentions_dir / f"{slug}__{vid}.json"
        # 单变体兼容旧表: 若 per-variant 缺但旧 <slug>.json 在, 回落旧表.
        fallback_used = False
        if not mentions_path.exists():
            legacy = mentions_dir / f"{slug}.json"
            if len(targets) == 1 and legacy.exists():
                mentions_path = legacy
                fallback_used = True
            else:
                errors.append(f"missing mentions table: {mentions_path} (先跑 build_mentions --slug {slug} --variant {vid})")
                continue
        try:
            mentions = json.loads(mentions_path.read_text(encoding="utf-8"))
        except Exception as exc:
            errors.append(f"mentions load fail {slug}__{vid}: {exc}")
            continue
        if not isinstance(mentions, dict):
            errors.append(f"mentions must be dict: {slug}__{vid}")
            continue
        v_errors, v_warns = check_one_variant(slug, vid, variant, mentions)
        errors.extend(v_errors)
        for w in v_warns:
            warns.append(f"[{slug}__{vid}] {w}" if not w.startswith("[" ) else w)
        _ = fallback_used
    return (errors, warns)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="交叉表机检只 warn 不 fail (#17)")
    group = parser.add_mutually_exclusive_group(required=True)
    group.add_argument("--slug", help="按角色检查, 如 --slug engineer")
    group.add_argument("--all", action="store_true", help="全量检查")
    parser.add_argument("--data-dir", default="data")
    parser.add_argument("--mentions-dir", default="")
    parser.add_argument("--variant", default="", help="单变体 id, 如 --variant ultimate")
    args = parser.parse_args(argv)

    repo = Path(__file__).resolve().parent.parent
    data_dir = Path(args.data_dir)
    if not data_dir.is_absolute():
        data_dir = repo / data_dir
    mentions_dir = Path(args.mentions_dir) if args.mentions_dir else data_dir / "mentions"
    if not mentions_dir.is_absolute():
        mentions_dir = repo / mentions_dir

    if args.slug:
        variant_arg = str(args.variant).strip() or None
        errors, warns = check_one(args.slug, data_dir, mentions_dir, variant_arg)
        if errors:
            for err in errors:
                print(f"FAIL: {err}", file=sys.stderr)
            return 1
        for w in warns:
            print(w)
        if warns:
            print(f"WARN: check_mentions {len(warns)} 项待清零/挂名, 仍可发布 (只 warn 不 fail)")
        else:
            suffix = f"__{variant_arg}" if variant_arg else ""
            print(f"OK: mentions cleared, {args.slug}{suffix} 交叉表清零")
        return 0

    builds_dir = data_dir / "builds"
    slugs = sorted(p.stem for p in builds_dir.glob("*.json")) if builds_dir.exists() else []
    failed = False
    total_warns = 0
    for slug in slugs:
        # 覆盖制: 每变体表独立, 缺表跳过待补.
        try:
            raw = json.loads((data_dir / "builds" / f"{slug}.json").read_text(encoding="utf-8"))
        except Exception:
            print(f"WARN: missing build, skip {slug} (待补)")
            continue
        variants_raw = raw.get("variants") if isinstance(raw, dict) else None
        vids: list[str] = [str(v.get("id", "")) for v in variants_raw if isinstance(v, dict)] if isinstance(variants_raw, list) else []
        if not vids:
            print(f"WARN: missing variants, skip {slug} (待补)")
            continue
        has_any = any((mentions_dir / f"{slug}__{vid}.json").exists() or (mentions_dir / f"{slug}.json").exists() for vid in vids)
        if not has_any:
            print(f"WARN: missing mentions table, skip {slug} (待补)")
            continue
        errors, warns = check_one(slug, data_dir, mentions_dir)
        if errors:
            for err in errors:
                print(f"FAIL [{slug}]: {err}", file=sys.stderr)
            failed = True
            continue
        for w in warns:
            print(w if w.startswith("[") else f"[{slug}] {w}")
        total_warns += len(warns)
    if failed:
        return 1
    if total_warns:
        print(f"WARN: check_mentions {total_warns} 项待清零/挂名, 仍可发布 (只 warn 不 fail)")
    else:
        print("OK: mentions cleared, 全量交叉表清零")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
