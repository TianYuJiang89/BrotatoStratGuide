"""#12 E2E seam: 图标版权页脚合规 三处统一加署名.

Seams under test (pre-agreed per #8: E2E only):
- `python scripts/build.py --slug <slug>` / `--all` / `--use-local-assets` exit codes + `docs/*.html` bytes
- `python scripts/check.py <html>` exit codes
- `data/wiki-cache.json` + `assets/` bytes (registry single source, emergency empty)

No internal imports, no network. All assertions inspect CLI exit codes
and generated file/data bytes.
"""

from __future__ import annotations

import re
import subprocess
import sys
from pathlib import Path

REPO = Path(__file__).resolve().parent.parent
BUILD = [sys.executable, "scripts/build.py"]
CHECK = [sys.executable, "scripts/check.py"]


def run_build(*args: str, cwd: Path = REPO) -> subprocess.CompletedProcess[str]:
    return subprocess.run([*BUILD, *args], cwd=cwd, capture_output=True, text=True)


def test_three_icon_sites_share_same_loading_path() -> None:
    """属性武器道具三处图标规则一致，无混用原图与占位 (#12)."""
    r = run_build("--slug", "cyborg")
    assert r.returncode == 0, f"build failed: {r.stderr[-2000:]}"
    html = (REPO / "docs" / "cyborg.html").read_text(encoding="utf-8")
    # 三处主图标: 同一渲染路径, 有图挂三件套 (替代文本+宽高+热链源+原文件标记+应急路径+懒加载+无来源引用+失败移除)。
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
        # 不用原图: 缩略图路径必须含 /thumb/。
        assert "/thumb/" in tag, f"must use thumbnail not original: {tag[:120]}"
    # 无混用原图与占位: 主表有热链, 次级本身统一占位。
    m_primary = re.search(r'data-section="attrs-primary".*?</section>', html, re.S)
    m_secondary = re.search(r'data-section="attrs-secondary".*?</section>', html, re.S)
    assert m_primary is not None and m_secondary is not None
    assert '<img class="sic"' in m_primary.group(0), "primary must carry hotlink icons"
    assert "◆" in m_secondary.group(0), "secondary itself must use placeholder"
    # 次级悬浮仍热链: 次级区 tip 内仍有 wiki 热链图。
    assert "wiki.spellsandguns.com" in m_secondary.group(0)
    # 武器道具区同路径: 亦有三件套图标, 无第二套 icon class。
    for section in ("weapons", "items"):
        m = re.search(rf'data-section="{section}".*?</section>', html, re.S)
        assert m is not None
        assert '<img class="sic"' in m.group(0), f"{section} must share icon path"
    assert "sic2" not in html and "wtip" not in html and "itip" not in html


def test_broken_image_or_offline_still_readable_lazy() -> None:
    """断图或断网仍可读，懒加载生效 (#12)."""
    r = run_build("--slug", "cyborg")
    assert r.returncode == 0, r.stderr[-2000:]
    html = (REPO / "docs" / "cyborg.html").read_text(encoding="utf-8")
    imgs = re.findall(r"<img[^>]*>", html)
    assert imgs, "page must carry images"
    for tag in imgs:
        assert 'loading="lazy"' in tag, f"every img lazy: {tag[:120]}"
        assert 'onerror="this.remove()"' in tag, f"every img fails soft: {tag[:120]}"
    # 外层占位保底: 属性 ◆ / 索引 🥔 至少其一在单页。
    assert "◆" in html
    # 无阻塞式外链: 断网双击可开。
    assert 'rel="stylesheet" href="http' not in html
    assert '<script src="http' not in html
    assert "fetch(" not in html


def test_footer_attribution_and_dual_links() -> None:
    """页脚署名与原页链齐全，译自来源站双链齐全 (#12)."""
    r = run_build("--slug", "cyborg")
    assert r.returncode == 0, r.stderr[-2000:]
    html = (REPO / "docs" / "cyborg.html").read_text(encoding="utf-8")
    m = re.search(r'<div class="footer">.*?</div>', html, re.S)
    assert m is not None, "footer must exist"
    foot = m.group(0)
    # 署名行: 图标 © Blobfish + wiki 来源 + 文本许可链。
    assert "Blobfish" in foot, "icon attribution missing"
    assert "brotato.wiki.spellsandguns.com" in foot, "wiki source link missing"
    assert "creativecommons.org/licenses/by-sa/4.0" in foot, "text license link missing"
    # 原页链: 至少链到 Characters 原页。
    assert "Characters" in foot, "original page link missing"
    # 译自来源站双链: 取材视频 + wiki 原页双链, 转述非搬运。
    assert "youtube.com/@Cephalopocalypse" in foot or "取材视频" in foot
    assert "Stats" in foot or "Wiki" in foot
    assert "转述" in foot or "不搬" in foot
    # 骨架占位文案必须消失。
    assert "后续合规票" not in html


def test_emergency_switch_off_by_default_but_usable() -> None:
    """应急开关平时不用，切换路径可用 (#12)."""
    r = run_build("--slug", "cyborg")
    assert r.returncode == 0, r.stderr[-2000:]
    html = (REPO / "docs" / "cyborg.html").read_text(encoding="utf-8")
    # 平时不用: 默认 src 全是 wiki 热链, 无 assets 自托管。
    assert "wiki.spellsandguns.com" in html
    assert 'src="assets/' not in html, "default must hotlink, not self-host"
    # 应急目录平时空: 只有占位, 无二进制。
    for group in ("chars", "items", "stats", "weapons"):
        d = REPO / "assets" / group
        assert d.is_dir(), f"assets/{group} must exist"
        pngs = list(d.rglob("*.png"))
        assert pngs == [], f"assets/{group} must stay empty (no binaries), got {pngs}"
    # 切换路径可用: --use-local-assets 一键切相对路径。
    r2 = run_build("--slug", "cyborg", "--use-local-assets")
    assert r2.returncode == 0, f"local switch failed: {r2.stderr[-2000:]}"
    local_html = (REPO / "docs" / "cyborg.html").read_text(encoding="utf-8")
    assert 'src="assets/' in local_html, "emergency switch must rewrite src to assets/"
    assert 'data-local="assets/' in local_html
    # 切回默认, 不污染后续测试/产物。
    r3 = run_build("--slug", "cyborg")
    assert r3.returncode == 0, r3.stderr[-2000:]
    assert 'src="assets/' not in (REPO / "docs" / "cyborg.html").read_text(encoding="utf-8")


def test_rating_seven_colors_legend_pending() -> None:
    """评级七色与图例与待校对标记正确 (#12)."""
    r = run_build("--slug", "cyborg")
    assert r.returncode == 0, r.stderr[-2000:]
    html = (REPO / "docs" / "cyborg.html").read_text(encoding="utf-8")
    tpl = (REPO / "templates" / "character.html").read_text(encoding="utf-8")
    # 七色: S/A/B/C/D/F + 空出, 图例挂表头下。
    for cls in ("rating-S", "rating-A", "rating-B", "rating-C",
                "rating-D", "rating-F", "rating-none"):
        assert cls in tpl, f"seven-color scale missing {cls} in template"
    assert "legend" in html.lower() or "图例" in html
    assert "只认视频作者口径" in html or "诚实空出" in html
    # 待校对标记: ※ + 待校对 badge, 只 warn 不 fail 已由旧测试覆盖, 此处只验标记存在。
    assert "※" in html and "待校对" in html
    assert "badge-review" in html
    # 主次拆表 + 表头复用不带角色名。
    assert 'data-section="attrs-primary"' in html
    assert 'data-section="attrs-secondary"' in html
    theads = re.findall(r"<th>(.*?)</th>", html)
    assert theads, "tables must carry headers"
    assert not any("赛博格" in h for h in theads), "headers must not carry character name"


def test_check_py_gates_footer_and_icons() -> None:
    """check.py 门禁: 页脚/图标缺失即 fail (#12)."""
    import tempfile

    r = run_build("--slug", "cyborg")
    assert r.returncode == 0, r.stderr[-2000:]
    html = (REPO / "docs" / "cyborg.html").read_text(encoding="utf-8")
    with tempfile.TemporaryDirectory() as tmp:
        good = Path(tmp) / "good.html"
        good.write_text(html, encoding="utf-8")
        r1 = subprocess.run([*CHECK, str(good)], cwd=REPO, capture_output=True, text=True)
        assert r1.returncode == 0, f"check must pass built page: {r1.stderr[-2000:]}"
        # 拔掉页脚署名: 门禁必须挂。
        stripped = re.sub(r'<div class="footer">.*?</div>', '<div class="footer"></div>',
                          html, flags=re.S)
        bad = Path(tmp) / "bad.html"
        bad.write_text(stripped, encoding="utf-8")
        r2 = subprocess.run([*CHECK, str(bad)], cwd=REPO, capture_output=True, text=True)
        assert r2.returncode != 0, "footer-stripped page must fail check"
        # 拔掉懒加载: 门禁必须挂。
        nolazy = html.replace('loading="lazy"', "")
        bad2 = Path(tmp) / "bad2.html"
        bad2.write_text(nolazy, encoding="utf-8")
        r3 = subprocess.run([*CHECK, str(bad2)], cwd=REPO, capture_output=True, text=True)
        assert r3.returncode != 0, "lazy-stripped page must fail check"
