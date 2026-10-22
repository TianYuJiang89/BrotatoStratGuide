#!/usr/bin/env python3
"""05 ranking 机械检验 CLI 薄皮 (#72 agent 内自验试点).

Deterministic-first + No silent fallback:
- 现有 validate_* 加 CLI 薄皮: 复用 scripts/step05_loop.validate_ranking,
  只验存在+格式 (键齐/类型/quote 子集/退役字段缺席), 不碰业务判断 (谁该 T1 不判).
- 只读不写: 不写任何文件, 只读 ranking/candidates/per_weapon, 机器可读报错 + exit code.
- 供 agent 落盘后自验: bash 跑本脚本 → 非零读 JSON errors → 只改报错项 → 重跑检验.
- 外闸不动: 本脚本不替代 check_segment1 / loop 内代码校验, 仅内闸.

用法 (cwd 为 workdir 时):
  python <repo>/scripts/validate_step05_ranking.py --workdir .
  python scripts/validate_step05_ranking.py --slug cyborg --variant ultimate --work-root G:/brotato-work

输出 (末行 JSON, 机器可读):
  {"ok": true, "step": "05-ranking", "errors": []}  exit 0
  {"ok": false, "step": "05-ranking", "errors": ["..."]}  exit 1
"""

from __future__ import annotations

import argparse
import json
import re
import sys
from pathlib import Path

REPO = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(REPO / "scripts"))

from step05_loop import validate_ranking  # noqa: E402  # 薄皮复用, 不另写规则


def _safe_term(name_en: str) -> str:
    return re.sub(r"[^A-Za-z0-9]+", "_", str(name_en)).strip("_")


def _resolve_workdir(args: argparse.Namespace) -> Path:
    if getattr(args, "workdir", None):
        return Path(args.workdir)
    return Path(args.work_root) / args.slug / args.variant


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description="05 ranking 机械检验 (#72, 只读)")
    ap.add_argument("--slug", default="cyborg")
    ap.add_argument("--variant", default="ultimate")
    ap.add_argument("--work-root", default="G:/brotato-work")
    ap.add_argument("--workdir", default="",
                    help="直接指定工作区目录 (agent cwd 即 workdir 时传 .)")
    args = ap.parse_args(argv)
    workdir = _resolve_workdir(args)

    step = "05-ranking"
    errors: list[str] = []

    outdir = workdir / "steps" / "05-weapons"
    per_dir = outdir / "per_weapon"
    candidates_path = outdir / "candidates.json"
    ranking_path = outdir / "ranking.json"

    # ---- 存在 (缺件即 fail, 不补空) ----
    for p, label in ((candidates_path, "steps/05-weapons/candidates.json"),
                     (ranking_path, "steps/05-weapons/ranking.json")):
        if not p.exists():
            errors.append(f"missing file: {label} (缺件即 fail)")

    candidates: list[dict] = []
    if candidates_path.exists():
        try:
            candidates = json.loads(candidates_path.read_text(encoding="utf-8"))
        except Exception as e:
            errors.append(f"candidates.json 非法 JSON: {e!r}")
            candidates = []
        if not errors or not any("candidates.json" in e for e in errors):
            if not isinstance(candidates, list) or not candidates:
                errors.append("candidates.json 须为非空数组 (discovery completeness)")
                candidates = []

    candidate_names: list[str] = []
    if isinstance(candidates, list) and candidates:
        for c in candidates:
            if isinstance(c, dict) and isinstance(c.get("name_en"), str):
                candidate_names.append(c["name_en"])
        if len(candidate_names) != len(set(candidate_names)):
            errors.append("candidates.json name_en 须去重")

    evidences: list[dict] = []
    if candidate_names:
        for n in candidate_names:
            safe = _safe_term(n)
            pp = per_dir / f"{safe}.json"
            if not pp.exists():
                errors.append(f"missing file: steps/05-weapons/per_weapon/{safe}.json (evidence 缺件即 fail)")
                continue
            try:
                ev = json.loads(pp.read_text(encoding="utf-8"))
            except Exception as e:
                errors.append(f"per_weapon/{safe}.json 非法 JSON: {e!r}")
                continue
            if not isinstance(ev, dict):
                errors.append(f"per_weapon/{safe}.json 须为对象")
                continue
            evidences.append(ev)

    if errors:
        print(json.dumps({"ok": False, "step": step, "errors": errors},
                         ensure_ascii=False))
        return 1

    # ---- 格式 (复用现有 validate_ranking: 键齐/类型/quote 子集/退役缺席, 不判业务) ----
    try:
        ranking_data = json.loads(ranking_path.read_text(encoding="utf-8"))
    except Exception as e:
        print(json.dumps({"ok": False, "step": step,
                          "errors": [f"ranking.json 非法 JSON: {e!r}"]},
                         ensure_ascii=False))
        return 1

    try:
        validate_ranking(ranking_data, candidate_names, evidences)
    except SystemExit as e:
        msg = str(e) if str(e) else "ranking 格式错 (缺件即 fail)"
        print(json.dumps({"ok": False, "step": step, "errors": [msg]},
                         ensure_ascii=False))
        return 1
    except Exception as e:
        print(json.dumps({"ok": False, "step": step,
                          "errors": [f"ranking 校验异常: {e!r}"]},
                         ensure_ascii=False))
        return 1

    print(json.dumps({"ok": True, "step": step, "errors": []}, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
