"""SOP 版本锁 E2E (#30): builds 自带规则版本戳, 不一致 build 直接 fail.

Seams under test (pre-agreed per #8: E2E only):
- `python scripts/build.py --slug <slug>` exit codes + `docs/*.html` artifacts
- `data/builds/<slug>.json` bytes (sop_version 字段)

No internal imports, no network. All assertions inspect CLI exit codes
and generated file bytes.
"""

from __future__ import annotations

import json
import shutil
import subprocess
import sys
from pathlib import Path

REPO = Path(__file__).resolve().parent.parent
BUILD = [sys.executable, "scripts/build.py"]
FIXTURE = REPO / "tests" / "fixtures" / "cyborg.json"


def run_build(*args: str, cwd: Path = REPO) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        [*BUILD, *args],
        cwd=cwd,
        capture_output=True,
        text=True,
    )


def expected_sop_version() -> str:
    """当前期望版本: docs/sop/new-character-guide.md 最新 commit (统一锚点, #30)."""
    r = subprocess.run(
        ["git", "log", "-1", "--format=%H", "--", "docs/sop/new-character-guide.md"],
        cwd=REPO,
        capture_output=True,
        text=True,
    )
    return r.stdout.strip()


def make_isolated(tmp_path: Path) -> tuple[Path, Path, Path]:
    work = tmp_path / "work"
    if work.exists():
        shutil.rmtree(work)
    shutil.copytree(REPO / "data", work / "data")
    shutil.copytree(REPO / "templates", work / "templates")
    build_file = work / "data" / "builds" / "cyborg.json"
    build_file.parent.mkdir(parents=True, exist_ok=True)
    build_file.write_text(FIXTURE.read_text(encoding="utf-8"), encoding="utf-8")
    out = tmp_path / "out"
    out.mkdir(parents=True, exist_ok=True)
    return (work / "data", work / "templates", out)


def build_isolated(data_dir: Path, templates_dir: Path, out: Path) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        [sys.executable, str(REPO / "scripts" / "build.py"),
         "--slug", "cyborg",
         "--data-dir", str(data_dir),
         "--templates-dir", str(templates_dir),
         "--out-dir", str(out)],
        cwd=REPO, capture_output=True, text=True,
    )


def test_missing_sop_version_fails(tmp_path: Path) -> None:
    """缺 sop_version 即 fail, 不生成产物, 报错指明期望版本."""
    data_dir, templates_dir, out = make_isolated(tmp_path)
    build_file = data_dir / "builds" / "cyborg.json"
    data = json.loads(build_file.read_text(encoding="utf-8"))
    data.pop("sop_version", None)
    build_file.write_text(json.dumps(data, ensure_ascii=False), encoding="utf-8")
    r = build_isolated(data_dir, templates_dir, out)
    assert r.returncode != 0, "missing sop_version must fail"
    combined = (r.stdout + r.stderr)
    assert "sop_version" in combined.lower() or "sop" in combined.lower()
    expected = expected_sop_version()
    assert expected[:7] in combined, f"error must point at expected version {expected[:7]}"
    assert not (out / "cyborg.html").exists(), "fail must not emit artifact"


def test_stale_sop_version_fails(tmp_path: Path) -> None:
    """旧版 sop_version 即 fail, 不生成产物, 报错指明期望版本."""
    data_dir, templates_dir, out = make_isolated(tmp_path)
    build_file = data_dir / "builds" / "cyborg.json"
    data = json.loads(build_file.read_text(encoding="utf-8"))
    data["sop_version"] = "0" * 40
    build_file.write_text(json.dumps(data, ensure_ascii=False), encoding="utf-8")
    r = build_isolated(data_dir, templates_dir, out)
    assert r.returncode != 0, "stale sop_version must fail"
    combined = (r.stdout + r.stderr)
    assert "sop_version" in combined.lower() or "sop" in combined.lower()
    expected = expected_sop_version()
    assert expected[:7] in combined, f"error must point at expected version {expected[:7]}"
    assert not (out / "cyborg.html").exists(), "fail must not emit artifact"


def test_current_sop_version_passes(tmp_path: Path) -> None:
    """当前版本 sop_version 放行 (隔离夹具与 repo 基线一致)."""
    data_dir, templates_dir, out = make_isolated(tmp_path)
    r = build_isolated(data_dir, templates_dir, out)
    assert r.returncode == 0, f"current sop_version must pass: {r.stderr[-2000:]}"
    assert (out / "cyborg.html").exists()
