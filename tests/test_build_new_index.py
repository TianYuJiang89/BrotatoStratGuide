"""#73 新链索引页: 五角色 guide 一页可达.

Seams under test (pre-agreed per TDD: CLI exit codes + file bytes, no internal LLM):
- `python scripts/build_new_index.py --help` exit codes + `--work-root`/`--out`
- 实 G 跑: 五卡齐全可点 (slug/variant/covers/sha/取证日期/视频标题链接 + guide href 目标存在)
- 夹具跑: 现场组装 (改 title 重跑即变, 防手写) + 幂等 (两跑逐字节一致)
- 缺件 fail loud: 缺 guide.json / 缺 guide.html 即 exit != 0, 不写半成品
- 旧 docs/index.html 碰都不碰 (只认 docs/new_index.html)

No internal imports, no network. All assertions inspect CLI exit codes
and generated file bytes (href targets resolved back to disk).
"""

from __future__ import annotations

import hashlib
import html as html_mod
import json
import re
import subprocess
import sys
import urllib.parse
import urllib.request
from pathlib import Path

REPO = Path(__file__).resolve().parent.parent
BUILD = [sys.executable, "scripts/build_new_index.py"]
EXPECTED: list[tuple[str, str]] = [
    ("cyborg", "ultimate"),
    ("doctor", "nightmare"),
    ("engineer", "ultimate"),
    ("one-armed", "ultimate"),
    ("ranger", "ultimate"),
]


def run_build(*args: str, cwd: Path = REPO) -> subprocess.CompletedProcess[str]:
    return subprocess.run([*BUILD, *args], cwd=cwd, capture_output=True, text=True)


def _resolve_href(html: str, out_path: Path) -> list[Path]:
    """索引中看攻略 href 回解为磁盘路径 (相对 href 或 file:// URI)."""
    hrefs = re.findall(r'<a class="go" href="([^"]+)"', html)
    out: list[Path] = []
    for h in hrefs:
        if h.startswith("file:"):
            out.append(Path(urllib.request.url2pathname(urllib.parse.urlparse(h).path)))
        else:
            out.append((out_path.parent / h).resolve())
    return out


def _write_variant(
    work: Path,
    slug: str,
    variant: str,
    *,
    title: str | None = None,
    published: str = "2026-09-01",
    covers: list[str] | None = None,
    with_html: bool = True,
) -> dict[str, str]:
    sha = hashlib.sha1(f"{slug}/{variant}".encode()).hexdigest()
    cov = covers if covers is not None else (["Nightmare"] if variant == "nightmare" else ["Ultimate"])
    base = work / slug / variant
    (base / "outputs").mkdir(parents=True, exist_ok=True)
    (base / "inputs").mkdir(parents=True, exist_ok=True)
    guide = {
        "slug": slug,
        "variant": variant,
        "covers": cov,
        "sha": sha,
        "url": f"https://www.youtube.com/watch?v={slug}-{variant}",
        "title": title if title is not None else f"{slug} {variant} Guide",
    }
    (base / "outputs" / "guide.json").write_text(json.dumps(guide, ensure_ascii=False), encoding="utf-8")
    (base / "inputs" / "meta.json").write_text(
        json.dumps({"published": published, "video_id": f"{slug}-{variant}"}), encoding="utf-8"
    )
    (base / "inputs" / "manifest.json").write_text(
        json.dumps(
            {"slug": slug, "variant": variant, "covers": cov,
             "sources": [{"sha1": sha, "published": published}]},
            ensure_ascii=False,
        ),
        encoding="utf-8",
    )
    if with_html:
        (base / "outputs" / "guide.html").write_text("<html><body>guide</body></html>", encoding="utf-8")
    return {"sha": sha, "title": str(guide["title"]), "url": str(guide["url"]), "published": published}


def _write_fixture(work: Path) -> dict[tuple[str, str], dict[str, str]]:
    got: dict[tuple[str, str], dict[str, str]] = {}
    for slug, variant in EXPECTED:
        got[(slug, variant)] = _write_variant(work, slug, variant)
    return got


def test_help_documents_work_root_and_out() -> None:
    r = run_build("--help")
    assert r.returncode == 0, f"--help must exit 0: {r.stderr[-1000:]}"
    assert "--work-root" in r.stdout
    assert "--out" in r.stdout


def test_never_touches_old_index() -> None:
    src = (REPO / "scripts" / "build_new_index.py").read_text(encoding="utf-8")
    hits = [m.start() for m in re.finditer(r"index\.html", src)]
    assert hits, "must mention an index output"
    for i in hits:
        assert src[max(0, i - 4):i] == "new_", "only docs/new_index.html allowed, never old docs/index.html"
    assert 'default="docs/new_index.html"' in src
    assert "build.py" not in src and "data/builds" not in src, "must not read old chain"


def test_real_g_five_cards_clickable(tmp_path: Path) -> None:
    """实 G 跑: 五卡齐全, 字段与 G 现场一致, href 目标全存在."""
    work = Path("G:/brotato-work")
    if not (work / "cyborg" / "ultimate" / "outputs" / "guide.json").exists():
        raise AssertionError("G work cyborg/ultimate outputs/guide.json missing (先备后跑前置)")
    out = tmp_path / "new_index.html"
    r = run_build("--work-root", str(work), "--out", str(out))
    assert r.returncode == 0, f"real G build must pass: {r.stderr[-2000:]}"
    assert out.is_file(), "must write single file output"
    page = out.read_text(encoding="utf-8")
    assert page.count('class="card"') == 5, "must render exactly 5 cards"
    for slug, variant in EXPECTED:
        guide = json.loads((work / slug / variant / "outputs" / "guide.json").read_text(encoding="utf-8"))
        meta = json.loads((work / slug / variant / "inputs" / "meta.json").read_text(encoding="utf-8"))
        for needle in (
            f'data-slug="{slug}"',
            f'data-variant="{variant}"',
            str(guide["sha"]),
            str(meta["published"]),
            html_mod.escape(str(guide["title"])),
            str(guide["url"]),
        ):
            assert needle in page, f"card {slug}/{variant} must show live field: {needle[:40]}"
        for c in guide["covers"]:
            assert html_mod.escape(str(c)) in page
    targets = _resolve_href(page, out)
    assert len(targets) == 5, f"5 guide links required, got {len(targets)}"
    for t in targets:
        assert t.is_file(), f"guide link target must exist (可点): {t}"


def test_fixture_live_assembly_idempotent_and_relhref(tmp_path: Path) -> None:
    """夹具跑: 同盘相对 href 可解, 改 title 重跑即变 (防手写), 两跑逐字节一致."""
    work = tmp_path / "work"
    got = _write_fixture(work)
    out = work / "new_index.html"
    r = run_build("--work-root", str(work), "--out", str(out))
    assert r.returncode == 0, f"fixture build must pass: {r.stderr[-2000:]}"
    page = out.read_text(encoding="utf-8")
    assert page.count('class="card"') == 5
    hrefs = re.findall(r'<a class="go" href="([^"]+)"', page)
    assert len(hrefs) == 5 and all(not h.startswith("file:") for h in hrefs), \
        f"same-tree out must emit relative hrefs, got {hrefs}"
    for t in _resolve_href(page, out):
        assert t.is_file(), f"relative href must resolve: {t}"
    # 现场组装: 改一单 title 重跑即变.
    _write_variant(work, "ranger", "ultimate", title="RANGER RE-TITLED LIVE")
    r2 = run_build("--work-root", str(work), "--out", str(out))
    assert r2.returncode == 0, r2.stderr[-2000:]
    page2 = out.read_text(encoding="utf-8")
    assert "RANGER RE-TITLED LIVE" in page2, "must assemble live from guide.json (禁手写)"
    assert got[("cyborg", "ultimate")]["sha"] in page2
    # 幂等: 同输入两跑逐字节一致 (无 wall-clock).
    b1 = out.read_bytes()
    r3 = run_build("--work-root", str(work), "--out", str(out))
    assert r3.returncode == 0, r3.stderr[-2000:]
    assert out.read_bytes() == b1, "same inputs must yield byte-identical page (幂等)"


def test_missing_guide_json_fails_loud_no_partial(tmp_path: Path) -> None:
    """缺一单 guide.json 即整页 fail, 不写半成品 (不静默缺卡)."""
    work = tmp_path / "work"
    _write_fixture(work)
    (work / "ranger" / "ultimate" / "outputs" / "guide.json").unlink()
    out = tmp_path / "new_index.html"
    r = run_build("--work-root", str(work), "--out", str(out))
    assert r.returncode != 0, "missing guide.json must fail loud"
    assert "FAIL" in (r.stderr + r.stdout) and "ranger" in (r.stderr + r.stdout)
    assert not out.exists(), "must not write partial page on missing card"


def test_missing_guide_html_fails_loud_no_dead_link(tmp_path: Path) -> None:
    """guide.html 缺失即 fail (所链目标不存在, 不发死链)."""
    work = tmp_path / "work"
    _write_fixture(work)
    (work / "doctor" / "nightmare" / "outputs" / "guide.html").unlink()
    out = tmp_path / "new_index.html"
    r = run_build("--work-root", str(work), "--out", str(out))
    assert r.returncode != 0, "missing guide.html must fail loud (禁死链)"
    assert "FAIL" in (r.stderr + r.stdout) and "doctor" in (r.stderr + r.stdout)
    assert not out.exists(), "must not write page with dead link"
