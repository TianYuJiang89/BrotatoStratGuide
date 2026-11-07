#!/usr/bin/env python3
"""01-sentences 折叠后句数闸 (#92): 与片长无关的密度带 + 折叠有效比.

退役口径: 绝对带 `300 <= 折叠后句数 <= 600` (#43 拿 31-38 分钟片校准, #90 放宽到 ±150
仍按绝对值)。片长一长就必红, 与折叠好坏无关: demon/ultimate (#86) 47:33 → 折叠后
726 句被误杀, 而折叠比 0.330 / 密度 15.3 句每分与历史全绿 12 例同档
(0.233-0.330 / 11.3-15.3)。

现口径 (两条都过才绿, 任一不满足即 fail; 不回落、不猜):
- 密度: 折叠后句数 ÷ 视频分钟数 ∈ [8, 22]
  折叠坏掉 (几乎不合并) 会冲到 30+; 过度折叠/断句崩会掉到个位数。
- 折叠有效比: 折叠后句数 ÷ 原始 cue 数 ∈ [0.15, 0.50], 仅 `subs_source=auto` 生效
  (manual 字幕没有滚动复读, fold 是 no-op, 比恒为 1.0, 按 manifest 跳过)。

不做的事 (沿 #92): 不改 fold、不改断句、不动 #90 的相邻复读口径; 不动 sentences.json。

用法:
  from sentence_band import band_errors_for_workdir, sentence_band_errors
  errs = band_errors_for_workdir(workdir, len(sentences))   # 读 inputs/ 三件
  errs = sentence_band_errors(n, duration, subs_source, raw_cues)  # 纯口径
"""

from __future__ import annotations

import json
import re
from pathlib import Path

DENSITY_MIN = 8.0    # 句每分下限 (历史全绿 11.3-15.3)
DENSITY_MAX = 22.0   # 句每分上限 (折叠崩会到 30+)
FOLD_RATIO_MIN = 0.15  # 折叠后/原始 cue 下限 (历史全绿 0.233-0.330)
FOLD_RATIO_MAX = 0.50  # 上限 (折叠过度即越界)
VALID_SUBS_SOURCE = ("auto", "manual")

_DUR_RE = re.compile(r"^(?:(\d+):)?(\d{1,2}):(\d{2})$")


def parse_duration_seconds(duration: str) -> float:
    """`mm:ss` / `h:mm:ss` -> 秒。解析不出即 ValueError (不回落)."""
    s = str(duration or "").strip()
    m = _DUR_RE.match(s)
    if not m:
        raise ValueError(f"duration 不可解析 (须 mm:ss 或 h:mm:ss): {duration!r}")
    hours, minutes, seconds = m.group(1), int(m.group(2)), int(m.group(3))
    if minutes >= 60 and hours is not None:
        raise ValueError(f"duration 分钟位越界: {duration!r}")
    if seconds >= 60:
        raise ValueError(f"duration 秒位越界: {duration!r}")
    return float((int(hours) * 3600 if hours else 0) + minutes * 60 + seconds)


def count_raw_cues(vtt_text: str) -> int:
    """折叠前的原始 cue 数 (带时间戳且有文本的块, 与 01 解析同口径).

    复用 run_segment1.parse_vtt_timed(fold=False), 避免断句规则两处漂移。
    """
    from run_segment1 import parse_vtt_timed

    cues = parse_vtt_timed(vtt_text, fold=False)
    return sum(1 for c in cues if isinstance(c, dict) and c.get("start") is not None)


def sentence_band_errors(n_sentences: int, duration: str, subs_source,
                         raw_cues: int) -> list[str]:
    """纯口径: 返回 errors (空表=绿)。缺件/不可解析一律 fail loud。"""
    errors: list[str] = []
    subs = subs_source if isinstance(subs_source, str) else ""
    if subs not in VALID_SUBS_SOURCE:
        errors.append(f"subs_source 须为 {'/'.join(VALID_SUBS_SOURCE)} (读 manifest), got {subs_source!r}")
    if not isinstance(n_sentences, int) or n_sentences <= 0:
        errors.append(f"折叠后句数不得为空 (got {n_sentences!r})")
        return errors
    try:
        dur_s = parse_duration_seconds(duration)
    except ValueError as e:
        errors.append(str(e))
        return errors
    if dur_s <= 0:
        errors.append(f"duration 须为正数: {duration!r}")
        return errors
    minutes = dur_s / 60.0
    density = n_sentences / minutes
    if not (DENSITY_MIN <= density <= DENSITY_MAX):
        errors.append(
            f"句密度越界: {n_sentences} 句 / {minutes:.1f} 分 = {density:.1f} 句每分 "
            f"(须 {DENSITY_MIN:g}-{DENSITY_MAX:g}; 过高=折叠没生效, 过低=过度折叠)")
    if subs == "auto":
        if not isinstance(raw_cues, int) or raw_cues <= 0:
            errors.append(f"原始 cue 数不得为空 (折叠有效比无法校验, got {raw_cues!r})")
        else:
            ratio = n_sentences / raw_cues
            if not (FOLD_RATIO_MIN <= ratio <= FOLD_RATIO_MAX):
                errors.append(
                    f"折叠有效比越界: {n_sentences}/{raw_cues} = {ratio:.3f} "
                    f"(须 {FOLD_RATIO_MIN:g}-{FOLD_RATIO_MAX:g}; 仅 auto 字幕校验)")
    return errors


def band_errors_for_workdir(workdir: Path, n_sentences: int) -> list[str]:
    """读 `<workdir>/inputs/{meta,manifest}.json` + `source.vtt` 后走纯口径。"""
    workdir = Path(workdir)
    meta_p = workdir / "inputs" / "meta.json"
    man_p = workdir / "inputs" / "manifest.json"
    vtt_p = workdir / "inputs" / "source.vtt"
    missing = [str(p) for p in (meta_p, man_p, vtt_p) if not p.exists()]
    if missing:
        return [f"01-sentences 句数闸缺件 (缺件即 fail, 不回落): {', '.join(missing)}"]
    try:
        meta = json.loads(meta_p.read_text(encoding="utf-8"))
        manifest = json.loads(man_p.read_text(encoding="utf-8"))
        vtt = vtt_p.read_text(encoding="utf-8")
    except Exception as e:  # 读失败即 fail loud
        return [f"01-sentences 句数闸读件失败 (不回落): {e!r}"]
    return sentence_band_errors(
        n_sentences,
        (meta or {}).get("duration", ""),
        (manifest or {}).get("subs_source", ""),
        count_raw_cues(vtt),
    )
