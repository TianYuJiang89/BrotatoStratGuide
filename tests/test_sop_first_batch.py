"""#14 E2E seam: 流程手册落地 + 首批真角色验证 (1-2).

Seams under test (pre-agreed per #8: E2E only):
- `python scripts/build.py --slug <slug>` / `--all` exit codes + `docs/*.html` bytes
- `python scripts/check.py <html>` exit codes
- `docs/sop/*.md` bytes (manual is explicit-call recoverable, not memory)
- `data/builds/<slug>.json` + `data/wiki-cache.json` bytes (single source)

No internal imports, no network. All assertions inspect CLI exit codes,
data file bytes, and generated file bytes.
"""

from __future__ import annotations

import json
import re
import subprocess
import sys
from pathlib import Path

REPO = Path(__file__).resolve().parent.parent
BUILD = [sys.executable, "scripts/build.py"]
CHECK = [sys.executable, "scripts/check.py"]

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
    return subprocess.run([*BUILD, *args], cwd=cwd, capture_output=True, text=True)


def sections_in(html: str) -> list[str]:
    return re.findall(r'data-section="([^"]+)"', html)


def test_sop_manual_lands_on_main_explicit_call() -> None:
    """手册落主干，新 session 显式调用可恢复共识：两文件齐全，含调用约定与三件事与三问。"""
    guide = REPO / "docs" / "sop" / "new-character-guide.md"
    template = REPO / "docs" / "sop" / "character-issue-template.md"
    assert guide.exists(), "docs/sop/new-character-guide.md must land on main (#14)"
    assert template.exists(), "docs/sop/character-issue-template.md must land on main (#14)"
    text = guide.read_text(encoding="utf-8")
    # 显式调用可恢复共识：新 session 先读手册全文，再读决议，不靠记忆。
    assert "先读本文件全文" in text, "SOP must state explicit-call recovery (no memory)"
    # 全链机器跑，人只做三件事：报角色名、选定候选、验收。
    for needle in ("报角色名", "选定候选", "验收"):
        assert needle in text, f"SOP must list human 3 things ({needle})"
    # 内容规则：武器把数不限一句话视频口径；道具下限弹性；商店升级两层先 Top3；避坑通用致命；高难只收高难变招。
    for needle in ("把数不限", "视频口径", "Top3", "避坑", "高难"):
        assert needle in text, f"SOP must lock content rules ({needle})"
    # 10 段顺序 + 机检 + 产物人不手改。
    assert "10 段" in text or "10段" in text or "mechanism" in text.lower()
    assert "人不手改" in text or "绝不手改" in text
    # 三问验收：选片对不对、转述忠不忠实、评级违不违手感；全过发布，不过批段重改；带待补照发，排版不重验。
    for needle in ("三问", "待补"):
        assert needle in text, f"SOP must state 3-question promo with 待补 ({needle})"


def test_per_character_template_has_fixed_sections_and_prohibitions() -> None:
    """逐角色单含固定段与禁止事项：模板原样填，人三问全过即发布，去草稿索引可点关单。"""
    template = REPO / "docs" / "sop" / "character-issue-template.md"
    assert template.exists()
    text = template.read_text(encoding="utf-8")
    assert "Part of #8" in text or "Part of #1" in text, "template must carry parent link"
    for needle in ("目标角色", "选定取材", "执行步骤", "禁止", "验收"):
        assert needle in text, f"template must have fixed section ({needle})"
    # 禁止事项：不编把数评级、不自造中文、不藏空段、不把娱乐局当主引用、后缀保留。
    for needle in ("不编", "不自造", "不藏", "娱乐局"):
        assert needle in text, f"template must list prohibitions ({needle})"
    # 人只做三件事 + 三问。
    assert "三问" in text


def test_first_real_character_engineer_builds_all_10_sections() -> None:
    """首批真角色页达验收线或带待补发布：engineer 全 10 段，Top3 真片，双标注，机检绿。"""
    r = run_build("--slug", "engineer")
    assert r.returncode == 0, f"engineer build must pass (fail=block, warn=publish): {r.stderr[-2000:]}"
    html = (REPO / "docs" / "engineer.html").read_text(encoding="utf-8")
    assert sections_in(html) == EXPECTED_ORDER, "engineer must carry all 10 sections in order"
    # 真片：主引用为 Engineer Ultimate Guide 真视频，非 demo 占位。
    assert "Wge0_hd9Rt8" in html, "engineer main must be real video Wge0_hd9Rt8"
    assert "youtube.com/watch?v=Wge0_hd9Rt8" in html
    assert "Ultimate" in html
    assert "教学局" in html, "Guide suffix must render 教学局"
    assert "demo-placeholder" not in html, "real character must not carry demo placeholder"
    # 双标注：发布日期 + 游戏版本齐全。
    assert "2026-09-01" in html, "engineer published 2026-09-01 (RSS upload_date)"
    assert "1.1.15" in html, "engineer game_version must carry Steam version from description"
    # 武器把数不限每把一句话只认视频口径：Wrench 真口径，T1>=1。
    assert "Wrench" in html, "engineer T1 must carry real Wrench (video: wrenches only)"
    # 道具下限弹性够复现：至少 3 件，Turret/Coffee/Improved Tools 均为视频实提。
    sec_items = re.search(r'data-section="items".*?</section>', html, re.S)
    assert sec_items is not None
    for needle in ("Turret", "Coffee", "Improved Tools"):
        assert needle in sec_items.group(0), f"engineer items must carry real {needle}"
    # 商店升级两层先 Top3 再点名：两段非空且含 Top3。
    for sec_name in ("upgrade", "shop"):
        m = re.search(rf'data-section="{sec_name}".*?</section>', html, re.S)
        assert m is not None
        assert "Top3" in m.group(0), f"{sec_name} must carry Top3 two-layer writing"
    # 产物人不手改标记 + 机检全绿。
    assert "GENERATED" in html and "scripts/build.py" in html
    r2 = subprocess.run([*CHECK, str(REPO / "docs" / "engineer.html")],
                        cwd=REPO, capture_output=True, text=True)
    assert r2.returncode == 0, f"engineer check.py must be green: {r2.stderr[-2000:]}"


def test_engineer_source_top3_supplement_and_captions() -> None:
    """Top3：1 主 + 1 补充均为 Ultimate Guide，有字幕，已纠专名，无娱乐局。"""
    data = json.loads((REPO / "data" / "builds" / "engineer.json").read_text(encoding="utf-8"))
    source = data.get("source")
    assert isinstance(source, dict)
    cands = source.get("candidates")
    assert isinstance(cands, list) and 1 <= len(cands) <= 3, "Top3: 1 主 + 不超 2 补充"
    assert cands[0].get("video_id") == "Wge0_hd9Rt8", "main must equal candidates[0]"
    assert source.get("video_id") == "Wge0_hd9Rt8"
    # 补充为第二支 Engineer Ultimate Guide 真片。
    ids = {c.get("video_id") for c in cands}
    assert "QbKT2VHnqbc" in ids, "supplement must be real QbKT2VHnqbc"
    for c in cands:
        assert c.get("difficulty") == "Ultimate", "difficulty only Ultimate"
        assert "tier list" not in str(c.get("title")).lower()
        assert "challenge" not in str(c.get("title")).lower()
        assert c.get("has_captions") is True, "both candidates carry auto captions"
    assert source.get("has_captions") is True
    transcript = source.get("transcript")
    assert isinstance(transcript, dict)
    assert transcript.get("captions") == "auto"
    assert transcript.get("corrected") is True, "must对照 wiki 纠专名 (Brotato/Bart)"
    assert "frames" not in transcript and "multimodal" not in transcript


def test_index_clickable_after_first_batch_no_draft() -> None:
    """三问全过即去草稿索引可点：engineer + cyborg 均可点，无死链，搜索筛选仍全能力。"""
    r = run_build("--all")
    assert r.returncode == 0, r.stderr[-2000:]
    html = (REPO / "docs" / "index.html").read_text(encoding="utf-8")
    assert "./engineer.html" in html, "engineer must be clickable (去草稿)"
    assert "./cyborg.html" in html, "cyborg stays clickable"
    assert (REPO / "docs" / "engineer.html").exists()
    # 未建页不点进空页。
    for slug in ("mage", "sailor", "ranger"):
        assert f"./{slug}.html" not in html
    # 全能力不回归：搜索 + 筛选 + 计数 + 空状态 + 头像。
    for needle in ('id="q"', 'id="dlc"', 'id="playable"', 'id="count"', "🥔"):
        assert needle in html
    m = re.search(r"var ROSTER\s*=\s*(\[.*?\]);", html, re.S)
    assert m is not None
    roster = json.loads(m.group(1))
    assert len(roster) == 64
    by_slug = {e["slug"]: e for e in roster}
    assert by_slug["engineer"].get("playable") is True
    assert by_slug["cyborg"].get("playable") is True
