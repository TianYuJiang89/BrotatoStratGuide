"""#15 E2E seam: weapons + key items hover with wiki本体信息 + 中英对照.

Seams under test (pre-agreed per #8: E2E only):
- `python scripts/build.py --slug <slug>` exit codes + `docs/*.html` bytes
- `python scripts/check.py <html>` exit codes
- `data/wiki-cache.json` bytes (registry is single URL source)

No internal imports, no network. All assertions inspect CLI exit codes,
data file bytes, and generated file bytes.
"""

from __future__ import annotations

import json
import re
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path

REPO = Path(__file__).resolve().parent.parent
BUILD = [sys.executable, "scripts/build.py"]
CHECK = [sys.executable, "scripts/check.py"]

FIRST_BATCH_ITEMS = ["Improved Tools", "Turret", "Coffee", "Big Arms"]
FIRST_BATCH_WEAPONS = ["SMG", "Pistol", "Minigun"]


def run_build(*args: str, cwd: Path = REPO) -> subprocess.CompletedProcess[str]:
    return subprocess.run([*BUILD, *args], cwd=cwd, capture_output=True, text=True)


def make_workdir() -> tuple[Path, Path, Path, tempfile.TemporaryDirectory[str]]:
    """Isolated data/templates/out copy. Caller must cleanup tmp."""
    tmp = tempfile.TemporaryDirectory()
    work = Path(tmp.name) / "work"
    shutil.copytree(REPO / "data", work / "data")
    shutil.copytree(REPO / "templates", work / "templates")
    # #19 clean slate: repo data/builds empty, restore fixture for isolated seam.
    _fx = REPO / "tests" / "fixtures" / "cyborg.json"
    _bf = work / "data" / "builds" / "cyborg.json"
    if not _bf.exists() and _fx.exists():
        _bf.parent.mkdir(parents=True, exist_ok=True)
        _bf.write_text(_fx.read_text(encoding="utf-8"), encoding="utf-8")
    out = Path(tmp.name) / "out"
    return (work / "data", work / "templates", out, tmp)


def build_fixture(data_dir: Path, templates_dir: Path, out: Path) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        [*BUILD, "--slug", "cyborg",
         "--data-dir", str(data_dir),
         "--templates-dir", str(templates_dir),
         "--out-dir", str(out)],
        cwd=REPO, capture_output=True, text=True,
    )


def test_registry_has_items_and_weapons_single_source() -> None:
    """注册表为唯一源：items/weapons 首批 7 条齐全，URL 集中，不存二进制。"""
    reg = json.loads((REPO / "data" / "wiki-cache.json").read_text(encoding="utf-8"))
    assert "items" in reg and "weapons" in reg, "registry must grow items/weapons maps"
    for en in FIRST_BATCH_ITEMS:
        assert en in reg["items"], f"registry items missing {en}"
        entry = reg["items"][en]
        assert entry.get("thumb", "").startswith("https://"), f"{en} thumb must be URL"
        assert "wiki.spellsandguns.com" in entry["thumb"], f"{en} thumb must be wiki hotlink"
        assert "wiki.spellsandguns.com" in entry.get("page", ""), f"{en} page must be wiki URL"
        for field in ("tier", "effects", "price", "unlock", "tags"):
            assert field in entry, f"items schema must lock full columns ({en} missing {field})"
    for en in FIRST_BATCH_WEAPONS:
        assert en in reg["weapons"], f"registry weapons missing {en}"
        entry = reg["weapons"][en]
        assert entry.get("thumb", "").startswith("https://"), f"{en} thumb must be URL"
        assert "wiki.spellsandguns.com" in entry.get("page", ""), f"{en} page must be wiki URL"
    # 不存二进制：thumb 全是 URL 字符串，仓库无新增二进制。
    assets = REPO / "assets"
    if assets.exists():
        assert list(assets.rglob("*.png")) == [], "no binary png in repo, registry only"


def test_cyborg_weapons_items_render_hover() -> None:
    """赛博格页武器道具名可悬浮：有本体信息 hover，英文必填，缺中文只英文加标 (隔离夹具)."""
    data_dir, templates_dir, out, tmp = make_workdir()
    try:
        r = build_fixture(data_dir, templates_dir, out)
        assert r.returncode == 0, f"build failed: {r.stderr[-2000:]}"
        html = (out / "cyborg.html").read_text(encoding="utf-8")
        for section in ("weapons", "items"):
            m = re.search(rf'data-section="{section}".*?</section>', html, re.S)
            assert m is not None
            assert "has-tip" in m.group(0), f"{section} names must carry hover"
            assert 'class="tip"' in m.group(0), f"{section} hover body must reuse .tip"
        # 武器 hover 含本体列，道具 hover 含 Tier。
        assert "Gun" in html, "SMG/Pistol hover must show wiki Class"
        assert "Tier 1" in html, "Coffee/Turret hover must show wiki Tier"
        # 中英对照：术语名中文括号英文；缺中文只英文但挂待校对标。
        assert "※" in html or "待校对" in html
    finally:
        tmp.cleanup()


def test_big_arms_schema_example_renders_all_fields() -> None:
    """Big Arms 为 schema 例：7 列全对，负值保留红绿语义。"""
    data_dir, templates_dir, out, tmp = make_workdir()
    try:
        build_file = data_dir / "builds" / "cyborg.json"
        data = json.loads(build_file.read_text(encoding="utf-8"))
        assert isinstance(data.get("variants"), list) and data["variants"]
        variant = data["variants"][0]
        variant["items"] = [*variant["items"], {"name_en": "Big Arms", "reason": "schema 例"}]
        build_file.write_text(json.dumps(data, ensure_ascii=False), encoding="utf-8")
        r = build_fixture(data_dir, templates_dir, out)
        assert r.returncode == 0, f"fixture build failed: {r.stderr[-2000:]}"
        html = (out / "cyborg.html").read_text(encoding="utf-8")
        m = re.search(r'data-section="items".*?</section>', html, re.S)
        assert m is not None
        sec = m.group(0)
        assert "Big Arms" in sec
        assert "Tier 4" in sec
        assert "105" in sec, "base price must render"
        assert "Generalist" in sec, "unlock must render"
        assert "Melee Damage" in sec and "Ranged Damage" in sec, "tags must render"
        # 术语对照：近战伤害 (Melee Damage)。
        assert "近战伤害" in sec and "(Melee Damage)" in sec
        # 负值红色、正值绿色（wiki 原样语义）。
        assert "neg" in sec and "pos" in sec
    finally:
        tmp.cleanup()


def test_unknown_weapon_fails() -> None:
    """机检：未知武器即 fail。"""
    data_dir, templates_dir, out, tmp = make_workdir()
    try:
        build_file = data_dir / "builds" / "cyborg.json"
        data = json.loads(build_file.read_text(encoding="utf-8"))
        assert isinstance(data.get("variants"), list) and data["variants"]
        variant = data["variants"][0]
        variant["weapons_t1"] = [*variant["weapons_t1"], {"name_en": "Fake Gun", "note": "造假"}]
        build_file.write_text(json.dumps(data, ensure_ascii=False), encoding="utf-8")
        r = build_fixture(data_dir, templates_dir, out)
        assert r.returncode != 0, "unknown weapon must fail"
        combined = (r.stdout + r.stderr).lower()
        assert "fake gun" in combined or "unknown" in combined or "未知" in combined
    finally:
        tmp.cleanup()


def test_unknown_item_fails() -> None:
    """机检：未知道具即 fail。"""
    data_dir, templates_dir, out, tmp = make_workdir()
    try:
        build_file = data_dir / "builds" / "cyborg.json"
        data = json.loads(build_file.read_text(encoding="utf-8"))
        assert isinstance(data.get("variants"), list) and data["variants"]
        variant = data["variants"][0]
        variant["items"] = [*variant["items"], {"name_en": "Fake Trinket", "reason": "造假"}]
        build_file.write_text(json.dumps(data, ensure_ascii=False), encoding="utf-8")
        r = build_fixture(data_dir, templates_dir, out)
        assert r.returncode != 0, "unknown item must fail"
        combined = (r.stdout + r.stderr).lower()
        assert "fake trinket" in combined or "unknown" in combined or "未知" in combined
    finally:
        tmp.cleanup()


def test_pending_only_warns_not_fail() -> None:
    """待校对只 warn 加标：首批全未校对仍可发布 (隔离)."""
    data_dir, templates_dir, out, tmp = make_workdir()
    try:
        r = build_fixture(data_dir, templates_dir, out)
        assert r.returncode == 0, f"pending must not fail: {r.stderr[-2000:]}"
        combined = r.stdout + r.stderr
        assert "WARN" in combined, "pending entries must warn"
        html = (out / "cyborg.html").read_text(encoding="utf-8")
        assert "※" in html or "待校对" in html
    finally:
        tmp.cleanup()


def test_hover_reuses_icon_and_tip_conventions() -> None:
    """复用 conventions：图标三件套同一渲染路径，悬浮仍走 .tip，不另起一套 (隔离)."""
    data_dir, templates_dir, out, tmp = make_workdir()
    try:
        r = build_fixture(data_dir, templates_dir, out)
        assert r.returncode == 0, r.stderr[-2000:]
        html = (out / "cyborg.html").read_text(encoding="utf-8")
        m = re.search(r'data-section="weapons".*?</section>', html, re.S)
        assert m is not None
        sec = m.group(0)
        # 三件套：替代文本宽高 + 热链源 + 懒加载 + 失败移除。
        assert 'class="sic"' in sec
        assert 'loading="lazy"' in sec
        assert 'referrerpolicy="no-referrer"' in sec
        assert 'onerror="this.remove()"' in sec
        # 无第二套图标 class。
        assert "sic2" not in html and "wtip" not in html and "itip" not in html
        # kv 行占满整行 grid（与 .th/.tm/.tf 同规则），悬浮自身不滚动。
        tpl = (REPO / "templates" / "character.html").read_text(encoding="utf-8")
        assert ".kv" in tpl, "hover kv rows must be styled"
        assert "1 / -1" in tpl
    finally:
        tmp.cleanup()


def test_dlc_badge_for_dlc_entry() -> None:
    """DLC 角标：注册表标 abyssal 的条目渲染必须带 DLC 角标。"""
    data_dir, templates_dir, out, tmp = make_workdir()
    try:
        reg_file = data_dir / "wiki-cache.json"
        reg = json.loads(reg_file.read_text(encoding="utf-8"))
        reg["items"]["Coffee"]["dlc"] = "abyssal"
        reg_file.write_text(json.dumps(reg, ensure_ascii=False), encoding="utf-8")
        r = build_fixture(data_dir, templates_dir, out)
        assert r.returncode == 0, f"fixture build failed: {r.stderr[-2000:]}"
        html = (out / "cyborg.html").read_text(encoding="utf-8")
        m = re.search(r'data-section="items".*?</section>', html, re.S)
        assert m is not None
        idx = m.group(0).find('tabindex="0">Coffee')
        assert idx >= 0, "Coffee hover must render"
        assert "badge-dlc" in m.group(0)[idx:idx + 500], "DLC entry must carry badge-dlc"
    finally:
        tmp.cleanup()


def test_invalid_dlc_value_fails() -> None:
    """机检：注册表 DLC 归属非法即 fail（角标源错误）。"""
    data_dir, templates_dir, out, tmp = make_workdir()
    try:
        reg_file = data_dir / "wiki-cache.json"
        reg = json.loads(reg_file.read_text(encoding="utf-8"))
        reg["weapons"]["SMG"]["dlc"] = "primal"
        reg_file.write_text(json.dumps(reg, ensure_ascii=False), encoding="utf-8")
        r = build_fixture(data_dir, templates_dir, out)
        assert r.returncode != 0, "invalid dlc value must fail"
    finally:
        tmp.cleanup()


def test_weapon_hover_is_transposed_weapons_list() -> None:
    """武器悬浮为 Weapons List 转置：行=属性列=Lv1-4，等级色加 scaling 对照 (隔离)."""
    data_dir, templates_dir, out, tmp = make_workdir()
    try:
        r = build_fixture(data_dir, templates_dir, out)
        assert r.returncode == 0, f"build failed: {r.stderr[-2000:]}"
        html = (out / "cyborg.html").read_text(encoding="utf-8")
        m = re.search(r'data-section="weapons".*?</section>', html, re.S)
        assert m is not None
        sec = m.group(0)
        assert '<table class="wt">' in sec, "weapon hover must be a transposed table"
        for lv in ("Lv1", "Lv2", "Lv3", "Lv4"):
            assert lv in sec, f"transposed header must carry {lv}"
        for cls in ('class="w1"', 'class="w2"', 'class="w3"', 'class="w4"'):
            assert cls in sec, "levels must keep wiki white/blue/purple/red semantics"
        # scaling 对照：3(50% 远程伤害 (Ranged Damage))。
        assert "远程伤害" in sec and "(Ranged Damage)" in sec
        # 缺级诚实空出：Minigun 一二级无数值。
        assert "Minigun" in sec
        assert '<span class="w1">—</span>' in sec
        # 行列：Class 行与价格行、特效行与解锁行齐全。
        assert "Base Price" in sec and "Special Effects" in sec and "Unlocked By" in sec
    finally:
        tmp.cleanup()


def test_gear_tips_share_attr_positioning() -> None:
    """装备悬浮与属性同一套定位：单翻转规则，装备表 wrapper 不裁剪 (隔离产物)."""
    tpl = (REPO / "templates" / "character.html").read_text(encoding="utf-8")
    # 只有共用翻转规则，无装备特例定位。
    assert "nth-last-child" in tpl, "shared bottom-flip rule must exist"
    assert ".gear .tip" not in tpl, "no gear-specific tip positioning"
    # 装备表 wrapper 不裁剪：短表装不下高 tip，滚动容器会拦腰截断。
    assert ".table-wrap.gear-wrap" in tpl
    gear_wrap = tpl.split(".table-wrap.gear-wrap")[1].split("}")[0]
    assert "overflow:visible" in gear_wrap.replace(" ", "")
    data_dir, templates_dir, out, tmp = make_workdir()
    try:
        r = build_fixture(data_dir, templates_dir, out)
        assert r.returncode == 0, r.stderr[-2000:]
        html = (out / "cyborg.html").read_text(encoding="utf-8")
        for section in ("weapons", "items"):
            m = re.search(rf'data-section="{section}".*?</section>', html, re.S)
            assert m is not None
            assert 'class="table-wrap gear-wrap"' in m.group(0), f"{section} tables must not clip tips"
            assert 'class="has-tip"' in m.group(0), f"{section} names must carry hover"
    finally:
        tmp.cleanup()


def test_check_py_gates_weapon_item_hover() -> None:
    """check.py 门禁：产物武器道具 hover 缺失即 fail (隔离产物)."""
    data_dir, templates_dir, out, tmp_iso = make_workdir()
    try:
        r = build_fixture(data_dir, templates_dir, out)
        assert r.returncode == 0, r.stderr[-2000:]
        html = (out / "cyborg.html").read_text(encoding="utf-8")
        with tempfile.TemporaryDirectory() as tmp:
            good = Path(tmp) / "good.html"
            good.write_text(html, encoding="utf-8")
            r1 = subprocess.run([*CHECK, str(good)], cwd=REPO, capture_output=True, text=True)
            assert r1.returncode == 0, f"check must pass built page: {r1.stderr[-2000:]}"
            # 拔掉 hover（武器道具区随之失去悬浮）：门禁必须挂。
            stripped = re.sub(r'<span class="has-tip[^"]*"[^>]*>', '<span>', html)
            bad = Path(tmp) / "bad.html"
            bad.write_text(stripped, encoding="utf-8")
            r2 = subprocess.run([*CHECK, str(bad)], cwd=REPO, capture_output=True, text=True)
            assert r2.returncode != 0, "hover-stripped page must fail check"
    finally:
        tmp_iso.cleanup()
