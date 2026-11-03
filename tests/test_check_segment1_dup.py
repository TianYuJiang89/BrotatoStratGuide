"""#90 check_segment1 相邻复读口径: 真复读 WARN, 折叠回归 FAIL.

真复读 (golem/ultimate #85 前例: id 102/103 同文 `Clear these enemies.`,
VTT 词级时间戳 42.8s vs 43.8s 证明两次独立 utterance) 与折叠 artifact
在 sentences.json 层面不可区分, 须人判. 机器只对 >=3 对 FAIL,
1-2 对 WARN 交 reviewer 按词级时间戳复核.
"""
from __future__ import annotations

import importlib.util
from pathlib import Path

REPO = Path(__file__).resolve().parent.parent


def _load(name: str, rel: str):
    spec = importlib.util.spec_from_file_location(name, str(REPO / rel))
    assert spec is not None and spec.loader is not None
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


def _texts(n: int, dup_pairs: int) -> list[str]:
    """n 句, 前 dup_pairs 对相邻重复 (第 2k-1 与 2k 句同文)."""
    out = []
    for i in range(n):
        if dup_pairs > 0 and i % 2 == 1 and (i // 2) < dup_pairs:
            out.append(out[-1])
        else:
            out.append(f"sentence {i}.")
    return out


def test_no_dup_passes() -> None:
    m = _load("check_segment1", "scripts/check_segment1.py")
    assert hasattr(m, "classify_adjacent_dups"), "须有分类函数 (真复读须人判, 机器只分类)"
    fail_idx, warn_idx = m.classify_adjacent_dups(_texts(10, 0))
    assert fail_idx == [] and warn_idx == []


def test_golem_style_single_pair_warns_not_fails() -> None:
    m = _load("check_segment1", "scripts/check_segment1.py")
    fail_idx, warn_idx = m.classify_adjacent_dups(_texts(10, 1))
    assert fail_idx == [], "1 对须不 FAIL (golem 102/103 真复读前例)"
    assert warn_idx == [1], "1 对须 WARN 并定位后一句下标"


def test_two_pairs_warn() -> None:
    m = _load("check_segment1", "scripts/check_segment1.py")
    fail_idx, warn_idx = m.classify_adjacent_dups(_texts(10, 2))
    assert fail_idx == []
    assert warn_idx == [1, 3]


def test_three_pairs_fail_as_fold_regression_signal() -> None:
    m = _load("check_segment1", "scripts/check_segment1.py")
    fail_idx, warn_idx = m.classify_adjacent_dups(_texts(10, 3))
    assert warn_idx == []
    assert fail_idx == [1, 3, 5], ">=3 对须 FAIL (折叠回归信号)"


def test_check_wires_warn_not_fail_for_few_dups() -> None:
    import inspect
    m = _load("check_segment1", "scripts/check_segment1.py")
    src = inspect.getsource(m)
    assert "classify_adjacent_dups" in src
    assert "got {adj}" not in src, "一刀切 got-N FAIL 须退役 (#90)"
