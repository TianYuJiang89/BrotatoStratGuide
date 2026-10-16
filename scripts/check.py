"""产物结构机检 (#9): 校验单角色页 10 段齐全且顺序正确.

用法: python scripts/check.py <html-file>
缺段/改序即 fail (退出码 1), 通过即 OK (退出码 0)。
"""

from __future__ import annotations

import re
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from build import SECTION_ORDER  # noqa: E402


def check_file(path: Path) -> list[str]:
    html_text = path.read_text(encoding="utf-8")
    found = re.findall(r'data-section="([^"]+)"', html_text)
    if found != SECTION_ORDER:
        return [
            f"section order mismatch in {path}: "
            f"expected {SECTION_ORDER}, got {found}"
        ]
    return []


def main(argv: list[str] | None = None) -> int:
    args = argv if argv is not None else sys.argv[1:]
    if len(args) != 1:
        print("usage: python scripts/check.py <html-file>", file=sys.stderr)
        return 2
    errors = check_file(Path(args[0]))
    if errors:
        for err in errors:
            print(f"FAIL: {err}", file=sys.stderr)
        return 1
    print("OK: sections ordered")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
