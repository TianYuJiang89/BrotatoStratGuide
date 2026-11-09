"""#96 prompt 消歧: 短引必须写成 原话“...”，裸引号即缺件.

Seams (deterministic, no LLM, no network):
- `prompt_contract.SHORT_QUOTE_MARKER` 单一来源
- 5 个短引类 builder 各含一次 (03 priority / 05 evidence / 05 ranking / 06 wording / 07 wording)
- 03 evidence / 03 grouping-ranking (#82/#83 专用句) 不重复注入; 08 码内明确不卡短引, 不挂
"""
from __future__ import annotations

import importlib.util
from pathlib import Path

import pytest

from prompt_fixtures import FEWSHOT, GROUPING, PHASES, RATINGS, SENTENCES, SYNTHESIS, WEAPONS

REPO = Path(__file__).resolve().parent.parent


def _load(name: str, rel: str):
    spec = importlib.util.spec_from_file_location(name, str(REPO / rel))
    assert spec is not None and spec.loader is not None
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


PC = _load("prompt_contract96", "scripts/prompt_contract.py")
S0307 = _load("s0307d", "scripts/step0307_loop.py")
S05 = _load("s05d", "scripts/step05_loop.py")
S06 = _load("s06d", "scripts/step06_loop.py")
S07 = _load("s07d", "scripts/step07_loop.py")
S08 = _load("s08d", "scripts/step08_loop.py")


def _count(prompt: str) -> int:
    return prompt.count(PC.SHORT_QUOTE_MARKER.strip())


def test_contract_constant_is_single_source() -> None:
    """契约句单一来源且语义到位（原话 前缀 / 裸引号即 fail）。"""
    txt = PC.SHORT_QUOTE_MARKER
    assert "原话" in txt and "裸 “...”" in txt and "fail" in txt


@pytest.mark.parametrize(
    "build",
    [
        pytest.param(lambda: S0307.build_priority_ranking_prompt(
            SENTENCES, GROUPING, RATINGS, WEAPONS, PHASES, FEWSHOT), id="0307-priority-ranking"),
        pytest.param(lambda: S05.build_evidence_prompt("Spear", SENTENCES, FEWSHOT), id="05-evidence"),
        pytest.param(lambda: S05.build_ranking_prompt(SENTENCES, WEAPONS["t1"], FEWSHOT), id="05-ranking"),
        pytest.param(lambda: S06.build_wording_prompt(
            {"phase": "p", "waves": "", "quotes": [SENTENCES[1]["text"]]}, SENTENCES, FEWSHOT),
            id="06-wording"),
        pytest.param(lambda: S07.build_wording_prompt(
            {"name": "Max HP", "kind": "upgrade", "quotes": [SENTENCES[1]["text"]]},
            SENTENCES, FEWSHOT, "B / must_take", SYNTHESIS, PHASES), id="07-wording"),
    ],
)
def test_short_quote_builders_carry_marker_contract(build) -> None:
    """短引类 builder 必含契约句恰好一次。"""
    assert _count(build()) == 1


def test_evidence_and_grouping_keep_their_own_marker_line() -> None:
    """03 evidence / 03 grouping-ranking 已有 #82/#83 专用句, 不重复注入。"""
    assert _count(S0307.build_evidence_prompt("Small Magazine", SENTENCES, FEWSHOT)) == 0
    assert _count(S0307.build_grouping_ranking_prompt(
        SENTENCES,
        [{"name_en": "Small Magazine", "group": "must_take",
          "quotes": [SENTENCES[1]["text"]], "analysis": "a"}],
        FEWSHOT)) == 0


def test_08_wording_not_attached() -> None:
    """08 码内明确不卡短引（意图进 fewshot），故不挂。"""
    assert _count(S08.build_wording_prompt(
        {"title": "t", "seeds": [SENTENCES[1]["text"]]}, SENTENCES, FEWSHOT)) == 0
