"""产物机检 (#10): 10 段齐全改序 fail + 术语全量角标排序图标校验.

用法: python scripts/check.py <html-file>
缺段/改序/术语对不上/角标缺失/图标缺失即 fail (退出码 1), 通过即 OK。
待校对只 warn (退出码仍 0)。
"""

from __future__ import annotations

import re
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from build import EXPECTED_PRIMARY, EXPECTED_SECONDARY, SECTION_ORDER  # noqa: E402


def check_file(path: Path) -> tuple[list[str], list[str]]:
    html_text = path.read_text(encoding="utf-8")
    errors: list[str] = []
    warns: list[str] = []
    found = re.findall(r'data-section="([^"]+)"', html_text)
    if found != SECTION_ORDER:
        errors.append(
            f"section order mismatch in {path}: expected {SECTION_ORDER}, got {found}"
        )
        return (errors, warns)
    # 主次全量拆两表: 行数与原序。
    m_primary = re.search(r'data-section="attrs-primary".*?</section>', html_text, re.S)
    m_secondary = re.search(r'data-section="attrs-secondary".*?</section>', html_text, re.S)
    if not m_primary or not m_secondary:
        errors.append("missing attrs-primary/attrs-secondary section")
        return (errors, warns)
    prim_html = m_primary.group(0)
    sec_html = m_secondary.group(0)
    pos: list[int] = []
    for en in EXPECTED_PRIMARY:
        idx = prim_html.find(f"({en})")
        if idx < 0:
            errors.append(f"术语对不上即 fail: 主表缺 {en}")
        else:
            pos.append(idx)
    if pos != sorted(pos):
        errors.append("primary order mismatch (须随 wiki Stats 原序)")
    pos2: list[int] = []
    for en in EXPECTED_SECONDARY:
        idx = sec_html.find(f"({en})")
        if idx < 0:
            errors.append(f"术语对不上即 fail: 次级表缺 {en}")
        else:
            pos2.append(idx)
    if pos2 != sorted(pos2):
        errors.append("secondary order mismatch (须随 wiki 次级表原序)")
    # 角标缺失即 fail: Curse 与 % Reroll Price 必须带 DLC。
    if "Curse" in prim_html and "DLC" not in prim_html:
        errors.append("角标缺失即 fail: Curse 缺 DLC 角标")
    if "Reroll Price" in sec_html and "DLC" not in sec_html:
        errors.append("角标缺失即 fail: % Reroll Price 缺 DLC 角标")
    # 武器道具 hover (#15): 有数据行 (无诚实空出) 必须有悬浮, 空口径行可免。
    for sec_name in ("weapons", "items"):
        m_sec = re.search(rf'data-section="{sec_name}".*?</section>', html_text, re.S)
        if m_sec and "待补口径" not in m_sec.group(0) and "has-tip" not in m_sec.group(0):
            errors.append(f"hover 缺失即 fail: {sec_name} 区有名无悬浮 (未知武器/道具或模板回归)")
    # 图标: 主表 wiki 热链, 次级 ◆ 占位。
    if "wiki.spellsandguns.com" not in html_text:
        errors.append("图标缺失即 fail: 主表缺 wiki 热链图标 (注册表唯一 URL 源)")
    if "◆" not in html_text:
        errors.append("图标缺失即 fail: 次级缺 ◆ 占位")
    # 待校对只 warn。
    if "※" in html_text or "待校对" in html_text:
        warns.append("术语待校对 (※)，中文以客户端简中为准")
    return (errors, warns)


def main(argv: list[str] | None = None) -> int:
    args = argv if argv is not None else sys.argv[1:]
    if len(args) != 1:
        print("usage: python scripts/check.py <html-file>", file=sys.stderr)
        return 2
    errors, warns = check_file(Path(args[0]))
    for w in warns:
        print(f"WARN: {w}")
    if errors:
        for err in errors:
            print(f"FAIL: {err}", file=sys.stderr)
        return 1
    print("OK: sections ordered, terms full, badges/icons ok")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
