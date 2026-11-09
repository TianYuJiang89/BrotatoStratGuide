"""陈坑清扫 (#97): 重跑后 N 变小, 清掉超编编号件与 agent log.

06/07/08 的 per-item 件按序号落盘 (`per_phase/00.json`、`per_item/00.json`、
`per_pitfall/00.json`) 且 N 由 agent 定, 重跑切出更少项时旧索引件没人清,
`check_segment2` 的「wording log 数 == N」直接顶爆 (fisherman #87: N=10 → N=8, 实得 14)。

单一来源: 三个 loop 共用本函数, 禁各写一份 (口径漂移)。
fail loud: 删不掉即报错退出 (静默留下会把 check 顶爆, 且属 strip 掉证据)。
"""

from __future__ import annotations

import re
from pathlib import Path

LOG_RE = re.compile(r"^(?P<prefix>.+)-(?P<idx>\d+)\.log")


def clean_stale_indexed(step_dir: Path, per_dir: Path, keep: int,
                        log_prefix: str) -> list[str]:
    """清掉 index >= keep 的编号件与该步 agent log (非编号旧代件也清).

    参数:
      step_dir: 本步步目录 (放 agent log), 例 `steps/06-phases`
      per_dir: 编号件目录 (`per_phase` / `per_item` / `per_pitfall`)
      keep: 本次运行的项数 (N), index >= keep 即超编
      log_prefix: log 文件名前缀 (`agent-wording`)

    返回: 被删文件名列表 (相对步目录, 供测试/日志); 无残留返回 []。
    """
    removed: list[str] = []
    if per_dir.is_dir():
        for path in sorted(per_dir.glob("*.json")):
            try:
                idx = int(path.stem)
            except ValueError:
                # 旧代 Safe 命名残留: N 变后无法对齐, 清掉重跑
                idx = keep
            if idx >= keep:
                _unlink(path, removed, step_dir)
    for path in sorted(step_dir.glob(f"{log_prefix}-*.log*")):
        m = LOG_RE.match(path.name)
        if m and m.group("prefix") == log_prefix and int(m.group("idx")) >= keep:
            _unlink(path, removed, step_dir)
    return removed


def _unlink(path: Path, removed: list[str], base: Path) -> None:
    """删一个残留件; 返回相对 base 的路径 (step_dir, 06/07/08 同一口径)."""
    try:
        path.unlink()
    except OSError as e:
        raise SystemExit(f"FAIL: 陈坑清扫删不掉 {path} ({e!r}); 残留会把 check 顶爆, 请先解锁再重跑")
    removed.append(path.relative_to(base).as_posix())
