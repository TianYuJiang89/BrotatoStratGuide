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
from build import (  # noqa: E402
    ALLOWED_DIFFICULTIES,
    ENTERTAINMENT_MARKERS,
    EXPECTED_PRIMARY,
    EXPECTED_SECONDARY,
    SECTION_ORDER,
)


def _is_allowed_difficulty(value: str) -> bool:
    """覆盖制难度: 单档或合讲合并标签均可."""
    parts = [p.strip() for p in value.split("+")]
    return bool(parts) and all(p in ALLOWED_DIFFICULTIES for p in parts)


def check_file(path: Path) -> tuple[list[str], list[str]]:
    html_text = path.read_text(encoding="utf-8")
    errors: list[str] = []
    warns: list[str] = []
    found = re.findall(r'data-section="([^"]+)"', html_text)
    # 覆盖制: 每变体 11 段, N x 顺序.
    if not found or len(found) % len(SECTION_ORDER) != 0:
        errors.append(
            f"section order mismatch in {path}: expected N x {SECTION_ORDER}, got {found}"
        )
        return (errors, warns)
    for i in range(0, len(found), len(SECTION_ORDER)):
        chunk = found[i:i + len(SECTION_ORDER)]
        if chunk != SECTION_ORDER:
            errors.append(
                f"section order mismatch in {path}: expected {SECTION_ORDER}, got {chunk} (variant block {i // len(SECTION_ORDER)})"
            )
            return (errors, warns)
    n_variants = len(found) // len(SECTION_ORDER)
    # 动态诚实标签: 单变体徽章 vs 多变体 tablist.
    n_panels = len(re.findall(r'role="tabpanel"', html_text))
    if n_panels == 0:
        # 旧单页无面板 (过渡期): 视为单变体, 须有覆盖或直接内容.
        n_panels = n_variants
    n_tabs = len(re.findall(r'role="tab"', html_text))
    has_tablist = 'role="tablist"' in html_text
    has_badge = "coverbadge" in html_text or "覆盖" in html_text
    if n_variants == 1:
        if has_tablist or n_tabs != 0:
            errors.append("动态诚实标签即 fail: 单变体不留单 tab 栏 (须退化为覆盖徽章)")
        if not has_badge:
            errors.append("动态诚实标签即 fail: 单变体须退化为覆盖徽章")
    else:
        if not has_tablist:
            errors.append(f"动态诚实标签即 fail: {n_variants} 变体须有 tablist (A 胜出)")
        if n_tabs != n_variants:
            errors.append(f"动态诚实标签即 fail: 有几份证据出几个 tab, want {n_variants}, got {n_tabs}")
        for needle in ("aria-selected", "tabpanel", "44px", "sticky"):
            if needle not in html_text:
                errors.append(f"A tab 即 fail: 缺 {needle}")
                break
    # 主次全量拆两表: 每变体逐块查行数与原序。
    prim_secs = re.findall(r'data-section="attrs-primary".*?</section>', html_text, re.S)
    sec_secs = re.findall(r'data-section="attrs-secondary".*?</section>', html_text, re.S)
    if not prim_secs or not sec_secs or len(prim_secs) != n_variants or len(sec_secs) != n_variants:
        errors.append("missing attrs-primary/attrs-secondary section (每变体须各一)")
        return (errors, warns)
    for prim_html in prim_secs:
        pos: list[int] = []
        for en in EXPECTED_PRIMARY:
            idx = prim_html.find(f"({en})")
            if idx < 0:
                errors.append(f"术语对不上即 fail: 主表缺 {en}")
            else:
                pos.append(idx)
        if pos != sorted(pos):
            errors.append("primary order mismatch (须随 wiki Stats 原序)")
    for sec_html in sec_secs:
        pos2: list[int] = []
        for en in EXPECTED_SECONDARY:
            idx = sec_html.find(f"({en})")
            if idx < 0:
                errors.append(f"术语对不上即 fail: 次级表缺 {en}")
            else:
                pos2.append(idx)
        if pos2 != sorted(pos2):
            errors.append("secondary order mismatch (须随 wiki 次级表原序)")
    # 角标缺失即 fail: 每变体 Curse 与 % Reroll Price 必须带 DLC。
    for prim_html in prim_secs:
        if "Curse" in prim_html and "DLC" not in prim_html:
            errors.append("角标缺失即 fail: Curse 缺 DLC 角标")
            break
    for sec_html in sec_secs:
        if "Reroll Price" in sec_html and "DLC" not in sec_html:
            errors.append("角标缺失即 fail: % Reroll Price 缺 DLC 角标")
            break
    # 武器道具 hover (#15): 每变体有数据行 (无诚实空出) 必须有悬浮, 空口径行可免。
    for sec_html in re.findall(r'data-section="weapons".*?</section>', html_text, re.S):
        if "待补口径" not in sec_html and "has-tip" not in sec_html:
            errors.append("hover 缺失即 fail: weapons 区有名无悬浮 (未知武器/道具或模板回归)")
            break
    for sec_html in re.findall(r'data-section="items".*?</section>', html_text, re.S):
        if "待补口径" not in sec_html and "has-tip" not in sec_html:
            errors.append("hover 缺失即 fail: items 区有名无悬浮 (未知武器/道具或模板回归)")
            break
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
    # #13 取材门禁每变体: 难度三档 (单档或合讲) + 娱乐局不进候选 + Top3 不超 3 + 链接齐全。
    for sec in re.findall(r'data-section="source".*?</section>', html_text, re.S):
        lowered = sec.lower()
        for marker in ENTERTAINMENT_MARKERS:
            if marker in lowered:
                errors.append(f"取材娱乐局即 fail: source 区命中 {marker!r} (永不作主引用/不进候选)")
                break
        cand_count = len(re.findall(r'data-candidate="', sec))
        if cand_count > 3:
            errors.append(f"取材 Top3 即 fail: 1 主 + 不超 2 补充, got {cand_count}")
        for diff in re.findall(r"难度：([^<\/]+)", sec):
            diff_text = diff.strip()
            if not diff_text or "待补" in diff_text or "占位" in diff_text or diff_text == "—":
                continue
            if not _is_allowed_difficulty(diff_text):
                errors.append(f"取材难度只认三档即 fail: {diff_text!r}")
                break
        if "youtube.com" not in sec and "youtu.be" not in sec and "待补" not in sec:
            errors.append("取材链接错即 fail: source 区缺 YouTube 链接且无待补徽标")
        # 巡检徽标只 warn (可发布):待补/待重审/资源待重审。
        if "待重审" in sec:
            warns.append("取材待重审 (版本漂移/旧日期, 人工触发复核)")
        if "资源待重审" in sec:
            warns.append("资源待重审 (HEAD 失效, 切应急前人工复核)")
        if "待补口径" in sec or "暂无可用主引用" in sec:
            warns.append("取材待补 (Top3/双标注/字幕缺项, 仍可发布)")
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
