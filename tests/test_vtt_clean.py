"""#94 01-sentences 清洗: 自动字幕 `&gt;&gt;` 讲话人标记 + HTML 实体归一.

Seams (deterministic-first, no LLM, no network):
- `build_mentions.parse_vtt` 文本口径: 实体解码 + 讲话人标记剥离 (句首/句内)
- `run_segment1.parse_vtt_timed` 与 `parse_vtt` **同口径**(同输入同文本, 只多 start/end)
- 保留: `<c>` / `<00:xx>` 词级标签剥离、cap 500、折叠前后时间戳映射不变

红灯来源 (#87 fisherman): raw VTT `&gt;&gt; And` 未解码未剥 → sentence record 带
`&gt;&gt; ` 前缀 → 下游 agent 逐字引用必撞「编 quote 即 fail」。
"""
from __future__ import annotations

import importlib.util
import textwrap
from pathlib import Path

REPO = Path(__file__).resolve().parent.parent


def _load(name: str, rel: str):
    spec = importlib.util.spec_from_file_location(name, str(REPO / rel))
    assert spec is not None and spec.loader is not None
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


BM = _load("bm_clean", "scripts/build_mentions.py")
RS1 = _load("rs1_clean", "scripts/run_segment1.py")


def _vtt(body: str) -> str:
    return "WEBVTT\n\n" + textwrap.dedent(body).strip() + "\n"


# ---------- parse_vtt (交叉表口径) ----------


def test_parse_vtt_strips_leading_speaker_marker_entity() -> None:
    """句首 `&gt;&gt;` 剥掉 (fisherman id=435 原样)。"""
    vtt = _vtt(
        """
        00:36:33.400 --> 00:36:35.230
        &gt;&gt; And yeah, I'll take the stone skin.
        """
    )
    assert BM.parse_vtt(vtt) == ["And yeah, I'll take the stone skin."]


def test_parse_vtt_strips_inline_speaker_markers() -> None:
    """句内多个标记也剥 (`&gt;&gt; [laughter] &gt;&gt; Oh, well.` → `[laughter] Oh, well.`)。"""
    vtt = _vtt(
        """
        00:30:03.440 --> 00:30:09.790
        &gt;&gt; [laughter]
        &gt;&gt; Oh, well.
        """
    )
    assert BM.parse_vtt(vtt) == ["[laughter] Oh, well."]


def test_parse_vtt_decodes_html_entities() -> None:
    """`&amp;` / `&#39;` 等实体解码 (只解一次, 不二次解)。"""
    vtt = _vtt(
        """
        00:00:01.000 --> 00:00:02.000
        Armor &amp; dodge, don&#39;t skip it.
        """
    )
    assert BM.parse_vtt(vtt) == ["Armor & dodge, don't skip it."]


def test_parse_vtt_keeps_karaoke_tag_stripping() -> None:
    """`<c>` / `<00:xx>` 词级标签仍剥 (旧口径不回归)。"""
    vtt = _vtt(
        """
        00:00:01.000 --> 00:00:02.000
        take<00:00:01.200><c> the</c><00:00:01.400><c> spear</c>
        """
    )
    assert BM.parse_vtt(vtt) == ["take the spear"]


# ---------- parse_vtt_timed (01 口径) ----------


def test_parse_vtt_timed_strips_marker_and_keeps_timestamps() -> None:
    """带时间戳同口径: 文本剥标记, start/end/t 不受影响。"""
    vtt = _vtt(
        """
        00:36:33.400 --> 00:36:35.230
        &gt;&gt; And yeah, I'll take the stone skin.
        """
    )
    out = RS1.parse_vtt_timed(vtt, fold=False)
    assert [c["text"] for c in out] == ["And yeah, I'll take the stone skin."]
    assert out[0]["start"] == "00:36:33.400"
    assert out[0]["end"] == "00:36:35.230"
    assert out[0]["start_s"] == 2193.4


def test_parse_vtt_timed_matches_parse_vtt_text() -> None:
    """两处 parser 文本口径须一致 (禁规则两处漂移)。"""
    vtt = _vtt(
        """
        00:00:01.000 --> 00:00:02.000
        &gt;&gt; Armor &amp; dodge

        00:00:03.000 --> 00:00:04.000
        take<00:00:03.200><c> the</c> spear
        """
    )
    assert [c["text"] for c in RS1.parse_vtt_timed(vtt, fold=False)] == BM.parse_vtt(vtt)


def test_clean_cue_text_is_single_source() -> None:
    """清洗函数单一来源: 两处 parser 都调 build_mentions.clean_cue_text。"""
    assert hasattr(BM, "clean_cue_text")
    assert BM.clean_cue_text("&gt;&gt; And yeah.") == "And yeah."
    assert BM.clean_cue_text("take<00:00:01.200><c> the</c> spear") == "take the spear"
