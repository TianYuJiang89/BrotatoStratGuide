"""#11 E2E seam: 索引全能力 搜索筛选头像回落.

Seams under test (pre-agreed per #8: E2E only):
- `python scripts/build.py --all` / `--slug` exit codes + `docs/index.html` bytes
- `data/wiki-cache.json` bytes (chars registry is single URL source)

No internal imports, no network. All assertions inspect CLI exit codes,
data file bytes, and generated file bytes.

#19 clean slate: repo index is 0 clickable. Playable assertions updated to 0.
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


def read_index() -> str:
    return (REPO / "docs" / "index.html").read_text(encoding="utf-8")


def extract_roster(html: str) -> list[dict]:
    m = re.search(r"var ROSTER\s*=\s*(\[.*?\]);", html, re.S)
    assert m is not None, "index must inline var ROSTER = [...] for file:// filtering"
    data = json.loads(m.group(1))
    assert isinstance(data, list)
    return data


def norm(s: str) -> str:
    """Mirror of index JS norm(): lower + strip spaces/hyphens/underscores."""
    return re.sub(r"[\s\-_]+", "", s.lower())


def initials(en: str) -> str:
    parts = re.split(r"[\s\-_]+", en)
    return "".join(p[0].lower() for p in parts if p)


def hay(entry: dict) -> str:
    slug = str(entry.get("slug", ""))
    slug_nodash = re.sub(r"[-_]+", "", slug)
    abbr = str(entry.get("abbr", "") or initials(str(entry.get("en", ""))))
    return norm(
        f"{entry.get('zh','')} {entry.get('en','')} {slug} {slug_nodash} {abbr}"
    )


def matches(entry: dict, query: str) -> bool:
    q = norm(query)
    if not q:
        return True
    return q in hay(entry)


def test_index_build_all_runs_and_covers_64() -> None:
    """覆盖 64 索引构建可跑：--all 成功，ROSTER 64，静态卡 64。"""
    r = run_build("--all")
    assert r.returncode == 0, f"build --all failed: {r.stderr[-2000:]}"
    html = read_index()
    roster = extract_roster(html)
    assert len(roster) == 64, f"ROSTER must be 64, got {len(roster)}"
    cards = re.findall(r'class="card"', html)
    assert len(cards) >= 64, f"static cards must cover 64, got {len(cards)}"


def test_search_fuzzy_zh_en_abbr_and_count_empty() -> None:
    """搜索模糊命中中英文与缩写，计数与空状态正确。"""
    r = run_build("--all")
    assert r.returncode == 0, r.stderr[-2000:]
    html = read_index()
    assert 'id="q"' in html, "search input #q required"
    assert 'id="count"' in html, "hit count #count required"
    assert 'id="grid"' in html, "grid #grid required"
    assert "当前命中" in html, "count must show 命中"
    assert "没有命中" in html, "empty state required"
    roster = extract_roster(html)
    by_slug = {e["slug"]: e for e in roster}
    hits = [e for e in roster if matches(e, "赛博")]
    assert "cyborg" in {e["slug"] for e in hits}, "zh fuzzy must hit cyborg"
    assert matches(by_slug["cyborg"], "CYBORG")
    assert matches(by_slug["cyborg"], "cyb")
    assert matches(by_slug["one-armed"], "onearmed")
    assert matches(by_slug["one-armed"], "One-Armed")
    assert matches(by_slug["beast-master"], "bm"), "abbr bm must hit beast-master"
    assert matches(by_slug["well-rounded"], "wr"), "abbr wr must hit well-rounded"
    assert matches(by_slug["cyborg"], "c"), "single-letter abbr must hit"
    assert [e for e in roster if matches(e, "不存在的角色zzz")] == []
    assert "ROSTER" in html and "norm" in html


def test_dlc_filter_and_playable_no_dead_links() -> None:
    """DLC 筛选与仅看可点正确，不点进空页 (#25: 1可点 cyborg)."""
    r = run_build("--all")
    assert r.returncode == 0, r.stderr[-2000:]
    html = read_index()
    assert 'id="dlc"' in html
    for val in ('value="all"', 'value="base"', 'value="abyssal"'):
        assert val in html, f"DLC filter missing {val}"
    assert "仅本体" in html and "Abyssal" in html
    assert 'id="playable"' in html and "仅看可点" in html
    roster = extract_roster(html)
    base = [e for e in roster if not e.get("dlc")]
    abyssal = [e for e in roster if e.get("dlc") == "abyssal"]
    assert len(base) == 50, f"base 50 required, got {len(base)}"
    assert len(abyssal) == 14, f"abyssal 14 required, got {len(abyssal)}"
    playable = [e for e in roster if e.get("playable")]
    assert [e.get("slug") for e in playable] == ["cyborg"], f"#25 must be 1 playable cyborg, got {[e.get('slug') for e in playable]}"
    # 可点才有链: 已建 cyborg 有链, 未建无死链.
    assert "./cyborg.html" in html, "built cyborg must link"
    for slug in ("engineer", "mage", "sailor", "ranger"):
        assert f'./{slug}.html' not in html, f"unbuilt {slug} must not link (no dead page)"
    assert 'value="all"' in html
    assert "playable" in html


def test_avatar_hotlink_with_fallback() -> None:
    """头像正常显示，断网回落占位仍可读。"""
    r = run_build("--all")
    assert r.returncode == 0, r.stderr[-2000:]
    html = read_index()
    roster = extract_roster(html)
    for e in roster:
        img = str(e.get("img", ""))
        assert img.startswith("https://"), f"{e.get('slug')} img must be URL"
        assert "wiki.spellsandguns.com" in img, f"{e.get('slug')} img must be wiki hotlink"
        assert "60px-" in img, f"{e.get('slug')} img must be 60px thumbnail"
    assert 'loading="lazy"' in html
    assert 'referrerpolicy="no-referrer"' in html
    assert 'onerror="this.remove()"' in html
    assert "🥔" in html
    reg = json.loads((REPO / "data" / "wiki-cache.json").read_text(encoding="utf-8"))
    assert "chars" in reg, "registry must grow chars map (single URL source)"
    assert len(reg["chars"]) == 64, f"chars 64 required, got {len(reg['chars'])}"
    sample = reg["chars"].get("Cyborg")
    assert sample is not None and "wiki.spellsandguns.com" in sample.get("thumb", "")
    assets = REPO / "assets"
    if assets.exists():
        assert list(assets.rglob("*.png")) == [], "no binary png in repo, registry only"


def test_index_file_double_click_runnable() -> None:
    """file 双击可跑：无 fetch/外链阻塞，生成标记 (#25: 1可点有角色链)."""
    r = run_build("--all")
    assert r.returncode == 0, r.stderr[-2000:]
    html = read_index()
    assert "<html" in html and "</html>" in html
    assert "fetch(" not in html
    assert 'rel="stylesheet" href="http' not in html
    assert '<script src="http' not in html
    # 1可点有角色链, 但索引自身可读.
    assert "./cyborg.html" in html, "cyborg built must link"
    assert "GENERATED" in html and "scripts/build.py" in html
    assert '<meta name="viewport"' in html
    assert "max-width" in html


def test_per_slug_build_also_refreshes_index() -> None:
    """#25 1可点: --slug cyborg 必过; 未知 slug 必 fail; --all 仍 64 全量."""
    r = run_build("--slug", "cyborg")
    assert r.returncode == 0, f"cyborg built must pass: {r.stderr[-2000:]}"
    r_miss = run_build("--slug", "mage")
    assert r_miss.returncode != 0, "missing build mage must fail"
    r2 = run_build("--all")
    assert r2.returncode == 0, r2.stderr[-2000:]
    html = read_index()
    roster = extract_roster(html)
    assert len(roster) == 64
    assert 'id="q"' in html and 'id="dlc"' in html and 'id="playable"' in html
