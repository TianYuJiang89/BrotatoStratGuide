"""Skeleton E2E seam: build CLI + generated HTML external behavior only.

Seams under test (pre-agreed per #8 Testing Decisions: 端到端为最高且唯一的 seam):
- `python scripts/build.py --slug <slug>` / `--all` exit codes + `docs/*.html` artifacts
- 机检门禁: 缺段/改序 => fail; 缺验收线 => warn + 待补徽标但可发布
- 产物可读性: 手机不溢出 / 离线双击可读 / 构建生成标记

No internal imports, no network. All assertions inspect CLI exit codes
and generated file bytes.

#32 1可点: repo has cyborg (Ultimate/Nightmare/Danger5 三变体), docs 1 clickable.
Rendering details are covered via isolated tmp fixtures (tests/fixtures/cyborg.json),
repo assertions cover the built index.
"""

from __future__ import annotations

import json
import re
import shutil
import subprocess
import sys
from pathlib import Path

REPO = Path(__file__).resolve().parent.parent
BUILD = [sys.executable, "scripts/build.py"]
FIXTURE = REPO / "tests" / "fixtures" / "cyborg.json"

# 10 段锁死顺序 (2a/2b 计为两节, 共 11 个 data-section; 内容模板 10 段中
# "核心属性"拆主次两表, 顺序不可变)。与 #5 决议顺序一致。
EXPECTED_ORDER = [
    "mechanism",
    "attrs-primary",
    "attrs-secondary",
    "weapons",
    "items",
    "phases",
    "upgrade",
    "shop",
    "pitfalls",
    "hard",
    "source",
]


def run_build(*args: str, cwd: Path = REPO) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        [*BUILD, *args],
        cwd=cwd,
        capture_output=True,
        text=True,
    )


def sections_in(html: str) -> list[str]:
    return re.findall(r'data-section="([^"]+)"', html)


def make_isolated(tmp_path: Path) -> tuple[Path, Path, Path]:
    """Isolated data/templates/out with fixture cyborg build (#32 1可点覆盖)."""
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


def test_per_slug_build_produces_ordered_sections(tmp_path: Path) -> None:
    """单角色构建: 10 段齐全且顺序正确 (隔离夹具, 不依赖 repo 测试数据)."""
    data_dir, templates_dir, out = make_isolated(tmp_path)
    r = build_isolated(data_dir, templates_dir, out)
    assert r.returncode == 0, f"build failed: {r.stderr[-2000:]}"
    html = (out / "cyborg.html").read_text(encoding="utf-8")
    assert sections_in(html) == EXPECTED_ORDER


def test_index_links_to_character_page() -> None:
    """#32 1可点: cyborg 已建链, engineer 未建无死链."""
    r = run_build("--all")
    assert r.returncode == 0, f"build --all failed: {r.stderr[-2000:]}"
    index = (REPO / "docs" / "index.html").read_text(encoding="utf-8")
    assert "./cyborg.html" in index, "cyborg built must link"
    assert "./engineer.html" not in index, "unbuilt engineer must not link"


def test_full_and_per_slug_builds_both_run(tmp_path: Path) -> None:
    """全量构建可跑 (1页) + 隔离单页构建可跑; 缺 build 的 slug 在 repo 上必须 fail."""
    r2 = run_build("--all")
    assert r2.returncode == 0, r2.stderr[-2000:]
    assert (REPO / "docs" / "index.html").exists()
    assert (REPO / "docs" / "cyborg.html").exists(), "#32 cyborg built"
    # 隔离单页仍可跑 (seam 不回归).
    data_dir, templates_dir, out = make_isolated(tmp_path)
    r1 = build_isolated(data_dir, templates_dir, out)
    assert r1.returncode == 0, r1.stderr[-2000:]
    assert (out / "cyborg.html").exists()
    # repo 上有数据时 --slug cyborg 必须 pass; 未知 slug 必须 fail.
    r3 = run_build("--slug", "cyborg")
    assert r3.returncode == 0, "cyborg built must pass"
    r4 = run_build("--slug", "mage")
    assert r4.returncode != 0, "missing build mage must fail"


def test_honest_empty_sections_are_shown_not_hidden(tmp_path: Path) -> None:
    """无口径段显示诚实空出而非隐藏: 空评级渲染为作者未提及, 段仍在 (隔离夹具)."""
    data_dir, templates_dir, out = make_isolated(tmp_path)
    r = build_isolated(data_dir, templates_dir, out)
    assert r.returncode == 0, r.stderr[-2000:]
    html = (out / "cyborg.html").read_text(encoding="utf-8")
    assert "作者未提及" in html
    assert sections_in(html) == EXPECTED_ORDER


def test_check_missing_section_fails(tmp_path: Path) -> None:
    """机检: 缺段即 fail (退出码非零), 产物不被视为有效。"""
    data_dir, templates_dir, out = make_isolated(tmp_path)
    build_file = data_dir / "builds" / "cyborg.json"
    data = json.loads(build_file.read_text(encoding="utf-8"))
    assert isinstance(data.get("variants"), list) and data["variants"]
    data["variants"][0].pop("pitfalls", None)
    build_file.write_text(json.dumps(data, ensure_ascii=False), encoding="utf-8")
    r = subprocess.run(
        [sys.executable, str(REPO / "scripts" / "build.py"),
         "--slug", "cyborg",
         "--data-dir", str(data_dir),
         "--templates-dir", str(templates_dir),
         "--out-dir", str(out)],
        cwd=REPO,
        capture_output=True,
        text=True,
    )
    assert r.returncode != 0, "missing section must fail"
    combined = (r.stdout + r.stderr).lower()
    assert "pitfalls" in combined or "缺段" in combined or "missing" in combined


def test_check_reordered_sections_fail(tmp_path: Path) -> None:
    """机检: 改序即 fail。直接对调产物两节顺序再跑机检 (隔离产物)."""
    data_dir, templates_dir, out = make_isolated(tmp_path)
    r = build_isolated(data_dir, templates_dir, out)
    assert r.returncode == 0, r.stderr[-2000:]
    html = (out / "cyborg.html").read_text(encoding="utf-8")
    a = html.index('data-section="upgrade"')
    b = html.index('data-section="shop"')
    assert a < b
    pattern = re.compile(
        r'(<section[^>]*data-section="upgrade".*?</section>)(.*?)'
        r'(<section[^>]*data-section="shop".*?</section>)',
        re.S,
    )
    m = pattern.search(html)
    assert m is not None
    reordered = html[: m.start()] + m.group(3) + m.group(2) + m.group(1) + html[m.end():]
    probe = tmp_path / "probe.html"
    probe.write_text(reordered, encoding="utf-8")
    r2 = subprocess.run(
        [sys.executable, str(REPO / "scripts" / "check.py"), str(probe)],
        cwd=REPO,
        capture_output=True,
        text=True,
    )
    assert r2.returncode != 0, "reordered sections must fail"


def test_missing_acceptance_warns_but_publishes(tmp_path: Path) -> None:
    """机检: 缺验收线只 warn 加待补徽标但可发布 (退出码仍 0)。"""
    data_dir, templates_dir, out = make_isolated(tmp_path)
    build_file = data_dir / "builds" / "cyborg.json"
    data = json.loads(build_file.read_text(encoding="utf-8"))
    data["variants"][0]["weapons_t1"] = []
    build_file.write_text(json.dumps(data, ensure_ascii=False), encoding="utf-8")
    r = subprocess.run(
        [sys.executable, str(REPO / "scripts" / "build.py"),
         "--slug", "cyborg",
         "--data-dir", str(data_dir),
         "--templates-dir", str(templates_dir),
         "--out-dir", str(out)],
        cwd=REPO,
        capture_output=True,
        text=True,
    )
    assert r.returncode == 0, f"acceptance gap must not fail: {r.stderr[-2000:]}"
    combined = r.stdout + r.stderr
    assert "WARN" in combined or "待补" in combined
    html = (out / "cyborg.html").read_text(encoding="utf-8")
    assert "待补口径" in html
    assert sections_in(html) == EXPECTED_ORDER


def test_mobile_tables_do_not_overflow(tmp_path: Path) -> None:
    """手机宽度下表格不溢出: 视口 + 限宽 + 表格滚动包装 (隔离产物)."""
    data_dir, templates_dir, out = make_isolated(tmp_path)
    r = build_isolated(data_dir, templates_dir, out)
    assert r.returncode == 0, r.stderr[-2000:]
    html = (out / "cyborg.html").read_text(encoding="utf-8")
    assert '<meta name="viewport"' in html
    assert "max-width" in html
    assert "overflow-x" in html
    assert "table-wrap" in html


def test_offline_double_click_readable(tmp_path: Path) -> None:
    """断网双击打开仍可读: 无外部样式/脚本阻塞, 相对链可 file:// 打开 (干净索引 + 隔离单页)."""
    data_dir, templates_dir, out = make_isolated(tmp_path)
    r = build_isolated(data_dir, templates_dir, out)
    assert r.returncode == 0, r.stderr[-2000:]
    char_html = (out / "cyborg.html").read_text(encoding="utf-8")
    index_html = (REPO / "docs" / "index.html").read_text(encoding="utf-8")
    for html in (char_html, index_html):
        assert "<html" in html and "</html>" in html
        assert "rel=\"stylesheet\" href=\"http" not in html
        assert "<script src=\"http" not in html
        assert "fetch(" not in html
    assert './index.html' in char_html
    # 干净索引无角色链, 但骨架可读.
    assert "<html" in index_html


def test_artifacts_are_generated_not_hand_edited(tmp_path: Path) -> None:
    """产物为构建生成, 无手改产物: 含生成标记指回构建命令 (索引 + 隔离单页)."""
    data_dir, templates_dir, out = make_isolated(tmp_path)
    r = build_isolated(data_dir, templates_dir, out)
    assert r.returncode == 0, r.stderr[-2000:]
    char_html = (out / "cyborg.html").read_text(encoding="utf-8")
    index_html = (REPO / "docs" / "index.html").read_text(encoding="utf-8")
    for html in (char_html, index_html):
        assert "GENERATED" in html
        assert "scripts/build.py" in html
