"""prompt builder 测试共用的最小夹具 (禁各测试各抄一份 SENTENCES/GROUPING/…)."""

from __future__ import annotations

FEWSHOT = "# TASK\nFROZEN 测试用 fewshot 占位。\n"

SENTENCES = [
    {"id": 1, "text": "And I'm going to lock the small magazine.", "start": "00:00:01.000",
     "end": "00:00:02.000", "start_s": 1.0, "end_s": 2.0, "t": 1},
    {"id": 2, "text": "Small magazine is is very good.", "start": "00:00:03.000",
     "end": "00:00:04.000", "start_s": 3.0, "end_s": 4.0, "t": 3},
]

GROUPING = [{"name_en": "Small Magazine", "count": 1, "group": "must_take",
             "quotes": [SENTENCES[1]["text"]], "analysis": "a", "note": "n",
             "quote_details": []}]

RATINGS = [{"term_en": "Max HP", "term_zh": "最大生命", "type": "primary", "count": 1,
            "rating": "B", "quotes": [SENTENCES[1]["text"]], "analysis": "a",
            "summary": "s", "quote_details": []}]

WEAPONS = {"t1": [{"name_en": "Spear", "count": 1, "tier": "t1",
                   "quotes": [SENTENCES[1]["text"]], "analysis": "a", "note": "n",
                   "copies": "未提及", "copies_quote": "", "quote_details": []}], "t2": []}

PHASES = [{"phase": "p", "waves": "", "goal": "g", "focus": "f", "pivot": "v",
           "quotes": [SENTENCES[1]["text"]], "quote_details": []}]

SYNTHESIS = {"upgrade_view": "u", "shop_view": "s", "channel_rule": "c",
             "rhythm": "r", "exceptions": "e"}
