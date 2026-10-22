"""#72 agent 内自验试点 (05 ranking): 机械检验 CLI 薄皮.

Seams (deterministic-first, no LLM in tests):
- CLI 薄皮只复用 step05_loop.validate_ranking, 不碰业务判断 (tier 谁该 T1 不判)
- 只验存在+格式 (键齐/类型/quote 子集/退役字段缺席), 只读不写
- 机器可读报错 (JSON {"ok", "errors"}) + exit code (0 绿/1 红)
- 外闸不动: 本脚本不写文件, 不替代 check_segment1 / loop 内校验
"""
from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path

import pytest

REPO = Path(__file__).resolve().parent.parent


def _run_validator(workdir: Path, extra: list[str] | None = None) -> subprocess.CompletedProcess:
    cmd = [sys.executable, str(REPO / "scripts" / "validate_step05_ranking.py"),
           "--workdir", str(workdir)]
    if extra:
        cmd += extra
    return subprocess.run(cmd, capture_output=True, text=True, cwd=str(REPO))


def _mk_workdir(tmp_path: Path, ranking: dict | None = None,
                drop_ranking: bool = False,
                candidates: list[dict] | None = None,
                evidences: dict[str, dict] | None = None) -> Path:
    """最小 05 ranking 工作区: candidates + per_weapon + ranking (+sentences 占位)."""
    workdir = tmp_path / "w"
    outdir = workdir / "steps" / "05-weapons"
    per = outdir / "per_weapon"
    per.mkdir(parents=True, exist_ok=True)
    sents = [
        {"id": 1, "text": "take a second minigun if shows up",
         "start": None, "end": None, "t": None},
        {"id": 2, "text": "four screwdrivers reducing effect",
         "start": None, "end": None, "t": None},
    ]
    (workdir / "steps" / "01-sentences").mkdir(parents=True, exist_ok=True)
    (workdir / "steps" / "01-sentences" / "sentences.json").write_text(
        json.dumps(sents, ensure_ascii=False) + "\n", encoding="utf-8")
    if candidates is None:
        candidates = [
            {"name_en": "Minigun", "count": 1,
             "quotes": [sents[0]["text"]],
             "quote_details": [{"quote": sents[0]["text"], "start": None,
                                "end": None, "t": None, "context": sents[0]["text"]}]},
            {"name_en": "Screwdriver", "count": 1,
             "quotes": [sents[1]["text"]],
             "quote_details": [{"quote": sents[1]["text"], "start": None,
                                "end": None, "t": None, "context": sents[1]["text"]}]},
        ]
    (outdir / "candidates.json").write_text(
        json.dumps(candidates, ensure_ascii=False) + "\n", encoding="utf-8")
    if evidences is None:
        evidences = {
            "Minigun": {"name_en": "Minigun", "tier": "T1",
                        "quotes": [sents[0]["text"]], "analysis": "a",
                        "note": "n", "copies": "2把起",
                        "copies_quote": sents[0]["text"][:12]},
            "Screwdriver": {"name_en": "Screwdriver", "tier": "T2",
                            "quotes": [sents[1]["text"]], "analysis": "a",
                            "note": "n", "copies": "未提及", "copies_quote": ""},
        }
    import re as _re
    for n, ev in evidences.items():
        safe = _re.sub(r"[^A-Za-z0-9]+", "_", n).strip("_")
        (per / f"{safe}.json").write_text(
            json.dumps(ev, ensure_ascii=False) + "\n", encoding="utf-8")
    if not drop_ranking:
        if ranking is None:
            ranking = {
                "t1": [{"name_en": "Minigun",
                        "note": f"主力原话\"{sents[0]['text'][:12]}\"。",
                        "copies": "2把起",
                        "copies_quote": sents[0]["text"][:12]}],
                "t2": [{"name_en": "Screwdriver",
                        "note": "过渡原话\"four screwdr\"。",
                        "copies": "未提及", "copies_quote": ""}],
            }
            # 保证短引逐字: 取 evidence quotes 前缀
            ranking["t2"][0]["note"] = f"过渡原话\"{sents[1]['text'][:12]}\"。"
            ranking["t2"][0]["copies_quote"] = ""
        (outdir / "ranking.json").write_text(
            json.dumps(ranking, ensure_ascii=False) + "\n", encoding="utf-8")
    return workdir


def test_validator_script_exists():
    p = REPO / "scripts" / "validate_step05_ranking.py"
    assert p.exists(), "scripts/validate_step05_ranking.py must exist (#72 CLI 薄皮)"


def test_validator_reuses_existing_validate_no_business():
    """薄皮只复用 validate_ranking, 不碰业务判断 (谁该 T1 不判, 不设断层/数字词)."""
    src = (REPO / "scripts" / "validate_step05_ranking.py").read_text(encoding="utf-8")
    assert "validate_ranking" in src, "须复用 step05_loop.validate_ranking (薄皮, 不另写规则)"
    assert "step05_loop" in src, "须从 step05_loop 导入 (现有 validate_* 加 CLI 薄皮)"
    for banned in ("verified+5", "最大断层", "数字词", "拿取动词", "score=",
                   "registry-slice", "is_core_gun"):
        assert banned not in src, f"检验脚本不碰业务判断 ({banned})"


def test_validator_readonly_no_write():
    """只读不写: 无写盘调用 (write_text/unlink/mkdir/open写)."""
    src = (REPO / "scripts" / "validate_step05_ranking.py").read_text(encoding="utf-8")
    for banned in ("write_text", ".unlink()", "mkdir(", 'open('):
        # open( 读允许, 写不允许: 查写模式
        if banned == "open(":
            continue
        assert banned not in src, f"检验脚本只读不写, 不许 {banned} (#72)"
    # 写模式 open(..., "w") / "a" 一律不许
    import re
    assert not re.search(r'open\([^)]*["\'][wa]["\']', src), "检验脚本不许 open 写模式 (只读)"


def test_validator_ok_green_machine_readable(tmp_path):
    workdir = _mk_workdir(tmp_path)
    r = _run_validator(workdir)
    assert r.returncode == 0, f"绿件须 exit 0: stdout={r.stdout[-1000:]} stderr={r.stderr[-1000:]}"
    payload = json.loads(r.stdout.strip().splitlines()[-1] if r.stdout.strip() else "{}")
    # 允许 human 前言 + 末行 JSON, 但末行须机器可读
    assert payload.get("ok") is True, f"绿件 ok 须 true: {payload}"
    assert payload.get("errors") == [], f"绿件 errors 须空: {payload}"


def test_validator_missing_file_red(tmp_path):
    workdir = _mk_workdir(tmp_path, drop_ranking=True)
    r = _run_validator(workdir)
    assert r.returncode == 1, "缺件须 exit 1 (missing-section-is-fail)"
    payload = json.loads(r.stdout.strip().splitlines()[-1])
    assert payload.get("ok") is False
    assert len(payload.get("errors", [])) >= 1, "缺件须机器可读报错"


def test_validator_format_red_retired_and_quote_subset(tmp_path):
    sents = ["take a second minigun if shows up", "four screwdrivers reducing effect"]
    # 退役字段 (顶层, 沿现有 validate_ranking 口径: 出现即 fail)
    bad_ranking = {
        "t1": [{"name_en": "Minigun", "note": f"主力原话\"{sents[0][:12]}\"。",
                "copies": "2把起", "copies_quote": sents[0][:12]}],
        "t2": [{"name_en": "Screwdriver", "note": f"过渡原话\"{sents[1][:12]}\"。",
                "copies": "未提及", "copies_quote": ""}],
        "confidence": "verified",
    }
    workdir = _mk_workdir(tmp_path / "case_retired", ranking=bad_ranking)
    r = _run_validator(workdir)
    assert r.returncode == 1, "退役字段须红 (出现即 fail)"
    payload = json.loads(r.stdout.strip().splitlines()[-1])
    assert payload.get("ok") is False and payload.get("errors"), "须机器可读报错"
    # quote 子集: 短引改写
    bad2 = {
        "t1": [{"name_en": "Minigun", "note": "主力原话\"我编的短引\"。",
                "copies": "2把起", "copies_quote": sents[0][:12]}],
        "t2": [{"name_en": "Screwdriver", "note": f"过渡原话\"{sents[1][:12]}\"。",
                "copies": "未提及", "copies_quote": ""}],
    }
    workdir2 = _mk_workdir(tmp_path / "case_quote", ranking=bad2)
    r2 = _run_validator(workdir2)
    assert r2.returncode == 1, "短引改写须红 (quote 子集)"


def test_validator_does_not_judge_tier(tmp_path):
    """不碰业务判断: T1/T2 互换仍绿 (只要格式自洽, 谁该 T1 不判)."""
    sents = ["take a second minigun if shows up", "four screwdrivers reducing effect"]
    rank_a = {
        "t1": [{"name_en": "Minigun", "note": f"主力原话\"{sents[0][:12]}\"。",
                "copies": "2把起", "copies_quote": sents[0][:12]}],
        "t2": [{"name_en": "Screwdriver", "note": f"过渡原话\"{sents[1][:12]}\"。",
                "copies": "未提及", "copies_quote": ""}],
    }
    rank_b = {
        "t1": [{"name_en": "Screwdriver", "note": f"主力原话\"{sents[1][:12]}\"。",
                "copies": "未提及", "copies_quote": ""}],
        "t2": [{"name_en": "Minigun", "note": f"过渡原话\"{sents[0][:12]}\"。",
                "copies": "2把起", "copies_quote": sents[0][:12]}],
    }
    w1 = _mk_workdir(tmp_path / "tier_a", ranking=rank_a)
    w2 = _mk_workdir(tmp_path / "tier_b", ranking=rank_b)
    assert _run_validator(w1).returncode == 0, "切分 A 须绿"
    assert _run_validator(w2).returncode == 0, "切分 B (互换) 亦须绿 (不判谁该 T1)"
