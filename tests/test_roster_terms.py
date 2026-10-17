"""#10 E2E seam: roster 64 + terms 17+22 single-source.

Seams under test (pre-agreed per #8: E2E only):
- `python scripts/build.py --slug <slug>` / `--all` exit codes + `docs/*.html` bytes
- `python scripts/check.py <html>` exit codes
- `python scripts/check_updates.py` append-rule exit codes

No internal imports, no network. All assertions inspect CLI exit codes
and generated file bytes.

#19 clean slate: rendering via isolated tmp fixture (tests/fixtures/cyborg.json).
"""

from __future__ import annotations

import csv
import json
import re
import shutil
import subprocess
import sys
from pathlib import Path

REPO = Path(__file__).resolve().parent.parent
BUILD = [sys.executable, "scripts/build.py"]
CHECK = [sys.executable, "scripts/check.py"]
CHECK_UPDATES = [sys.executable, "scripts/check_updates.py"]
FIXTURE = REPO / "tests" / "fixtures" / "cyborg.json"

EXPECTED_PRIMARY = [
    "Max HP",
    "HP Regeneration",
    "Life Steal",
    "Damage",
    "Melee Damage",
    "Ranged Damage",
    "Elemental Damage",
    "Attack Speed",
    "Crit Chance",
    "Engineering",
    "Range",
    "Armor",
    "Dodge",
    "Speed",
    "Luck",
    "Harvesting",
    "Curse",
]

EXPECTED_SECONDARY = [
    "Consumable Heal",
    "% Materials Healing",
    "% XP Gain",
    "% Pickup Range",
    "% Items Price",
    "% Explosion Damage",
    "% Explosion Size",
    "Bounces",
    "Piercing",
    "% Piercing Damage",
    "% Damage against Bosses",
    "% Structure Attack Speed",
    "Structure Range",
    "% Burning Speed",
    "Burning Spread",
    "Knockback",
    "% Double Material Chance",
    "Free Rerolls",
    "Trees",
    "% Enemies",
    "% Enemy Speed",
    "% Reroll Price",
]


def run(*args: str, cwd: Path = REPO) -> subprocess.CompletedProcess[str]:
    if args and args[0].endswith("check_updates.py"):
        cmd = [sys.executable, *args]
    elif args and args[0].endswith("check.py"):
        cmd = [sys.executable, *args]
    else:
        cmd = [*BUILD, *args]
    return subprocess.run(cmd, cwd=cwd, capture_output=True, text=True)


def run_build(*args: str, cwd: Path = REPO) -> subprocess.CompletedProcess[str]:
    return subprocess.run([*BUILD, *args], cwd=cwd, capture_output=True, text=True)


def ensure_fixture(work: Path) -> None:
    _bf = work / "data" / "builds" / "cyborg.json"
    # #23: repo已有真数据，隔离缝一律用夹具覆盖。
    if FIXTURE.exists():
        _bf.parent.mkdir(parents=True, exist_ok=True)
        _bf.write_text(FIXTURE.read_text(encoding="utf-8"), encoding="utf-8")


def build_isolated(data_dir: Path, templates_dir: Path, out: Path) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        [sys.executable, str(REPO / "scripts" / "build.py"), "--slug", "cyborg",
         "--data-dir", str(data_dir), "--templates-dir", str(templates_dir),
         "--out-dir", str(out)],
        cwd=REPO, capture_output=True, text=True,
    )


def test_roster_64_dlc_14_mod_rejected() -> None:
    """名录 64 齐全，DLC 14 归属正确，Mod 拒收。"""
    roster = json.loads((REPO / "data" / "roster.json").read_text(encoding="utf-8"))
    assert len(roster) == 64, f"roster must be 64, got {len(roster)}"
    abyssal = [r for r in roster if r.get("dlc") == "abyssal"]
    assert len(abyssal) == 14, f"DLC 14 required, got {len(abyssal)}"
    ids = [r.get("id") for r in roster]
    assert len(set(ids)) == 64
    r = run_build("--slug", "mod-fake-character")
    assert r.returncode != 0, "Mod/unknown slug must fail"
    combined = (r.stdout + r.stderr).lower()
    assert "unknown" in combined or "mod" in combined or "missing" in combined


def test_terms_primary_17_secondary_22_wiki_order() -> None:
    """术语主次全量拆两表，原序正确，旧次级 3 口径作废。"""
    terms_path = REPO / "data" / "terms.csv"
    assert terms_path.exists(), "data/terms.csv must exist"
    with terms_path.open(encoding="utf-8") as f:
        rows = list(csv.DictReader(f))
    primary = [r for r in rows if r["type"] == "primary"]
    secondary = [r for r in rows if r["type"] == "secondary"]
    assert len(primary) == 17, f"primary 17 required, got {len(primary)}"
    assert len(secondary) == 22, f"secondary 22 required, got {len(secondary)}"
    assert [r["en"] for r in primary] == EXPECTED_PRIMARY
    assert [r["en"] for r in secondary] == EXPECTED_SECONDARY
    import tempfile

    with tempfile.TemporaryDirectory() as tmp:
        work = Path(tmp) / "work"
        shutil.copytree(REPO / "data", work / "data")
        shutil.copytree(REPO / "templates", work / "templates")
        ensure_fixture(work)
        out = Path(tmp) / "out"
        prim = [r for r in rows if r["type"] == "primary"]
        sec = [r for r in rows if r["type"] == "secondary"][:3]
        with (work / "data" / "terms.csv").open("w", encoding="utf-8", newline="") as f:
            w = csv.DictWriter(f, fieldnames=["en", "zh", "type", "dlc", "source_version", "needs_review"])
            w.writeheader()
            w.writerows(prim + sec)
        r = subprocess.run(
            [sys.executable, str(REPO / "scripts" / "build.py"), "--slug", "cyborg",
             "--data-dir", str(work / "data"), "--templates-dir", str(work / "templates"),
             "--out-dir", str(out)],
            cwd=REPO, capture_output=True, text=True,
        )
        assert r.returncode != 0, "old secondary-3 caliber must fail"


def test_unknown_term_fails() -> None:
    """术语对不上即 fail：ratings 出现未知英文必须失败。"""
    import tempfile

    with tempfile.TemporaryDirectory() as tmp:
        work = Path(tmp) / "work"
        shutil.copytree(REPO / "data", work / "data")
        shutil.copytree(REPO / "templates", work / "templates")
        ensure_fixture(work)
        out = Path(tmp) / "out"
        build_file = work / "data" / "builds" / "cyborg.json"
        data = json.loads(build_file.read_text(encoding="utf-8"))
        assert isinstance(data.get("variants"), list) and data["variants"]
        ratings = data["variants"][0].get("ratings")
        assert isinstance(ratings, dict), "cyborg.json variants[0] must use single-source ratings"
        ratings["Fake Stat That Does Not Exist"] = {"rating": "S", "note": "造假"}
        build_file.write_text(json.dumps(data, ensure_ascii=False), encoding="utf-8")
        r = subprocess.run(
            [sys.executable, str(REPO / "scripts" / "build.py"), "--slug", "cyborg",
             "--data-dir", str(work / "data"), "--templates-dir", str(work / "templates"),
             "--out-dir", str(out)],
            cwd=REPO, capture_output=True, text=True,
        )
        assert r.returncode != 0, "unknown term must fail"
        combined = (r.stdout + r.stderr).lower()
        assert "fake" in combined or "unknown" in combined or "mismatch" in combined or "术语" in combined


def test_missing_dlc_badge_fails() -> None:
    """角标缺失即 fail：DLC 术语缺 dlc 标记必须失败。"""
    import tempfile

    with tempfile.TemporaryDirectory() as tmp:
        work = Path(tmp) / "work"
        shutil.copytree(REPO / "data", work / "data")
        shutil.copytree(REPO / "templates", work / "templates")
        ensure_fixture(work)
        out = Path(tmp) / "out"
        terms_path = work / "data" / "terms.csv"
        with terms_path.open(encoding="utf-8") as f:
            rows = list(csv.DictReader(f))
        for row in rows:
            if row["en"] == "Curse":
                row["dlc"] = ""
        with terms_path.open("w", encoding="utf-8", newline="") as f:
            w = csv.DictWriter(f, fieldnames=["en", "zh", "type", "dlc", "source_version", "needs_review"])
            w.writeheader()
            w.writerows(rows)
        r = subprocess.run(
            [sys.executable, str(REPO / "scripts" / "build.py"), "--slug", "cyborg",
             "--data-dir", str(work / "data"), "--templates-dir", str(work / "templates"),
             "--out-dir", str(out)],
            cwd=REPO, capture_output=True, text=True,
        )
        assert r.returncode != 0, "missing DLC badge must fail"


def test_pending_only_warns_not_fail(tmp_path: Path) -> None:
    """待校对只 warn 加标：全量待校对仍可发布 (隔离)."""
    import shutil

    work = tmp_path / "work"
    shutil.copytree(REPO / "data", work / "data")
    shutil.copytree(REPO / "templates", work / "templates")
    ensure_fixture(work)
    out = tmp_path / "out"
    out.mkdir(parents=True, exist_ok=True)
    r = build_isolated(work / "data", work / "templates", out)
    assert r.returncode == 0, f"pending must not fail: {r.stderr[-2000:]}"
    combined = r.stdout + r.stderr
    assert "WARN" in combined or "待校对" in combined or "※" in combined
    html = (out / "cyborg.html").read_text(encoding="utf-8")
    assert "※" in html or "待校对" in html


def test_cyborg_rerendered_full_not_demo(tmp_path: Path) -> None:
    """同一单角色页重渲染后角标排序图标正确，非演示拷贝 (隔离)."""
    import shutil

    work = tmp_path / "work"
    shutil.copytree(REPO / "data", work / "data")
    shutil.copytree(REPO / "templates", work / "templates")
    ensure_fixture(work)
    out = tmp_path / "out"
    out.mkdir(parents=True, exist_ok=True)
    r = build_isolated(work / "data", work / "templates", out)
    assert r.returncode == 0, r.stderr[-2000:]
    html = (out / "cyborg.html").read_text(encoding="utf-8")
    primary_sec = re.search(r'data-section="attrs-primary".*?</section>', html, re.S)
    secondary_sec = re.search(r'data-section="attrs-secondary".*?</section>', html, re.S)
    assert primary_sec is not None and secondary_sec is not None
    positions = []
    for en in EXPECTED_PRIMARY:
        idx = primary_sec.group(0).find(f"({en})")
        assert idx >= 0, f"primary {en} missing in rendered page"
        positions.append(idx)
    assert positions == sorted(positions), "primary must follow wiki order"
    positions2 = []
    for en in EXPECTED_SECONDARY:
        idx = secondary_sec.group(0).find(f"({en})")
        assert idx >= 0, f"secondary {en} missing in rendered page"
        positions2.append(idx)
    assert positions2 == sorted(positions2), "secondary must follow wiki order"
    assert "Curse" in primary_sec.group(0)
    assert "DLC" in primary_sec.group(0), "Curse DLC badge missing"
    assert "Reroll Price" in secondary_sec.group(0)
    assert "DLC" in secondary_sec.group(0), "Reroll Price DLC badge missing"
    assert "wiki.spellsandguns.com" in html, "stat icons must be inlined from registry"
    assert "◆" in html, "secondary placeholder ◆ required"


def test_registry_is_single_url_source(tmp_path: Path) -> None:
    """缓存注册表为唯一 URL 源，不存二进制，构建时内联 (隔离产物)."""
    reg_path = REPO / "data" / "wiki-cache.json"
    assert reg_path.exists(), "data/wiki-cache.json must exist"
    reg = json.loads(reg_path.read_text(encoding="utf-8"))
    assert "stats" in reg
    for en in EXPECTED_PRIMARY:
        assert en in reg["stats"], f"registry missing {en}"
        entry = reg["stats"][en]
        assert entry.get("thumb"), f"primary {en} must have thumb"
        assert "wiki.spellsandguns.com" in entry["thumb"]
    for en in EXPECTED_SECONDARY:
        assert en in reg["stats"], f"registry missing {en}"
        entry = reg["stats"][en]
        assert entry.get("missing") or not entry.get("thumb"), f"secondary {en} must be placeholder"
    assets = REPO / "assets"
    if assets.exists():
        pngs = list(assets.rglob("*.png"))
        assert pngs == [], "no binary png in repo, registry only"
    import shutil

    work = tmp_path / "work"
    shutil.copytree(REPO / "data", work / "data")
    shutil.copytree(REPO / "templates", work / "templates")
    ensure_fixture(work)
    out = tmp_path / "out"
    out.mkdir(parents=True, exist_ok=True)
    r = build_isolated(work / "data", work / "templates", out)
    assert r.returncode == 0, r.stderr[-2000:]
    html = (out / "cyborg.html").read_text(encoding="utf-8")
    assert "fetch(" not in html
    assert "wiki.spellsandguns.com" in html


def test_append_rule_uncalibrated_not_published() -> None:
    """追加规则可用：未校对不发布，Mod 永不进入。"""
    r = subprocess.run([*CHECK_UPDATES], cwd=REPO, capture_output=True, text=True)
    assert r.returncode == 0, f"check_updates baseline must pass: {r.stderr[-2000:]}"
    import tempfile

    with tempfile.TemporaryDirectory() as tmp:
        work = Path(tmp) / "work"
        shutil.copytree(REPO / "data", work / "data")
        roster = json.loads((work / "data" / "roster.json").read_text(encoding="utf-8"))
        roster.append({"id": "primal-test", "en": "Primal Test", "zh": "测试", "dlc": "primal", "needs_review": True})
        (work / "data" / "roster.json").write_text(json.dumps(roster, ensure_ascii=False), encoding="utf-8")
        r2 = subprocess.run(
            [sys.executable, str(REPO / "scripts" / "check_updates.py"),
             "--data-dir", str(work / "data")],
            cwd=REPO, capture_output=True, text=True,
        )
        assert r2.returncode != 0, "uncalibrated append must fail"


def test_attr_tooltip_three_columns_and_flips_up_near_bottom(tmp_path: Path) -> None:
    """属性 hover：3 列排版 + 靠底向上，不滚 (隔离产物)."""
    import shutil

    work = tmp_path / "work"
    shutil.copytree(REPO / "data", work / "data")
    shutil.copytree(REPO / "templates", work / "templates")
    ensure_fixture(work)
    out = tmp_path / "out"
    out.mkdir(parents=True, exist_ok=True)
    r = build_isolated(work / "data", work / "templates", out)
    assert r.returncode == 0, r.stderr[-2000:]
    tpl = (REPO / "templates" / "character.html").read_text(encoding="utf-8")
    assert "repeat(3" in tpl, "tooltip must use 3-column grid"
    assert "bottom:100%" in tpl, "bottom rows must flip upward"
    assert "nth-last-child" in tpl, "only near-bottom rows flip upward"
    tip_blocks = re.findall(r"\.tip\s*\{[^}]*\}", tpl)
    assert tip_blocks, "tooltip css must exist"
    for block in tip_blocks:
        assert "overflow" not in block or "visible" in block, f"tooltip must not scroll: {block}"
    html = (out / "cyborg.html").read_text(encoding="utf-8")
    assert 'class="tip"' in html
    assert 'class="tm"' in html, "more-count line must span full grid row"
