"""#19 E2E seam: 测试数据清空回到干净起点.

Seams under test (per #16 Notes: E2E only):
- `python scripts/build.py --all` exit codes + `docs/index.html` bytes
- `data/builds/*.json` bytes (must be 0) + `docs/*.html` bytes (no char pages)

No internal imports, no network.
"""

from __future__ import annotations

import json
import re
import subprocess
import sys
from pathlib import Path

REPO = Path(__file__).resolve().parent.parent
BUILD = [sys.executable, "scripts/build.py"]


def run_build(*args: str, cwd: Path = REPO) -> subprocess.CompletedProcess[str]:
    return subprocess.run([*BUILD, *args], cwd=cwd, capture_output=True, text=True)


def test_builds_dir_is_empty_clean_slate() -> None:
    """干净起点: data/builds 无测试数据 (0 json)."""
    builds = list((REPO / "data" / "builds").glob("*.json"))
    assert builds == [], f"data/builds must be empty after #19, got {[p.name for p in builds]}"


def test_no_char_pages_only_index() -> None:
    """干净起点: docs 无旧角色页, 只有索引."""
    assert not (REPO / "docs" / "cyborg.html").exists(), "docs/cyborg.html must be deleted (#19)"
    assert not (REPO / "docs" / "engineer.html").exists(), "docs/engineer.html must be deleted (#19)"
    assert (REPO / "docs" / "index.html").exists(), "docs/index.html must exist (rebuilt 0 clickable)"


def test_index_zero_clickable_no_dead_links() -> None:
    """重建索引 0 可点: 64 全量, playable 全 0, 无死链, 全能力骨架仍在."""
    r = run_build("--all")
    assert r.returncode == 0, f"build --all must pass on empty slate: {r.stderr[-2000:]}"
    html = (REPO / "docs" / "index.html").read_text(encoding="utf-8")
    assert "GENERATED" in html and "scripts/build.py" in html
    m = re.search(r"var ROSTER\s*=\s*(\[.*?\]);", html, re.S)
    assert m is not None, "index must inline var ROSTER for file:// filtering"
    roster = json.loads(m.group(1))
    assert len(roster) == 64, f"ROSTER must stay 64, got {len(roster)}"
    playable = [e for e in roster if e.get("playable")]
    assert playable == [], f"0 clickable after clean, got {[e.get('slug') for e in playable]}"
    for slug in ("cyborg", "engineer", "mage", "sailor", "ranger"):
        assert f"./{slug}.html" not in html, f"unbuilt {slug} must not link (no dead page)"
    for needle in ('id="q"', 'id="dlc"', 'id="playable"', 'id="count"', "🥔"):
        assert needle in html, f"index full ability skeleton must remain ({needle})"
    assert '<meta name="viewport"' in html
    assert "fetch(" not in html
