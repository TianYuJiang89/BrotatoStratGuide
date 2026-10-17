"""#20+#21 E2E seam: 多难度覆盖制 (variants 数组 + 动态诚实标签 + 交叉表按变体).

Seams under test (pre-agreed per #16 Notes: E2E only):
- `docs/sop/*.md` bytes (SOP 变体定义覆盖制)
- `python scripts/build.py --slug <slug>` exit codes + `docs/*.html` bytes
- `data/mentions/<slug>__<variant>.json` bytes + `check_mentions` exit codes

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
BUILD_MENTIONS = [sys.executable, "scripts/build_mentions.py"]
CHECK_MENTIONS = [sys.executable, "scripts/check_mentions.py"]
CHECK = [sys.executable, "scripts/check.py"]
FIXTURE = REPO / "tests" / "fixtures" / "cyborg.json"


def test_sop_variant_coverage_terms() -> None:
    """SOP 变体定义覆盖制 (#20 决议 + #21 先改后做): variants 数组 + 动态诚实标签."""
    guide = (REPO / "docs" / "sop" / "new-character-guide.md").read_text(encoding="utf-8")
    checklist = (REPO / "docs" / "sop" / "reviewer-checklist.md").read_text(encoding="utf-8")
    template = (REPO / "docs" / "sop" / "character-issue-template.md").read_text(encoding="utf-8")
    for needle in ("覆盖范围", "covers", "variants"):
        assert needle in guide, f"SOP 必须载明覆盖制 ({needle})"
    for needle in ("动态", "诚实", "合讲", "徽章"):
        assert needle in guide, f"SOP 必须载明动态诚实标签 ({needle})"
    assert "置灰" not in guide or "废除" in guide or "取代" in guide, "旧空档置灰必须废除/取代"
    for needle in ("__", "每变体"):
        assert needle in guide, f"SOP 必须载明交叉表按变体 ({needle})"
    for needle in ("covers", "每变体"):
        assert needle in checklist, f"reviewer 清单必须同步覆盖制 ({needle})"
    assert "variants" in template or "covers" in template, "模板必须同步覆盖制"


def _base_variant() -> dict:
    """新夹具首变体为底 (覆盖制, 非真口径)."""
    raw = json.loads(FIXTURE.read_text(encoding="utf-8"))
    if isinstance(raw, dict) and isinstance(raw.get("variants"), list) and raw["variants"]:
        base = raw["variants"][0]
        assert isinstance(base, dict)
        return dict(base)
    return dict(raw) if isinstance(raw, dict) else {}


def _old_to_variant(old: dict, covers: list[str], label: str = "") -> dict:
    """旧单层夹具转覆盖制变体 (测试隔离用, 非真口径, 兼容新旧夹具)."""
    base = old.get("variants")[0] if isinstance(old.get("variants"), list) and old.get("variants") else old
    assert isinstance(base, dict)
    vid = "-".join(c.lower().replace(" ", "-") for c in covers)
    return {
        "id": vid,
        "covers": covers,
        "label": label or " + ".join(covers),
        "status": "ready",
        "mechanism": base.get("mechanism", ""),
        "ratings": base.get("ratings", {}),
        "weapons_t1": base.get("weapons_t1", []),
        "weapons_t2": base.get("weapons_t2", []),
        "items": base.get("items", []),
        "phases": base.get("phases", []),
        "upgrade": base.get("upgrade", ""),
        "shop": base.get("shop", ""),
        "pitfalls": base.get("pitfalls", []),
        "hard": base.get("hard", ""),
        "source": base.get("source", {}),
    }


def _make_workdir_with_variants(variants: list[dict]) -> tuple[Path, Path, Path, tempfile.TemporaryDirectory[str]]:
    tmp = tempfile.TemporaryDirectory()
    work = Path(tmp.name) / "work"
    shutil.copytree(REPO / "data", work / "data")
    shutil.copytree(REPO / "templates", work / "templates")
    payload = {"slug": "cyborg", "variants": variants}
    bf = work / "data" / "builds" / "cyborg.json"
    bf.parent.mkdir(parents=True, exist_ok=True)
    bf.write_text(json.dumps(payload, ensure_ascii=False), encoding="utf-8")
    out = Path(tmp.name) / "out"
    out.mkdir(parents=True, exist_ok=True)
    return (work / "data", work / "templates", out, tmp)


def _build(data_dir: Path, templates_dir: Path, out: Path) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        [*BUILD, "--slug", "cyborg",
         "--data-dir", str(data_dir),
         "--templates-dir", str(templates_dir),
         "--out-dir", str(out)],
        cwd=REPO, capture_output=True, text=True,
    )


def test_single_variant_renders_cover_badge_no_tablist() -> None:
    """单变体退化为覆盖徽章, 不留单 tab 栏 (动态诚实标签)."""
    old = json.loads(FIXTURE.read_text(encoding="utf-8"))
    variants = [_old_to_variant(old, ["Nightmare"])]
    data_dir, templates_dir, out, tmp = _make_workdir_with_variants(variants)
    try:
        r = _build(data_dir, templates_dir, out)
        assert r.returncode == 0, f"单变体须可构建: {r.stderr[-2000:]}"
        html = (out / "cyborg.html").read_text(encoding="utf-8")
        assert "coverbadge" in html or "覆盖" in html, "单变体须退化为覆盖徽章"
        assert 'role="tablist"' not in html, "单变体不留单 tab 栏"
        assert "Nightmare" in html
        assert "GENERATED" in html and "scripts/build.py" in html
        # 离线双击可读: 无外部阻塞, 无 fetch.
        assert "fetch(" not in html
        assert '<script src="http' not in html
    finally:
        tmp.cleanup()


def test_multi_variant_renders_tablist_with_honest_labels() -> None:
    """多变体 A 胜出 tab: sticky 分段独占切换 + APG + 全名标签高->低."""
    old = json.loads(FIXTURE.read_text(encoding="utf-8"))
    v_ult = _old_to_variant(old, ["Ultimate"])
    v_nm = _old_to_variant(old, ["Nightmare"])
    # 故意逆序给, 构建须按最高难度高->低排序 (Ultimate 在前).
    data_dir, templates_dir, out, tmp = _make_workdir_with_variants([v_nm, v_ult])
    try:
        r = _build(data_dir, templates_dir, out)
        assert r.returncode == 0, f"多变体须可构建: {r.stderr[-2000:]}"
        html = (out / "cyborg.html").read_text(encoding="utf-8")
        assert 'role="tablist"' in html, "多变体须有 tablist (A 胜出)"
        assert html.count('role="tab"') == 2, "有几份证据出几个 tab"
        assert "Ultimate" in html and "Nightmare" in html
        # 全名标签 (Danger 5 不用 D5), APG 键盘, 44px 触区, 横滑, sticky.
        for needle in ("aria-selected", "tabpanel", "44px", "sticky"):
            assert needle in html, f"A tab 须含 {needle}"
        # 高->低排序: Ultimate tab 先于 Nightmare.
        assert html.index("Ultimate") < html.index("Nightmare"), "排序须高->低"
        # 每变体独立内容: 两个面板各有 11 段.
        secs = re.findall(r'data-section="([^"]+)"', html)
        assert len(secs) == 22, f"每变体 11 段 x2=22, got {len(secs)}"
        # 页内首个 JS, vanilla 离线.
        assert "fetch(" not in html
    finally:
        tmp.cleanup()


def test_merged_variant_single_tab_with_plus_label() -> None:
    """合讲合并: 同一视频覆盖多档只跑一份, 单 tab 标签 Ultimate + Nightmare."""
    old = json.loads(FIXTURE.read_text(encoding="utf-8"))
    merged = _old_to_variant(old, ["Ultimate", "Nightmare"], "Ultimate + Nightmare")
    # 合讲 source 难度即合并标签 (非单档).
    merged["source"] = dict(merged["source"])
    merged["source"]["difficulty"] = "Ultimate + Nightmare"
    data_dir, templates_dir, out, tmp = _make_workdir_with_variants([merged])
    try:
        r = _build(data_dir, templates_dir, out)
        assert r.returncode == 0, f"合讲变体须可构建: {r.stderr[-2000:]}"
        html = (out / "cyborg.html").read_text(encoding="utf-8")
        assert "Ultimate + Nightmare" in html, "合讲标签须 Ultimate + Nightmare"
        assert 'role="tablist"' not in html, "合讲单变体退徽章, 无 tab 栏"
    finally:
        tmp.cleanup()


def test_old_single_layer_keys_rejected() -> None:
    """旧单层键废除: 顶层含 mechanism 等即 fail, 须只用 variants 数组."""
    tmp = tempfile.TemporaryDirectory()
    work = Path(tmp.name) / "work"
    shutil.copytree(REPO / "data", work / "data")
    shutil.copytree(REPO / "templates", work / "templates")
    old_flat = json.loads(FIXTURE.read_text(encoding="utf-8"))
    # 新夹具已是 variants 形, 还原旧扁平形 (取首变体铺平) 触发废除 fail.
    if isinstance(old_flat.get("variants"), list) and old_flat["variants"]:
        flat = dict(old_flat["variants"][0])
        flat.pop("id", None); flat.pop("covers", None); flat.pop("label", None); flat.pop("status", None)
    else:
        flat = dict(old_flat)
    bf = work / "data" / "builds" / "cyborg.json"
    bf.parent.mkdir(parents=True, exist_ok=True)
    bf.write_text(json.dumps(flat, ensure_ascii=False), encoding="utf-8")
    out = Path(tmp.name) / "out"
    out.mkdir(parents=True, exist_ok=True)
    try:
        r = subprocess.run(
            [*BUILD, "--slug", "cyborg", "--data-dir", str(work / "data"),
             "--templates-dir", str(work / "templates"), "--out-dir", str(out)],
            cwd=REPO, capture_output=True, text=True,
        )
        assert r.returncode != 0, "旧单层键须 fail (废除)"
        combined = (r.stdout + r.stderr).lower()
        assert "variants" in combined or "废除" in combined or "单层" in combined
    finally:
        tmp.cleanup()


def test_variant_covers_sorting_and_label_enforced() -> None:
    """covers 须高->低排序且 label/id 须一致, 否则 fail."""
    base = _base_variant()
    bad = dict(base)
    bad["covers"] = ["Nightmare", "Ultimate"]
    bad["label"] = "Nightmare + Ultimate"
    bad["id"] = "nightmare-ultimate"
    data_dir, templates_dir, out, tmp = _make_workdir_with_variants([bad])
    try:
        r = _build(data_dir, templates_dir, out)
        assert r.returncode != 0, "covers 逆序须 fail"
    finally:
        tmp.cleanup()


def test_build_mentions_per_variant_files() -> None:
    """交叉表按变体: data/mentions/<slug>__<variant>.json 每变体独立跑."""
    old = json.loads(FIXTURE.read_text(encoding="utf-8"))
    v_ult = _old_to_variant(old, ["Ultimate"])
    v_nm = _old_to_variant(old, ["Nightmare"])
    data_dir, templates_dir, out, tmp = _make_workdir_with_variants([v_ult, v_nm])
    try:
        subs = data_dir / "subs"
        subs.mkdir(parents=True, exist_ok=True)
        vtt = "WEBVTT\n\n00:00.000 --> 00:02.000\nwrenches only with turrets\n"
        (subs / "cyborg__ultimate.en-orig.vtt").write_text(vtt, encoding="utf-8")
        (subs / "cyborg__nightmare.en-orig.vtt").write_text(vtt, encoding="utf-8")
        for vid in ("ultimate", "nightmare"):
            r = subprocess.run(
                [*BUILD_MENTIONS, "--slug", "cyborg", "--variant", vid, "--data-dir", str(data_dir)],
                cwd=REPO, capture_output=True, text=True,
            )
            assert r.returncode == 0, f"build_mentions {vid} 须 exit 0: {r.stderr[-2000:]}"
            p = data_dir / "mentions" / f"cyborg__{vid}.json"
            assert p.exists(), f"交叉表须落 {p.name} (每变体)"
            payload = json.loads(p.read_text(encoding="utf-8"))
            assert payload.get("variant") == vid
            assert isinstance(payload.get("terms"), dict) and len(payload["terms"]) == 39
        # check_mentions 只 warn 不 fail.
        r = subprocess.run(
            [*CHECK_MENTIONS, "--slug", "cyborg", "--data-dir", str(data_dir)],
            cwd=REPO, capture_output=True, text=True,
        )
        assert r.returncode == 0, f"check_mentions 只 warn 不 fail: {r.stderr[-2000:]}"
    finally:
        tmp.cleanup()


def test_check_py_gates_variant_tabs() -> None:
    """check.py 覆盖制门禁: 单徽章 vs 多 tablist, 缺失即 fail."""
    old = json.loads(FIXTURE.read_text(encoding="utf-8"))
    # 单变体须过 check.
    data_dir, templates_dir, out, tmp = _make_workdir_with_variants([_old_to_variant(old, ["Nightmare"])])
    try:
        assert _build(data_dir, templates_dir, out).returncode == 0
        html = out / "cyborg.html"
        r = subprocess.run([*CHECK, str(html)], cwd=REPO, capture_output=True, text=True)
        assert r.returncode == 0, f"check 须过单变体徽章页: {r.stderr[-2000:]}"
        # 拔掉徽章即 fail.
        bad = html.read_text(encoding="utf-8").replace("coverbadge", "no-badge").replace("覆盖", "no-badge")
        probe = out / "probe_single.html"
        probe.write_text(bad, encoding="utf-8")
        r2 = subprocess.run([*CHECK, str(probe)], cwd=REPO, capture_output=True, text=True)
        assert r2.returncode != 0, "单变体缺徽章须 fail"
    finally:
        tmp.cleanup()
    # 多变体须过 check, 拔掉 tablist 即 fail.
    v_ult = _old_to_variant(old, ["Ultimate"])
    v_nm = _old_to_variant(old, ["Nightmare"])
    data_dir2, templates_dir2, out2, tmp2 = _make_workdir_with_variants([v_ult, v_nm])
    try:
        assert _build(data_dir2, templates_dir2, out2).returncode == 0
        html2 = out2 / "cyborg.html"
        r3 = subprocess.run([*CHECK, str(html2)], cwd=REPO, capture_output=True, text=True)
        assert r3.returncode == 0, f"check 须过多变体 tab 页: {r3.stderr[-2000:]}"
        stripped = html2.read_text(encoding="utf-8").replace('role="tablist"', 'role="notabs"')
        probe2 = out2 / "probe_multi.html"
        probe2.write_text(stripped, encoding="utf-8")
        r4 = subprocess.run([*CHECK, str(probe2)], cwd=REPO, capture_output=True, text=True)
        assert r4.returncode != 0, "多变体缺 tablist 须 fail"
    finally:
        tmp2.cleanup()
