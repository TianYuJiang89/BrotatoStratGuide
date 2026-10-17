"""资源巡检 (#12): 注册表单源校验 + 应急目录平时空, 平时只校验不下载.

- 默认离线可跑 (无网络断言): 注册表全量 URL 结构 + 缩略图规格 +
  应急目录平时空 (只有占位, 无二进制) + 三处图标三件套字段齐全。
- --live 可选: 对注册表全量 thumb 做 HEAD (只读头不下载正文),
  404/5xx 即挂资源待重审, 不自动删图, 连续 7 天大面积 404 才人工切应急。
  与 check_updates.py 分工不混 (后者只管 Steam 数组 + Fandom 数量 + 取材日期)。

退出码: 结构错/应急二进制入库即 fail (1), 待校对只 warn (仍 0)。
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from urllib.request import Request, urlopen

sys.path.insert(0, str(Path(__file__).resolve().parent))
from build import (  # noqa: E402
    EXPECTED_PRIMARY,
    EXPECTED_SECONDARY,
    WIKI_BASE,
    local_icon_path,
)

EMERGENCY_GROUPS = ("chars", "items", "stats", "weapons")


def load_registry(data_dir: Path) -> dict[str, object]:
    return json.loads((data_dir / "wiki-cache.json").read_text(encoding="utf-8"))  # type: ignore[no-any-return]


def check_offline(data_dir: Path, repo: Path) -> tuple[list[str], list[str]]:
    errors: list[str] = []
    warns: list[str] = []
    try:
        reg = load_registry(data_dir)
    except Exception as exc:
        return ([f"registry load fail: {exc}"], [])
    stats = reg.get("stats")
    if not isinstance(stats, dict):
        return (["wiki-cache.json stats must be a dict"], [])
    # 主 17 必须有 thumb 缩略图, 次级 22 必须 missing 占位。
    for en in EXPECTED_PRIMARY:
        entry = stats.get(en)
        if not isinstance(entry, dict):
            errors.append(f"registry missing URL for term: {en}")
            continue
        thumb = entry.get("thumb")
        if not isinstance(thumb, str) or WIKI_BASE not in thumb:
            errors.append(f"registry missing URL for primary term: {en}")
        elif "/thumb/" not in thumb:
            errors.append(f"registry must use thumbnail not original for {en}")
    for en in EXPECTED_SECONDARY:
        entry = stats.get(en)
        if not isinstance(entry, dict):
            errors.append(f"registry missing URL for term: {en}")
            continue
        if entry.get("thumb") and not entry.get("missing"):
            errors.append(f"secondary {en} must use placeholder (wiki 无专用图标)")
    # items/weapons/chars 全量 URL + 缩略图规格。
    for section in ("items", "weapons"):
        sec = reg.get(section)
        if not isinstance(sec, dict) or not sec:
            errors.append(f"wiki-cache.json {section} must be a non-empty dict")
            continue
        for en, entry in sec.items():
            if not isinstance(entry, dict):
                errors.append(f"registry {section} entry broken: {en}")
                continue
            for field in ("page", "thumb"):
                value = entry.get(field)
                if not isinstance(value, str) or WIKI_BASE not in value:
                    errors.append(f"registry missing URL for {section}: {en} ({field})")
            thumb = entry.get("thumb")
            if isinstance(thumb, str) and "/thumb/" not in thumb:
                errors.append(f"registry must use thumbnail not original for {section}:{en}")
    chars = reg.get("chars")
    if not isinstance(chars, dict) or len(chars) != 64:
        errors.append("chars must be 64 (头像唯一 URL 源)")
    else:
        for en, entry in chars.items():
            if not isinstance(entry, dict):
                errors.append(f"registry entry broken: chars:{en}")
                continue
            thumb = entry.get("thumb")
            if not isinstance(thumb, str) or WIKI_BASE not in thumb or "/thumb/" not in thumb:
                errors.append(f"registry missing avatar thumb for char: {en}")
            elif "60px-" not in thumb:
                errors.append(f"registry avatar must be 60px thumbnail for char: {en}")
    # 应急目录平时空: 只有占位, 无二进制入库 (平时只校验不下载)。
    assets = repo / "assets"
    for group in EMERGENCY_GROUPS:
        d = assets / group
        if not d.is_dir():
            errors.append(f"assets/{group} must exist (应急开关目录, 平时空)")
            continue
        pngs = [p for p in d.rglob("*.png")]
        if pngs:
            errors.append(f"assets/{group} must stay empty (平时只校验不下载), got {pngs[0].name}")
        # 应急路径可推导: 每个英文名都能映射到全小写短横线相对路径。
        pool: dict[str, object] = {}
        if group == "stats" and isinstance(stats, dict):
            pool = {en: stats.get(en) for en in (*EXPECTED_PRIMARY, *EXPECTED_SECONDARY)}
        elif isinstance(reg.get(group), dict):
            sec_map = reg.get(group)
            assert isinstance(sec_map, dict)
            pool = dict(sec_map)
        for en in pool:
            local = local_icon_path(group, str(en))
            if not local.startswith(f"assets/{group}/") or not local.endswith(".png"):
                errors.append(f"emergency path broken for {group}:{en} -> {local}")
    # 待校对只 warn。
    pending = sum(
        1 for en in (*EXPECTED_PRIMARY, *EXPECTED_SECONDARY)
        if isinstance(stats.get(en), dict) and str(stats.get(en, {}).get("needs_review", "")).upper() == "TRUE"  # type: ignore[union-attr]
    )
    if pending:
        warns.append(f"术语待校对 {pending} 项（※），中文以客户端简中为准")
    return (errors, warns)


def check_live(data_dir: Path, limit: int = 0) -> tuple[list[str], list[str]]:
    """全量 HEAD (只读头不下载正文): 404/5xx 即资源待重审, 不自动删图。"""
    errors: list[str] = []
    warns: list[str] = []
    reg = load_registry(data_dir)
    urls: list[str] = []
    seen: set[str] = set()

    def collect(mapping: object) -> None:
        if not isinstance(mapping, dict):
            return
        for entry in mapping.values():
            if not isinstance(entry, dict):
                continue
            thumb = entry.get("thumb")
            if isinstance(thumb, str) and thumb and thumb not in seen:
                seen.add(thumb)
                urls.append(thumb)
            tips = entry.get("tooltip")
            if isinstance(tips, list):
                for tip in tips:
                    if isinstance(tip, dict):
                        thumb2 = tip.get("thumb")
                        if isinstance(thumb2, str) and thumb2 and thumb2 not in seen:
                            seen.add(thumb2)
                            urls.append(thumb2)

    collect(reg.get("stats"))
    collect(reg.get("items"))
    collect(reg.get("weapons"))
    collect(reg.get("chars"))
    if limit > 0:
        urls = urls[:limit]
    bad = 0
    for url in urls:
        try:
            req = Request(url, method="HEAD")
            req.add_header("User-Agent", "BrotatoStratGuide-check/1.0")
            with urlopen(req, timeout=15) as resp:  # noqa: S310
                code = getattr(resp, "status", 200)
                if code >= 400:
                    bad += 1
                    errors.append(f"资源待重审 HEAD {code}: {url}")
        except Exception as exc:  # noqa: BLE001
            bad += 1
            errors.append(f"资源待重审 HEAD fail: {url} ({exc})")
    if bad:
        warns.append(f"HEAD {bad}/{len(urls)} 失效, 连续 7 天大面积 404 才人工切 --use-local-assets, 不自动删图")
    else:
        print(f"OK: HEAD {len(urls)} urls all reachable (只校验不下载)")
    return (errors, warns)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="资源巡检 (#12: 平时只校验不下载)")
    parser.add_argument("--data-dir", default="data")
    parser.add_argument("--live", action="store_true", help="live 全量 HEAD 校验 (需网络, 只读头不下载)")
    parser.add_argument("--limit", type=int, default=0, help="live 抽查上限 (0=全量)")
    args = parser.parse_args(argv)
    repo = Path(__file__).resolve().parent.parent
    data_dir = Path(args.data_dir)
    if not data_dir.is_absolute():
        data_dir = repo / data_dir
    errors, warns = check_offline(data_dir, repo)
    for w in warns:
        print(f"WARN: {w}")
    if errors:
        for e in errors:
            print(f"FAIL: {e}", file=sys.stderr)
        return 1
    if args.live:
        live_errors, live_warns = check_live(data_dir, args.limit)
        for w in live_warns:
            print(f"WARN: {w}")
        for e in live_errors:
            print(f"FAIL: {e}", file=sys.stderr)
        if live_errors:
            return 1
    print("OK: registry URLs + thumbnails + emergency-empty, switch ready")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
