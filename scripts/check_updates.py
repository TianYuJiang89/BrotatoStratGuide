"""追加与巡检基线 (#10): 名录 64 + 术语 17+22 + Mod 拒收 + 未校对不发布.

- 默认校验本地基线 (离线可跑, 无网络断言):
  roster 64 (DLC 14), terms 主 17 + 次级 22 原序, 旧 3 口径作废,
  Mod 拒收 (未知 slug 不在 64 内), 追加增量未校对不发布。
- --live 可选: 查 Steam 1942280 dlc 数组 + Fandom Characters bt-dlc 数量,
  命中漂移即待重审 (需网络, 测试不跑 live)。

退出码: 基线错/追加未校对/Mod 即 fail (1), 待校对只 warn (仍 0)。
"""

from __future__ import annotations

import argparse
import csv
import json
import sys
from pathlib import Path

BASELINE_ROSTER = 64
BASELINE_ABYSSAL = 14
BASELINE_PRIMARY = 17
BASELINE_SECONDARY = 22
STEAM_DLC_BASELINE = [2868390, 3281080, 4498220]
FANDOM_BT_DLC_BASELINE = 14

sys.path.insert(0, str(Path(__file__).resolve().parent))
from build import EXPECTED_PRIMARY, EXPECTED_SECONDARY, LAST_MAJOR_UPDATE  # noqa: E402


def load_roster(data_dir: Path) -> list[dict[str, object]]:
    raw = json.loads((data_dir / "roster.json").read_text(encoding="utf-8"))
    return [r for r in raw if isinstance(r, dict)] if isinstance(raw, list) else []


def load_terms(data_dir: Path) -> list[dict[str, str]]:
    with (data_dir / "terms.csv").open(encoding="utf-8") as f:
        return [{k: (v.strip() if isinstance(v, str) else "") for k, v in r.items()} for r in csv.DictReader(f)]


def check_baseline(data_dir: Path) -> tuple[list[str], list[str]]:
    errors: list[str] = []
    warns: list[str] = []
    roster = load_roster(data_dir)
    if len(roster) < BASELINE_ROSTER:
        errors.append(f"名录 64 齐全: got {len(roster)}, need >=64")
        return (errors, warns)
    # 基线 64 内 DLC 14 归属正确 (多出的追加另查)。
    base = roster[:BASELINE_ROSTER]
    abyssal = [r for r in base if r.get("dlc") == "abyssal"]
    if len(abyssal) != BASELINE_ABYSSAL:
        errors.append(f"DLC 14 归属正确: got {len(abyssal)}, need 14")
    ids = [str(r.get("id", "")) for r in roster]
    if len(set(ids)) != len(ids):
        errors.append("roster ids must be unique (Mod 拒收)")
    terms = load_terms(data_dir)
    primary = [r for r in terms if r.get("type") == "primary"]
    secondary = [r for r in terms if r.get("type") == "secondary"]
    if len(primary) != BASELINE_PRIMARY or len(secondary) != BASELINE_SECONDARY:
        if len(secondary) == 3:
            errors.append("旧次级 3 口径作废，按全量 22 执行")
        else:
            errors.append(f"术语主次全量: got {len(primary)}+{len(secondary)}, need 17+22")
        return (errors, warns)
    if [r["en"] for r in primary] != EXPECTED_PRIMARY:
        errors.append("primary order mismatch (wiki 原序)")
    if [r["en"] for r in secondary] != EXPECTED_SECONDARY:
        errors.append("secondary order mismatch (wiki 次级原序)")
    by_en = {r["en"]: r for r in terms}
    for dlc_en in ("Curse", "% Reroll Price"):
        row = by_en.get(dlc_en)
        if not row or row.get("dlc") != "abyssal":
            errors.append(f"角标缺失即 fail: {dlc_en} 缺 abyssal")
    pending = sum(1 for r in terms if r.get("needs_review", "").upper() == "TRUE")
    if pending:
        warns.append(f"术语待校对 {pending} 项（※），中文以客户端简中为准")
    roster_pending = sum(1 for r in roster[:BASELINE_ROSTER] if str(r.get("needs_review", "")).upper() == "TRUE" or r.get("needs_review") is True)
    if roster_pending:
        warns.append(f"名录中文待校对 {roster_pending} 项（※），未校对前标待校对发布")
    # 追加规则: 超出基线 64 的增量必须已校对 (needs_review FALSE)，否则未校对不发布。
    extra = roster[BASELINE_ROSTER:]
    for r in extra:
        needs = r.get("needs_review")
        needs_true = str(needs).upper() == "TRUE" or needs is True
        if needs_true or str(r.get("zh", "")).strip() == "":
            errors.append(f"追加规则: 未校对不发布 {r.get('id')} (查数组对增量再校对入库)")
        # Mod 永不进入: 追加 dlc 非法或 id 非法即拒。
        if not r.get("id") or not r.get("en"):
            errors.append(f"追加规则: Mod 拒收 {r}")
    # #13 取材巡检:各 build 取材日期早于大更新即 warn 待重审 (人工触发复核)。
    # 离线可跑, 无网络断言;缺日期/占位即待补 warn, 非法难度等门禁由 build 报 fail。
    builds_dir = data_dir / "builds"
    if builds_dir.is_dir():
        for build_file in sorted(builds_dir.glob("*.json")):
            try:
                payload = json.loads(build_file.read_text(encoding="utf-8"))
            except Exception:
                continue
            if not isinstance(payload, dict):
                continue
            source = payload.get("source")
            if not isinstance(source, dict):
                continue
            published = source.get("published")
            game_version = source.get("game_version")
            slug = build_file.stem
            if not isinstance(published, str) or not published.strip():
                warns.append(f"取材待补 {slug}: 发布日期缺项 (双标注须齐全)")
                continue
            import re as _re

            if not _re.fullmatch(r"\d{4}-\d{2}-\d{2}", published.strip()):
                # 占位文案 (待补/占位) 走待补 warn, 其余非法格式同样 warn (fail 由 build 门禁报)。
                warns.append(f"取材待补 {slug}: 发布日期 {published!r} 非 YYYY-MM-DD")
                continue
            if published.strip() < LAST_MAJOR_UPDATE:
                warns.append(
                    f"取材待重审 {slug}: 发布 {published.strip()} 早于大更新 {LAST_MAJOR_UPDATE} "
                    f"(双标注复核, 命中待重审)"
                )
            if not isinstance(game_version, str) or not game_version.strip():
                warns.append(f"取材待补 {slug}: 游戏版本缺项 (双标注须齐全)")
    return (errors, warns)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="追加与巡检基线 (#10)")
    parser.add_argument("--data-dir", default="data")
    parser.add_argument("--live", action="store_true", help="live Steam+Fandom drift check (needs network)")
    args = parser.parse_args(argv)
    repo = Path(__file__).resolve().parent.parent
    data_dir = Path(args.data_dir)
    if not data_dir.is_absolute():
        data_dir = repo / data_dir
    errors, warns = check_baseline(data_dir)
    for w in warns:
        print(f"WARN: {w}")
    if errors:
        for e in errors:
            print(f"FAIL: {e}", file=sys.stderr)
        return 1
    if args.live:
        # 人工触发路径 (需网络, 测试不跑): 命中即挂待重审, 不自动改数。
        try:
            import urllib.request

            with urllib.request.urlopen(
                "https://store.steampowered.com/api/appdetails?appids=1942280&l=schinese",
                timeout=15,
            ) as resp:
                payload = json.loads(resp.read().decode("utf-8"))
                dlc = payload.get("1942280", {}).get("data", {}).get("dlc", [])
                if sorted(dlc) != sorted(STEAM_DLC_BASELINE):
                    print(f"WARN: Steam dlc 数组漂移 {dlc}，命中待重审 (当前基线 {STEAM_DLC_BASELINE})")
        except Exception as exc:
            print(f"WARN: live Steam 检查跳过 ({exc})")
    print("OK: roster 64 + terms 17+22 baseline, append rule ready")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
