"""#10 E2E seam: roster 64 + terms 17+22 single-source.

Seams under test (pre-agreed per #8: E2E only):
- `python scripts/build.py --slug <slug>` / `--all` exit codes + `docs/*.html` bytes
- `python scripts/check.py <html>` exit codes
- `python scripts/check_updates.py` append-rule exit codes

No internal imports, no network. All assertions inspect CLI exit codes
and generated file bytes.
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
    # Dispatch: build vs check vs check_updates share same helper.
    if args and args[0].endswith("check_updates.py"):
        cmd = [sys.executable, *args]
    elif args and args[0].endswith("check.py"):
        cmd = [sys.executable, *args]
    else:
        cmd = [*BUILD, *args]
    return subprocess.run(cmd, cwd=cwd, capture_output=True, text=True)


def run_build(*args: str, cwd: Path = REPO) -> subprocess.CompletedProcess[str]:
    return subprocess.run([*BUILD, *args], cwd=cwd, capture_output=True, text=True)


def test_roster_64_dlc_14_mod_rejected() -> None:
    """名录 64 齐全，DLC 14 归属正确，Mod 拒收。"""
    roster = json.loads((REPO / "data" / "roster.json").read_text(encoding="utf-8"))
    assert len(roster) == 64, f"roster must be 64, got {len(roster)}"
    abyssal = [r for r in roster if r.get("dlc") == "abyssal"]
    assert len(abyssal) == 14, f"DLC 14 required, got {len(abyssal)}"
    ids = [r.get("id") for r in roster]
    assert len(set(ids)) == 64
    # Mod 拒收：未知 slug 即 fail。
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
    # 旧口径作废：次级只有 3 行（Explosion/Reroll/XP）必须被拒。
    # 用隔离夹具把 terms 截成旧 3 口径，构建必须 fail。
    import tempfile

    with tempfile.TemporaryDirectory() as tmp:
        work = Path(tmp) / "work"
        shutil.copytree(REPO / "data", work / "data")
        shutil.copytree(REPO / "templates", work / "templates")
        out = Path(tmp) / "out"
        old_secondary = {"Explosion Damage", "Reroll Price", "XP Gain"}
        kept = [r for r in rows if not (r["type"] == "secondary" and r["en"] not in old_secondary)]
        # kept secondary should be exactly old 3 if source were old; here we force old shape
        # by keeping only those 3 (map % Reroll Price -> Reroll Price for old check)
        # Instead: truncate to first 3 secondary to simulate old caliber.
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
        out = Path(tmp) / "out"
        build_file = work / "data" / "builds" / "cyborg.json"
        data = json.loads(build_file.read_text(encoding="utf-8"))
        ratings = data.get("ratings")
        assert isinstance(ratings, dict), "cyborg.json must use single-source ratings"
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
        out = Path(tmp) / "out"
        # 把 Curse 的 dlc 置空，模拟角标缺失。
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


def test_pending_only_warns_not_fail() -> None:
    """待校对只 warn 加标：全量待校对仍可发布。"""
    r = run_build("--slug", "cyborg")
    assert r.returncode == 0, f"pending must not fail: {r.stderr[-2000:]}"
    combined = r.stdout + r.stderr
    assert "WARN" in combined or "待校对" in combined or "※" in combined
    html = (REPO / "docs" / "cyborg.html").read_text(encoding="utf-8")
    assert "※" in html or "待校对" in html


def test_cyborg_rerendered_full_not_demo() -> None:
    """同一单角色页重渲染后角标排序图标正确，非演示拷贝。"""
    r = run_build("--slug", "cyborg")
    assert r.returncode == 0, r.stderr[-2000:]
    html = (REPO / "docs" / "cyborg.html").read_text(encoding="utf-8")
    # 主 17 + 次级 22 全量，非演示 5+3。
    # 按 data-section 切出两表，数行数（每行一个中文括号英文）。
    primary_sec = re.search(r'data-section="attrs-primary".*?</section>', html, re.S)
    secondary_sec = re.search(r'data-section="attrs-secondary".*?</section>', html, re.S)
    assert primary_sec is not None and secondary_sec is not None
    # 主表英文名按 wiki 原序出现。
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
    # DLC 角标：诅咒与重随价格必须带 DLC 标记。
    assert "Curse" in primary_sec.group(0)
    assert "DLC" in primary_sec.group(0), "Curse DLC badge missing"
    assert "Reroll Price" in secondary_sec.group(0)
    assert "DLC" in secondary_sec.group(0), "Reroll Price DLC badge missing"
    # 图标：主表有 wiki 热链图标，次级统一占位 ◆。
    assert "wiki.spellsandguns.com" in html, "stat icons must be inlined from registry"
    assert "◆" in html, "secondary placeholder ◆ required"


def test_registry_is_single_url_source() -> None:
    """缓存注册表为唯一 URL 源，不存二进制，构建时内联。"""
    reg_path = REPO / "data" / "wiki-cache.json"
    assert reg_path.exists(), "data/wiki-cache.json must exist"
    reg = json.loads(reg_path.read_text(encoding="utf-8"))
    assert "stats" in reg
    # 主 17 必须有 thumb，次级 22 必须 missing 占位。
    for en in EXPECTED_PRIMARY:
        assert en in reg["stats"], f"registry missing {en}"
        entry = reg["stats"][en]
        assert entry.get("thumb"), f"primary {en} must have thumb"
        assert "wiki.spellsandguns.com" in entry["thumb"]
    for en in EXPECTED_SECONDARY:
        assert en in reg["stats"], f"registry missing {en}"
        entry = reg["stats"][en]
        assert entry.get("missing") or not entry.get("thumb"), f"secondary {en} must be placeholder"
    # 不存二进制：仓库无 png 二进制入库（assets 为空或仅 .gitkeep）。
    assets = REPO / "assets"
    if assets.exists():
        pngs = list(assets.rglob("*.png"))
        assert pngs == [], "no binary png in repo, registry only"
    # 构建时内联：产物无运行时 fetch，file:// 可开。
    html = (REPO / "docs" / "cyborg.html").read_text(encoding="utf-8")
    assert "fetch(" not in html
    assert "wiki.spellsandguns.com" in html


def test_append_rule_uncalibrated_not_published() -> None:
    """追加规则可用：未校对不发布，Mod 永不进入。"""
    # check_updates.py 必须存在且可跑（默认全量校验）。
    r = subprocess.run([*CHECK_UPDATES], cwd=REPO, capture_output=True, text=True)
    assert r.returncode == 0, f"check_updates baseline must pass: {r.stderr[-2000:]}"
    # 未校对新增：用隔离 roster 加一个 needs_review=true 的新角色，必须 fail。
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
