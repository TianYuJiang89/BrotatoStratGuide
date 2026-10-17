"""#14 E2E seam: 流程手册落地 + 首批真角色验证 (1-2).

Seams under test (pre-agreed per #8: E2E only):
- `python scripts/build.py --slug <slug>` / `--all` exit codes + `docs/*.html` bytes
- `python scripts/check.py <html>` exit codes
- `docs/sop/*.md` bytes (manual is explicit-call recoverable, not memory)
- `data/builds/<slug>.json` + `data/wiki-cache.json` bytes (single source)

No internal imports, no network. All assertions inspect CLI exit codes,
data file bytes, and generated file bytes.

#19 clean slate: 旧单变体工程师/赛博格测试数据已删 (data/builds 空, docs 0 可点),
#14 单变体验收测试已退役, 由 #21 多变体重做 + #22 reviewer 首单验收取代.
#14 失败批注留历史, 本文件仅保留手册/模板/口径规则三项, 不再断言旧真页.
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


def test_mentioned_attributes_count_as_ratings_not_empty() -> None:
    """提过即算口径规则仍在 SOP (#19 后仅断言手册, 旧单变体数据已删待 #21 重做)."""
    guide = (REPO / "docs" / "sop" / "new-character-guide.md").read_text(encoding="utf-8")
    assert "提过" in guide, "SOP must state mentioned-counts-as-rating rule"
