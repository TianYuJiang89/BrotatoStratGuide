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
    # 三处统一 (#12): 主图标同一渲染路径, 有图三件套 + 原文件标记 + 应急路径, 缩略图不用原图。
    sic_tags = re.findall(r'<img class="sic"[^>]*>', html_text)
    if not sic_tags:
        errors.append("图标缺失即 fail: 三处无统一 sic 图标 (属性/武器/道具须走同一函数)")
    for tag in sic_tags:
        if 'loading="lazy"' not in tag:
            errors.append("图标缺失即 fail: sic 缺 loading=lazy (懒加载生效)")
            break
        if 'referrerpolicy="no-referrer"' not in tag:
            errors.append("图标缺失即 fail: sic 缺 referrerpolicy=no-referrer")
            break
        if 'onerror="this.remove()"' not in tag:
            errors.append("图标缺失即 fail: sic 缺 onerror 失败移除 (断图仍可读)")
            break
        if "data-file=" not in tag:
            errors.append("图标缺失即 fail: sic 缺 data-file 原文件标记")
            break
        if "data-local=" not in tag:
            errors.append("图标缺失即 fail: sic 缺 data-local 应急路径")
            break
        if "/thumb/" not in tag:
            errors.append("图标缺失即 fail: sic 须用缩略图不用原图 (/thumb/)")
            break
    # 全页懒加载 (#12 断图断网可读): 每个 img 懒加载 + 失败移除, 无阻塞式外链。
    for tag in re.findall(r"<img[^>]*>", html_text):
        if 'loading="lazy"' not in tag:
            errors.append("图标缺失即 fail: 存在非懒加载 img (懒加载生效)")
            break
        if 'onerror=' not in tag:
            errors.append("图标缺失即 fail: 存在无失败移除 img (断图仍可读)")
            break
    if 'rel="stylesheet" href="http' in html_text or '<script src="http' in html_text:
        errors.append("离线可读即 fail: 存在阻塞式外链 (断网双击须可开)")
    if "fetch(" in html_text:
        errors.append("离线可读即 fail: 存在运行时 fetch (须构建时内联)")
    # 页脚署名 (#12): 固定署名行 + 原页链 + 译自来源站双链 + 许可链, 缺一即 fail。
    m_foot = re.search(r'<div class="footer">.*?</div>', html_text, re.S)
    foot = m_foot.group(0) if m_foot else ""
    for needle, msg in (
        ("Blobfish", "页脚缺失即 fail: 缺图标 © Blobfish 署名"),
        ("brotato.wiki.spellsandguns.com", "页脚缺失即 fail: 缺 wiki 来源链"),
        ("creativecommons.org/licenses/by-sa/4.0", "页脚缺失即 fail: 缺 CC BY-SA 文本许可链"),
        ("Characters", "页脚缺失即 fail: 缺 Characters 原页链"),
        ("Wiki", "页脚缺失即 fail: 缺译自来源站 Wiki 链 (双链之一)"),
    ):
        if needle not in foot:
            errors.append(msg)
    if ("转述" not in foot and "不搬" not in foot):
        errors.append("页脚缺失即 fail: 缺转述非搬运/不搬截图原片声明")
    if "后续合规票" in html_text:
        errors.append("页脚缺失即 fail: 骨架占位文案未替换为合规署名")
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
