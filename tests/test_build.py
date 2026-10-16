"""Skeleton E2E seam: build CLI + generated HTML external behavior only.

Seams under test (pre-agreed per #8 Testing Decisions: 端到端为最高且唯一的 seam):
- `python scripts/build.py --slug <slug>` / `--all` exit codes + `docs/*.html` artifacts
- 机检门禁: 缺段/改序 => fail; 缺验收线 => warn + 待补徽标但可发布
- 产物可读性: 手机不溢出 / 离线双击可读 / 构建生成标记

No internal imports, no network. All assertions inspect CLI exit codes
and generated file bytes.
"""

from __future__ import annotations

import json
import re
import subprocess
import sys
from pathlib import Path

REPO = Path(__file__).resolve().parent.parent
BUILD = [sys.executable, "scripts/build.py"]

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


def test_per_slug_build_produces_ordered_sections() -> None:
    """单角色构建: 10 段齐全且顺序正确 (赛博格)。"""
    r = run_build("--slug", "cyborg")
    assert r.returncode == 0, f"build failed: {r.stderr[-2000:]}"
    html = (REPO / "docs" / "cyborg.html").read_text(encoding="utf-8")
    assert sections_in(html) == EXPECTED_ORDER


def test_index_links_to_character_page() -> None:
    """索引页可点进单角色页。"""
    r = run_build("--all")
    assert r.returncode == 0, f"build --all failed: {r.stderr[-2000:]}"
    index = (REPO / "docs" / "index.html").read_text(encoding="utf-8")
    assert 'href="./cyborg.html"' in index or 'href="cyborg.html"' in index


def test_full_and_per_slug_builds_both_run() -> None:
    """全量构建与按角色构建均可跑。"""
    r1 = run_build("--slug", "cyborg")
    r2 = run_build("--all")
    assert r1.returncode == 0, r1.stderr[-2000:]
    assert r2.returncode == 0, r2.stderr[-2000:]
    assert (REPO / "docs" / "cyborg.html").exists()
    assert (REPO / "docs" / "index.html").exists()


def test_honest_empty_sections_are_shown_not_hidden() -> None:
    """无口径段显示诚实空出而非隐藏: 空评级渲染为作者未提及, 段仍在。"""
    r = run_build("--slug", "cyborg")
    assert r.returncode == 0
    html = (REPO / "docs" / "cyborg.html").read_text(encoding="utf-8")
    # 骨架赛博格数据故意留至少一个空评级, 证明空出路径。
    assert "作者未提及" in html
    # 所有段仍齐全 (未隐藏)。
    assert sections_in(html) == EXPECTED_ORDER


def test_check_missing_section_fails(tmp_path: Path) -> None:
    """机检: 缺段即 fail (退出码非零), 产物不被视为有效。"""
    # 用最小夹具喂构建: 复制仓库数据到隔离目录, 删掉一节后跑机检。
    import shutil

    work = tmp_path / "work"
    shutil.copytree(REPO / "data", work / "data")
    shutil.copytree(REPO / "templates", work / "templates")
    build_file = work / "data" / "builds" / "cyborg.json"
    data = json.loads(build_file.read_text(encoding="utf-8"))
    # 删掉避坑段, 模拟缺段。
    data.pop("pitfalls", None)
    build_file.write_text(json.dumps(data, ensure_ascii=False), encoding="utf-8")
    out = tmp_path / "out"
    r = subprocess.run(
        [sys.executable, str(REPO / "scripts" / "build.py"),
         "--slug", "cyborg",
         "--data-dir", str(work / "data"),
         "--templates-dir", str(work / "templates"),
         "--out-dir", str(out)],
        cwd=REPO,
        capture_output=True,
        text=True,
    )
    assert r.returncode != 0, "missing section must fail"
    combined = (r.stdout + r.stderr).lower()
    assert "pitfalls" in combined or "缺段" in combined or "missing" in combined


def test_check_reordered_sections_fail(tmp_path: Path) -> None:
    """机检: 改序即 fail。直接对调产物两节顺序再跑机检。"""
    r = run_build("--slug", "cyborg")
    assert r.returncode == 0
    html = (REPO / "docs" / "cyborg.html").read_text(encoding="utf-8")
    # 对调升级与商店两节的 data-section 顺序 (内容不动, 只换顺序标记)。
    a = html.index('data-section="upgrade"')
    b = html.index('data-section="shop"')
    assert a < b
    # 把 shop 整节搬到 upgrade 之前: 用正则切出两节并交换。
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
    import shutil

    work = tmp_path / "work"
    shutil.copytree(REPO / "data", work / "data")
    shutil.copytree(REPO / "templates", work / "templates")
    build_file = work / "data" / "builds" / "cyborg.json"
    data = json.loads(build_file.read_text(encoding="utf-8"))
    # 抽空 T1 武器, 跌破验收线 (T1>=1) 但结构仍全。
    data["weapons_t1"] = []
    build_file.write_text(json.dumps(data, ensure_ascii=False), encoding="utf-8")
    out = tmp_path / "out"
    r = subprocess.run(
        [sys.executable, str(REPO / "scripts" / "build.py"),
         "--slug", "cyborg",
         "--data-dir", str(work / "data"),
         "--templates-dir", str(work / "templates"),
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
    # 段仍齐全 (warn 不隐藏段)。
    assert sections_in(html) == EXPECTED_ORDER


def test_mobile_tables_do_not_overflow() -> None:
    """手机宽度下表格不溢出: 视口 + 限宽 + 表格滚动包装。"""
    html = (REPO / "docs" / "cyborg.html").read_text(encoding="utf-8")
    assert '<meta name="viewport"' in html
    assert "max-width" in html
    assert "overflow-x" in html
    assert "table-wrap" in html


def test_offline_double_click_readable() -> None:
    """断网双击打开仍可读: 无外部样式/脚本阻塞, 相对链可 file:// 打开。"""
    char_html = (REPO / "docs" / "cyborg.html").read_text(encoding="utf-8")
    index_html = (REPO / "docs" / "index.html").read_text(encoding="utf-8")
    for html in (char_html, index_html):
        assert "<html" in html and "</html>" in html
        # 无外部阻塞式引用 (外链 CSS/JS/fetch)。
        assert "rel=\"stylesheet\" href=\"http" not in html
        assert "<script src=\"http" not in html
        assert "fetch(" not in html
    # 相对链可 file:// 打开: 单页回链索引, 索引可点进单页。
    assert './index.html' in char_html
    assert './cyborg.html' in index_html


def test_artifacts_are_generated_not_hand_edited() -> None:
    """产物为构建生成, 无手改产物: 含生成标记指回构建命令。"""
    for name in ("cyborg.html", "index.html"):
        html = (REPO / "docs" / name).read_text(encoding="utf-8")
        assert "GENERATED" in html
        assert "scripts/build.py" in html
