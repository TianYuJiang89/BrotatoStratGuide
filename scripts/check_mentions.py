"""交叉表机检 (#17): 字幕提到未定级 warn, 定级无命中挂名 warn, 只 warn 不 fail.

输入: `data/mentions/<slug>.json` (build_mentions 产物) + `data/builds/<slug>.json`.
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


def check_one(
    slug: str, data_dir: Path, mentions_dir: Path
) -> tuple[list[str], list[str]]:
    errors: list[str] = []
    warns: list[str] = []
    mentions_path = mentions_dir / f"{slug}.json"
    if not mentions_path.exists():
        return ([f"missing mentions table: {mentions_path} (先跑 build_mentions --slug {slug})"], [])
    build_path = data_dir / "builds" / f"{slug}.json"
    if not build_path.exists():
        return ([f"missing build data: {build_path}"], [])
    try:
        mentions = json.loads(mentions_path.read_text(encoding="utf-8"))
    except Exception as exc:
        return ([f"mentions load fail {slug}: {exc}"], [])
    try:
        data = json.loads(build_path.read_text(encoding="utf-8"))
    except Exception as exc:
        return ([f"build load fail {slug}: {exc}"], [])
    if not isinstance(mentions, dict) or not isinstance(data, dict):
        return ([f"mentions/build must be dict: {slug}"], [])

    terms_m = mentions.get("terms")
    weapons_m = mentions.get("weapons")
    items_m = mentions.get("items")
    if not isinstance(terms_m, dict):
        return ([f"mentions terms must be dict: {slug}"], [])

    ratings_raw = data.get("ratings")
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

    # --- 武器 (weapons_t1+t2 的 name_en 集合为定级) ---
    present_weapons: dict[str, object] = {}
    for key in ("weapons_t1", "weapons_t2"):
        arr = data.get(key)
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

    # --- 道具 (items 的 name_en 集合为定级) ---
    present_items: dict[str, object] = {}
    arr = data.get("items")
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


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="交叉表机检只 warn 不 fail (#17)")
    group = parser.add_mutually_exclusive_group(required=True)
    group.add_argument("--slug", help="按角色检查, 如 --slug engineer")
    group.add_argument("--all", action="store_true", help="全量检查")
    parser.add_argument("--data-dir", default="data")
    parser.add_argument("--mentions-dir", default="")
    args = parser.parse_args(argv)

    repo = Path(__file__).resolve().parent.parent
    data_dir = Path(args.data_dir)
    if not data_dir.is_absolute():
        data_dir = repo / data_dir
    mentions_dir = Path(args.mentions_dir) if args.mentions_dir else data_dir / "mentions"
    if not mentions_dir.is_absolute():
        mentions_dir = repo / mentions_dir

    if args.slug:
        errors, warns = check_one(args.slug, data_dir, mentions_dir)
        if errors:
            for err in errors:
                print(f"FAIL: {err}", file=sys.stderr)
            return 1
        for w in warns:
            print(w)
        if warns:
            print(f"WARN: check_mentions {len(warns)} 项待清零/挂名, 仍可发布 (只 warn 不 fail)")
        else:
            print(f"OK: mentions cleared, {args.slug} 交叉表清零")
        return 0

    builds_dir = data_dir / "builds"
    slugs = sorted(p.stem for p in builds_dir.glob("*.json")) if builds_dir.exists() else []
    failed = False
    total_warns = 0
    for slug in slugs:
        # 无字幕无表者跳过 (待补, 由 build_mentions --all 统一提示).
        if not (mentions_dir / f"{slug}.json").exists():
            print(f"WARN: missing mentions table, skip {slug} (待补)")
            continue
        errors, warns = check_one(slug, data_dir, mentions_dir)
        if errors:
            for err in errors:
                print(f"FAIL [{slug}]: {err}", file=sys.stderr)
            failed = True
            continue
        for w in warns:
            print(f"[{slug}] {w}")
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
