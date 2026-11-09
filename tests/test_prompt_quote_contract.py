"""#95 prompt 消歧：整句 quotes 契约句须挂在每个逐字校验的 builder 上.

Seams (deterministic, no LLM, no network):
- `scripts/prompt_contract.QUOTE_WHOLE_SENTENCE` 单一来源（禁各 loop 各写一份）
- 9 个输出整句 quotes 的 builder 必含该句**恰好一次**
- 短引类 builder（06/08 wording）不挂（不回归）

红灯来源 (#87 fisherman): discovery agent 把 `And ` 省掉、其余逐字 → 「编 quote」闸。
"""
from __future__ import annotations

import importlib.util
from pathlib import Path

import pytest

from prompt_fixtures import FEWSHOT, GROUPING, PHASES, RATINGS, SENTENCES, WEAPONS

REPO = Path(__file__).resolve().parent.parent


def _load(name: str, rel: str):
    spec = importlib.util.spec_from_file_location(name, str(REPO / rel))
    assert spec is not None and spec.loader is not None
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


PC = _load("prompt_contract", "scripts/prompt_contract.py")
S0307 = _load("s0307c", "scripts/step0307_loop.py")
S04 = _load("s04c", "scripts/step04_loop.py")
S05 = _load("s05c", "scripts/step05_loop.py")
S06 = _load("s06c", "scripts/step06_loop.py")
S07 = _load("s07c", "scripts/step07_loop.py")
S08 = _load("s08c", "scripts/step08_loop.py")


def _count(prompt: str) -> int:
    return prompt.count(PC.QUOTE_WHOLE_SENTENCE.strip())


def test_contract_constant_is_single_source() -> None:
    """契约句单一来源且语义到位（整句 / 开头词 / 截断即 fail）。"""
    txt = PC.QUOTE_WHOLE_SENTENCE
    assert "整句" in txt and "开头词" in txt and "截断即 fail" in txt
    assert "And/So/Now/Yeah" in txt


@pytest.mark.parametrize(
    "build",
    [
        pytest.param(lambda: S0307.build_discovery_prompt(SENTENCES, ["Small Magazine"], 0, 1, FEWSHOT),
                     id="0307-discovery"),
        pytest.param(lambda: S0307.build_evidence_prompt("Small Magazine", SENTENCES, FEWSHOT),
                     id="0307-evidence"),
        pytest.param(lambda: S0307.build_priority_ranking_prompt(SENTENCES, GROUPING, RATINGS, WEAPONS, PHASES, FEWSHOT),
                     id="0307-priority-ranking"),
        pytest.param(lambda: S04.build_attribute_prompt("Max HP", SENTENCES, FEWSHOT),
                     id="04-attribute"),
        pytest.param(lambda: S05.build_discovery_prompt(SENTENCES, ["Spear"], 0, 1, FEWSHOT),
                     id="05-discovery"),
        pytest.param(lambda: S05.build_evidence_prompt("Spear", SENTENCES, FEWSHOT),
                     id="05-evidence"),
        pytest.param(lambda: S06.build_segmentation_prompt(SENTENCES, FEWSHOT),
                     id="06-segmentation"),
        pytest.param(lambda: S07.build_selection_prompt(SENTENCES, GROUPING, RATINGS, WEAPONS, PHASES, FEWSHOT),
                     id="07-selection"),
        pytest.param(lambda: S08.build_discovery_prompt(SENTENCES, FEWSHOT),
                     id="08-discovery"),
    ],
)
def test_quote_builders_carry_whole_sentence_contract(build) -> None:
    """整句 quotes 类 builder 必含契约句恰好一次。"""
    assert _count(build()) == 1


def test_short_quote_builders_do_not_carry_it() -> None:
    """短引类 builder 不挂（拷的是 quotes 里的短引，不是整句）。"""
    assert _count(S06.build_wording_prompt({"phase": "p", "waves": "", "quotes": [SENTENCES[1]["text"]]},
                                           SENTENCES, FEWSHOT)) == 0
    assert _count(S08.build_wording_prompt({"title": "t", "seeds": [SENTENCES[1]["text"]]},
                                           SENTENCES, FEWSHOT)) == 0
