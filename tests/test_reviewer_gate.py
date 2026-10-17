"""#18 E2E seam: SOP 拆细 + reviewer 块级 gate 落 SOP.

Seams under test (pre-agreed per #16 Notes: E2E only):
- `docs/sop/*.md` bytes (manual is explicit-call recoverable, not memory)
- No internal imports, no network.
"""

from __future__ import annotations

from pathlib import Path

REPO = Path(__file__).resolve().parent.parent


def test_sop_splits_black_box_into_extract_clear_fill() -> None:
    """大黑箱拆细: 抽取 -> 交叉表清零 -> 填表, 交叉表格式引用 #17."""
    guide = REPO / "docs" / "sop" / "new-character-guide.md"
    assert guide.exists()
    text = guide.read_text(encoding="utf-8")
    # 拆细三段都在 (抽取 / 交叉表清零 / 填表).
    for needle in ("抽取", "交叉表", "清零", "填表"):
        assert needle in text, f"SOP 必须拆细含 {needle}"
    # 交叉表格式先定 (#17): 输出落 data/mentions/<slug>.json, 脚本名可跑.
    for needle in ("data/mentions/", "build_mentions", "check_mentions"):
        assert needle in text, f"SOP 必须引用 #17 交叉表资产 ({needle})"
    # 只 warn 不 fail, 不动 check.py 门禁.
    assert "warn" in text.lower(), "SOP 必须载明 check_mentions 只 warn"
    assert "check.py" in text


def test_sop_names_reviewer_block_gate_and_no_self_review() -> None:
    """reviewer 块级审 + drafter 不审己稿 + 降级另开票 + 人三问退为末闸."""
    guide = (REPO / "docs" / "sop" / "new-character-guide.md").read_text(encoding="utf-8")
    for needle in ("reviewer", "块级", "不审己稿", "降级", "另开票"):
        assert needle in text_lower_or_original(guide, needle), f"SOP 必须载明 {needle}"
    # 人三问仍在, 但退为末闸 (reviewer 在前).
    assert "三问" in guide


def text_lower_or_original(haystack: str, needle: str) -> str:
    # reviewer 大小写不敏感, 中文精确.
    if needle == "reviewer":
        assert "reviewer" in haystack.lower(), "SOP 必须载明 reviewer"
        return needle
    assert needle in haystack, f"SOP 必须载明 {needle}"
    return needle


def test_reviewer_checklist_exists_with_three_checks() -> None:
    """新增 reviewer 清单: 10段x变体逐块查三件事, 输出意见清单给 drafter 改."""
    checklist = REPO / "docs" / "sop" / "reviewer-checklist.md"
    assert checklist.exists(), "docs/sop/reviewer-checklist.md 必须新增 (#18)"
    text = checklist.read_text(encoding="utf-8")
    for needle in ("10", "变体", "清零", "出处", "意见清单", "drafter"):
        assert needle in text, f"reviewer 清单必须含 {needle}"
    # 三件事: 命中清零了没 / 每条 rating 有无出处 / 有无无出处 rating (疑为编).
    assert "无出处" in text or "疑为编" in text


def test_character_template_synced_with_cross_table_and_reviewer() -> None:
    """character-issue-template.md 同步: 交叉表清零步骤 + reviewer 块级 gate."""
    template = REPO / "docs" / "sop" / "character-issue-template.md"
    assert template.exists()
    text = template.read_text(encoding="utf-8")
    for needle in ("交叉表", "清零", "reviewer"):
        # reviewer 大小写不敏感
        if needle == "reviewer":
            assert "reviewer" in text.lower(), "模板必须同步 reviewer gate"
        else:
            assert needle in text, f"模板必须同步 {needle}"
    # 模板仍保留固定段与三问 (不回归 #14).
    assert "三问" in text
