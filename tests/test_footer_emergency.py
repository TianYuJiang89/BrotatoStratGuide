"""#12 E2E seam: 图标版权页脚合规 三处统一加署名.

Seams under test (pre-agreed per #8: E2E only):
- `python scripts/build.py --slug <slug>` / `--all` / `--use-local-assets` exit codes + `docs/*.html` bytes
- `python scripts/check.py <html>` exit codes
- `data/wiki-cache.json` + `assets/` bytes (registry single source, emergency empty)

No internal imports, no network. All assertions inspect CLI exit codes
and generated file/data bytes.

#19 clean slate: rendering via isolated tmp fixture, not repo docs.
"""

from __future__ import annotations

import re
import shutil
import subprocess
import sys
from pathlib import Path

REPO = Path(__file__).resolve().parent.parent
BUILD = [sys.executable, "scripts/build.py"]
CHECK = [sys.executable, "scripts/check.py"]
FIXTURE = REPO / "tests" / "fixtures" / "cyborg.json"


def run_build(*args: str, cwd: Path = REPO) -> subprocess.CompletedProcess[str]:
    return subprocess.run([*BUILD, *args], cwd=cwd, capture_output=True, text=True)


def make_isolated(tmp_path: Path, extra_args: list[str] | None = None) -> tuple[Path, str]:
    """Build fixture cyborg into isolated out, return (html_path, html)."""
    work = tmp_path / "work"
    if work.exists():
        shutil.rmtree(work)
    shutil.copytree(REPO / "data", work / "data")
    shutil.copytree(REPO / "templates", work / "templates")
    build_file = work / "data" / "builds" / "cyborg.json"
    # #23: repo已有真数据，隔离缝一律用夹具覆盖。
    build_file.parent.mkdir(parents=True, exist_ok=True)
    build_file.write_text(FIXTURE.read_text(encoding="utf-8"), encoding="utf-8")
    out = tmp_path / "out"
    out.mkdir(parents=True, exist_ok=True)
    args = [sys.executable, str(REPO / "scripts" / "build.py"),
            "--slug", "cyborg",
            "--data-dir", str(work / "data"),
            "--templates-dir", str(work / "templates"),
            "--out-dir", str(out)]
    if extra_args:
        args.extend(extra_args)
    r = subprocess.run(args, cwd=REPO, capture_output=True, text=True)
    assert r.returncode == 0, f"isolated build failed: {r.stderr[-2000:]}"
    html = (out / "cyborg.html").read_text(encoding="utf-8")
    return (out / "cyborg.html", html)


def test_three_icon_sites_share_same_loading_path(tmp_path: Path) -> None:
    """属性武器道具三处图标规则一致，无混用原图与占位 (#12)."""
    _, html = make_isolated(tmp_path)
    icons = re.findall(r'<img class="sic"[^>]*>', html)
    assert icons, "stat/weapon/item icons must share one rendering path"
    for tag in icons:
        assert 'loading="lazy"' in tag, f"lazy missing: {tag[:120]}"
        assert 'referrerpolicy="no-referrer"' in tag, f"no-referrer missing: {tag[:120]}"
        assert 'onerror="this.remove()"' in tag, f"onerror missing: {tag[:120]}"
        assert 'width=' in tag and 'height=' in tag, f"size missing: {tag[:120]}"
        assert 'alt=' in tag, f"alt missing: {tag[:120]}"
        assert 'data-file=' in tag, f"原文件标记 missing: {tag[:120]}"
        assert 'data-local=' in tag, f"应急路径 missing: {tag[:120]}"
        assert "wiki.spellsandguns.com" in tag, f"thumb must be wiki hotlink: {tag[:120]}"
        assert "/thumb/" in tag, f"must use thumbnail not original: {tag[:120]}"
    m_primary = re.search(r'data-section="attrs-primary".*?</section>', html, re.S)
    m_secondary = re.search(r'data-section="attrs-secondary".*?</section>', html, re.S)
    assert m_primary is not None and m_secondary is not None
    assert '<img class="sic"' in m_primary.group(0), "primary must carry hotlink icons"
    assert "◆" in m_secondary.group(0), "secondary itself must use placeholder"
    assert "wiki.spellsandguns.com" in m_secondary.group(0)
    for section in ("weapons", "items"):
        m = re.search(rf'data-section="{section}".*?</section>', html, re.S)
        assert m is not None
        assert '<img class="sic"' in m.group(0), f"{section} must share icon path"
    assert "sic2" not in html and "wtip" not in html and "itip" not in html


def test_broken_image_or_offline_still_readable_lazy(tmp_path: Path) -> None:
    """断图或断网仍可读，懒加载生效 (#12)."""
    _, html = make_isolated(tmp_path)
    imgs = re.findall(r"<img[^>]*>", html)
    assert imgs, "page must carry images"
    for tag in imgs:
        assert 'loading="lazy"' in tag, f"every img lazy: {tag[:120]}"
        assert 'onerror="this.remove()"' in tag, f"every img fails soft: {tag[:120]}"
    assert "◆" in html
    assert 'rel="stylesheet" href="http' not in html
    assert '<script src="http' not in html
    assert "fetch(" not in html


def test_footer_attribution_and_dual_links(tmp_path: Path) -> None:
    """页脚署名与原页链齐全，译自来源站双链齐全 (#12)."""
    _, html = make_isolated(tmp_path)
    m = re.search(r'<div class="footer">.*?</div>', html, re.S)
    assert m is not None, "footer must exist"
    foot = m.group(0)
    assert "Blobfish" in foot, "icon attribution missing"
    assert "brotato.wiki.spellsandguns.com" in foot, "wiki source link missing"
    assert "creativecommons.org/licenses/by-sa/4.0" in foot, "text license link missing"
    assert "Characters" in foot, "original page link missing"
    assert "youtube.com/@Cephalopocalypse" in foot or "取材视频" in foot
    assert "Stats" in foot or "Wiki" in foot
    assert "转述" in foot or "不搬" in foot
    assert "后续合规票" not in html


def test_emergency_switch_off_by_default_but_usable(tmp_path: Path) -> None:
    """应急开关平时不用，切换路径可用 (#12, 隔离)."""
    _, html = make_isolated(tmp_path)
    assert "wiki.spellsandguns.com" in html
    assert 'src="assets/' not in html, "default must hotlink, not self-host"
    for group in ("chars", "items", "stats", "weapons"):
        d = REPO / "assets" / group
        assert d.is_dir(), f"assets/{group} must exist"
        pngs = list(d.rglob("*.png"))
        assert pngs == [], f"assets/{group} must stay empty (no binaries), got {pngs}"
    _, local_html = make_isolated(tmp_path, extra_args=["--use-local-assets"])
    assert 'src="assets/' in local_html, "emergency switch must rewrite src to assets/"
    assert 'data-local="assets/' in local_html


def test_rating_seven_colors_legend_pending(tmp_path: Path) -> None:
    """评级七色与图例与待校对标记正确 (#12)."""
    _, html = make_isolated(tmp_path)
    tpl = (REPO / "templates" / "character.html").read_text(encoding="utf-8")
    for cls in ("rating-S", "rating-A", "rating-B", "rating-C",
                "rating-D", "rating-F", "rating-none"):
        assert cls in tpl, f"seven-color scale missing {cls} in template"
    assert "legend" in html.lower() or "图例" in html
    assert "只认视频作者口径" in html or "诚实空出" in html
    assert "※" in html and "待校对" in html
    assert "badge-review" in html
    assert 'data-section="attrs-primary"' in html
    assert 'data-section="attrs-secondary"' in html
    theads = re.findall(r"<th>(.*?)</th>", html)
    assert theads, "tables must carry headers"
    assert not any("赛博格" in h for h in theads), "headers must not carry character name"


def test_check_py_gates_footer_and_icons(tmp_path: Path) -> None:
    """check.py 门禁: 页脚/图标缺失即 fail (#12)."""
    import tempfile

    _, html = make_isolated(tmp_path)
    with tempfile.TemporaryDirectory() as tmp:
        good = Path(tmp) / "good.html"
        good.write_text(html, encoding="utf-8")
        r1 = subprocess.run([*CHECK, str(good)], cwd=REPO, capture_output=True, text=True)
        assert r1.returncode == 0, f"check must pass built page: {r1.stderr[-2000:]}"
        stripped = re.sub(r'<div class="footer">.*?</div>', '<div class="footer"></div>',
                          html, flags=re.S)
        bad = Path(tmp) / "bad.html"
        bad.write_text(stripped, encoding="utf-8")
        r2 = subprocess.run([*CHECK, str(bad)], cwd=REPO, capture_output=True, text=True)
        assert r2.returncode != 0, "footer-stripped page must fail check"
        nolazy = html.replace('loading="lazy"', "")
        bad2 = Path(tmp) / "bad2.html"
        bad2.write_text(nolazy, encoding="utf-8")
        r3 = subprocess.run([*CHECK, str(bad2)], cwd=REPO, capture_output=True, text=True)
        assert r3.returncode != 0, "lazy-stripped page must fail check"
