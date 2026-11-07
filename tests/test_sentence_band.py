#!/usr/bin/env python3
"""#92: 01-sentences 折叠后句数闸 (密度带 + 折叠有效比) 回归测试.

旧口径绝对带 300-600 是拿 31-38 分钟片校准的, 片长一长必红:
demon/ultimate (#86) 47:33 → 折叠后 726 句被误杀, 而折叠比 0.330 / 密度 15.3
与历史全绿 12 例 (0.233-0.330 / 11.3-15.3) 同档.
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

import pytest

REPO = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(REPO / "scripts"))

from sentence_band import (  # noqa: E402
    DENSITY_MAX,
    DENSITY_MIN,
    FOLD_RATIO_MAX,
    FOLD_RATIO_MIN,
    band_errors_for_workdir,
    count_raw_cues,
    parse_duration_seconds,
    sentence_band_errors,
)


VTT_ROLLING = """WEBVTT
Kind: captions
Language: en

00:00:00.000 --> 00:00:02.000
Hello my friends

00:00:01.500 --> 00:00:03.000
Hello my friends and welcome

00:00:02.800 --> 00:00:05.000
Hello my friends and welcome back to another run.
"""


def test_parse_duration_seconds_mmss_and_hmmss() -> None:
    assert parse_duration_seconds("47:33") == pytest.approx(2853.0)
    assert parse_duration_seconds("35:04") == pytest.approx(2104.0)
    assert parse_duration_seconds("1:02:03") == pytest.approx(3723.0)


@pytest.mark.parametrize("bad", ["", "47", "aa:bb", "47:33:00:00", "-1:00"])
def test_parse_duration_seconds_fails_loud(bad: str) -> None:
    with pytest.raises(ValueError):
        parse_duration_seconds(bad)


def test_count_raw_cues_counts_pre_fold_cues_with_text() -> None:
    # 3 条滚动 cue (词级重叠), header 无时间戳不计.
    assert count_raw_cues(VTT_ROLLING) == 3


def test_count_raw_cues_ignores_timestamp_only_blocks() -> None:
    vtt = (
        "WEBVTT\n\n"
        "00:00:00.000 --> 00:00:02.000\n\n"
        "00:00:02.000 --> 00:00:04.000\nfirst line\n\n"
        "00:00:04.000 --> 00:00:06.000\nsecond line\n"
    )
    assert count_raw_cues(vtt) == 2


def test_band_green_for_historical_runs_and_demon() -> None:
    # 历史 12 例区间 395-555 句 / 31-38 分钟 / 折比 0.233-0.330 + demon 726 句 / 47:33 / 0.330
    cases = (
        (395, "35:04", 1592), (442, "31:30", 1428), (411, "33:23", 1450),
        (501, "35:16", 1618), (443, "35:10", 1570), (412, "34:54", 1744),
        (555, "37:27", 1780), (441, "38:03", 1892), (415, "33:26", 1504),
        (415, "35:55", 1702), (451, "35:06", 1516),
        (726, "47:33", 2198),  # demon/ultimate #86
    )
    for n, dur, raw in cases:
        assert sentence_band_errors(n, dur, "auto", raw) == [], f"{n}/{dur}/{raw} should be green"


def test_band_fails_too_sparse() -> None:
    # #92 指定样例: 5 句每分 → 过于稀疏
    errs = sentence_band_errors(200, "40:00", "auto", 1000)
    assert errs and any("密度" in e for e in errs), errs


def test_band_fails_too_dense() -> None:
    # #92 指定样例: 30 句每分 → 折叠没生效
    errs = sentence_band_errors(1050, "35:00", "auto", 2400)
    assert errs and any("密度" in e for e in errs), errs


def test_band_fails_fold_ratio_low() -> None:
    # #92 指定样例: 折比 0.05 → 折叠几乎没合并 (密度 11.4 句/分 合法, 隔离折比一条)
    errs = sentence_band_errors(400, "35:00", "auto", 8000)
    assert errs and any("折叠" in e for e in errs), errs
    assert not any("密度" in e for e in errs), errs


def test_band_fails_fold_ratio_high() -> None:
    # #92 指定样例: 折比 0.80 → 折叠过度
    errs = sentence_band_errors(400, "35:00", "auto", 500)
    assert errs and any("折叠" in e for e in errs), errs


def test_band_skips_fold_ratio_for_manual_subs() -> None:
    # manual 字幕 fold 是 no-op (折比恒 1.0), 只查密度
    assert sentence_band_errors(500, "40:00", "manual", 500) == []
    errs = sentence_band_errors(50, "40:00", "manual", 50)
    assert errs and any("密度" in e for e in errs), errs


@pytest.mark.parametrize("subs", ["", " AUTO ", "human", None])
def test_band_fails_loud_on_bad_subs_source(subs) -> None:
    errs = sentence_band_errors(726, "47:33", subs, 2198)
    assert errs and any("subs_source" in e for e in errs), errs


def test_band_fails_loud_on_bad_duration() -> None:
    errs = sentence_band_errors(726, "47 minutes", "auto", 2198)
    assert errs and any("duration" in e for e in errs), errs


def test_band_fails_loud_on_empty_sentences() -> None:
    errs = sentence_band_errors(0, "47:33", "auto", 2198)
    assert errs and any("不得为空" in e for e in errs), errs


def test_band_fails_loud_on_zero_raw_cues() -> None:
    errs = sentence_band_errors(726, "47:33", "auto", 0)
    assert errs and any("cue" in e for e in errs), errs


def test_band_constants_match_documented_range() -> None:
    assert (DENSITY_MIN, DENSITY_MAX) == (8.0, 22.0)
    assert (FOLD_RATIO_MIN, FOLD_RATIO_MAX) == (0.15, 0.50)


def _write_inputs(workdir: Path, duration: str, subs_source: str, vtt: str) -> None:
    (workdir / "inputs").mkdir(parents=True, exist_ok=True)
    (workdir / "inputs" / "meta.json").write_text(json.dumps({"duration": duration}), encoding="utf-8")
    (workdir / "inputs" / "manifest.json").write_text(json.dumps({"subs_source": subs_source}), encoding="utf-8")
    (workdir / "inputs" / "source.vtt").write_text(vtt, encoding="utf-8")


def test_band_errors_for_workdir_reads_inputs(tmp_path: Path) -> None:
    workdir = tmp_path / "demon" / "ultimate"
    _write_inputs(workdir, "47:33", "auto", VTT_ROLLING)
    # 3 cue 折成 1 句 / 47:33 → 密度过低, 证明真的读到了 inputs
    errs = band_errors_for_workdir(workdir, 1)
    assert any("密度" in e for e in errs), errs


def test_band_errors_for_workdir_requires_inputs(tmp_path: Path) -> None:
    errs = band_errors_for_workdir(tmp_path / "nope", 726)
    assert errs, "缺 inputs 须 fail loud (不回落)"


def test_band_errors_for_workdir_green_on_demon_run() -> None:
    """真件回归: demon/ultimate 726 句 / 47:33 / auto, 旧绝对带误杀的那一例."""
    workdir = Path("G:/brotato-work/demon/ultimate")
    src = workdir / "inputs" / "source.vtt"
    if not src.exists():
        raise AssertionError("G work demon/ultimate inputs missing (先取证后跑前置, 缺件即 fail)")
    assert band_errors_for_workdir(workdir, 726) == []
