"""#60 per-attribute loop: frozen fewshot + for-loop x39.

Seams (deterministic-first, no LLM in tests):
- prompt building: fewshot + full sentences + one attr, no verb/over/count logic in code
- agent output validation: shape only (39全量/quotes逐字/quote_details平行t合法/summary<=120禁泄漏含短引/count==0<=>-)
- count backfill by code (agent must not fill count)
- old anchor fields retired (anchors/confidence/kind/inferred/reason must be absent)
- fail loud on missing/fabricated quote (no fallback, no blank补)
"""
from __future__ import annotations

import importlib.util
import json
from pathlib import Path

REPO = Path(__file__).resolve().parent.parent


def _load(name: str, rel: str):
    spec = importlib.util.spec_from_file_location(name, str(REPO / rel))
    assert spec is not None and spec.loader is not None
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


def _sentences():
    return [
        {"id": 1, "text": "You buy ranged damage at triple the normal rate, uh, which is of course incredibly strong.",
         "start": "00:00:16.320", "end": "00:00:19.349", "start_s": 16.32, "end_s": 19.349, "t": 16},
        {"id": 2, "text": "I'm going to take three range damage over 15 attack speed.",
         "start": "00:24:36.720", "end": "00:24:43.430", "start_s": 1476.72, "end_s": 1483.43, "t": 1476},
        {"id": 3, "text": "The way this character works is you gain extra ranged damage, but all of your ranged damage turns to engineering halfway through the wave.",
         "start": "00:00:16.320", "end": "00:00:23.830", "start_s": 16.32, "end_s": 23.83, "t": 16},
    ]


def test_step04_loop_module_exists():
    p = REPO / "scripts" / "step04_loop.py"
    assert p.exists(), "scripts/step04_loop.py must exist (#60 for-loop调度)"


def test_prompt_build_contains_fewshot_sentences_attr_only():
    m = _load("step04_loop", "scripts/step04_loop.py")
    assert hasattr(m, "build_attribute_prompt")
    fewshot = (REPO / "prompts" / "step04-ratings-fewshot.md").read_text(encoding="utf-8")
    prompt = m.build_attribute_prompt("Ranged Damage", _sentences(), fewshot)
    # 必须含基准fewshot + 全量整句 + 这一个属性名
    assert "Ranged Damage" in prompt
    assert "You buy ranged damage at triple" in prompt
    # 一次只塞一个属性：其它属性名不应作为任务目标出现（允许fewshot内出现，但任务行只提一个）
    assert "TASK_ATTR" in prompt or "这一个属性" in prompt or "属性名" in prompt
    # 语义零进代码：prompt构建不得含动词闭集/窗30/over/负面词表逻辑
    low = prompt.lower()
    # 允许fewshot原文含over等，但构建器自身不得注入锚规则（检查构建器源码）
    import inspect
    src = inspect.getsource(m.build_attribute_prompt)
    for banned in ("pick up", "同句窗", "over 前", "负面词表", "上半", "下半"):
        assert banned not in src, f"build_attribute_prompt must not encode anchor rules ({banned})"


def test_validate_shape_ok_and_fail_loud():
    m = _load("step04_loop", "scripts/step04_loop.py")
    assert hasattr(m, "validate_attribute_output")
    sents = _sentences()
    good = {
        "term_en": "Ranged Damage",
        "rating": "S",
        "quotes": ["You buy ranged damage at triple the normal rate, uh, which is of course incredibly strong."],
        "analysis": "来源=捡（三倍率）→前半波爆发机制→整局入口故S。不计次数。",
        "summary": "无脑堆，前半波秒怪全靠它。",
    }
    # count=len(quotes)无扫描，agent不填：validate不应要求count
    assert "count" not in good
    m.validate_attribute_output(good, "Ranged Damage", sents)
    # 编quote即fail loud
    import pytest
    bad = dict(good)
    bad["quotes"] = ["我编的一句根本不在字幕里"]
    with pytest.raises(SystemExit):
        m.validate_attribute_output(bad, "Ranged Damage", sents)
    # 缺件即fail loud（缺summary）
    bad2 = dict(good)
    del bad2["summary"]
    with pytest.raises(SystemExit):
        m.validate_attribute_output(bad2, "Ranged Damage", sents)
    # 自洽：-必须空quotes（正例）
    zero = {
        "term_en": "Bounces",
        "rating": "-",
        "quotes": [],
        "analysis": "作者未提及。",
        "summary": "作者未提及",
    }
    m.validate_attribute_output(zero, "Bounces", sents)
    # 自洽：-却给quotes即fail；S-D却空quotes即fail
    bad3 = dict(zero)
    bad3["quotes"] = ["You buy ranged damage at triple the normal rate, uh, which is of course incredibly strong."]
    with pytest.raises(SystemExit):
        m.validate_attribute_output(bad3, "Bounces", sents)
    bad4 = dict(good)
    bad4["quotes"] = []
    with pytest.raises(SystemExit):
        m.validate_attribute_output(bad4, "Ranged Damage", sents)


def test_validate_rejects_old_anchor_fields_and_count_leak():
    m = _load("step04_loop", "scripts/step04_loop.py")
    import pytest
    sents = _sentences()
    base = {
        "term_en": "Ranged Damage",
        "rating": "S",
        "quotes": ["You buy ranged damage at triple the normal rate, uh, which is of course incredibly strong."],
        "analysis": "来源=捡→机制→S。",
        "summary": "无脑堆。",
    }
    # 旧四件退役：含anchors即fail
    for old in ("anchors", "confidence", "kind", "inferred", "reason"):
        bad = dict(base)
        bad[old] = [] if old == "anchors" else "x"
        with pytest.raises(SystemExit):
            m.validate_attribute_output(bad, "Ranged Damage", sents)
    # agent填count即fail（count只活代码）
    bad = dict(base)
    bad["count"] = 5
    with pytest.raises(SystemExit):
        m.validate_attribute_output(bad, "Ranged Damage", sents)
    # summary超120即fail
    bad = dict(base)
    bad["summary"] = "x" * 121
    with pytest.raises(SystemExit):
        m.validate_attribute_output(bad, "Ranged Damage", sents)
    # 计数泄漏即fail
    bad = dict(base)
    bad["summary"] = "字幕出现5次所以强"
    with pytest.raises(SystemExit):
        m.validate_attribute_output(bad, "Ranged Damage", sents)
    # 不查动词/over/S数量帽：11个S也不fail（形状只卡存在性）
    # （本测试只验validate不查S数量：多S由人看抽检，不由代码卡）


def test_backfill_builds_final_entry_with_quote_details():
    m = _load("step04_loop", "scripts/step04_loop.py")
    assert hasattr(m, "build_final_entry")
    sents = _sentences()
    agent = {
        "term_en": "Ranged Damage",
        "rating": "S",
        "quotes": ["You buy ranged damage at triple the normal rate, uh, which is of course incredibly strong."],
        "analysis": "来源=捡→机制→S。",
        "summary": "无脑堆。",
    }
    entry = m.build_final_entry("Ranged Damage", "远程伤害", "primary", agent, sents)
    assert entry["term_en"] == "Ranged Damage"
    assert entry["count"] == 1
    assert entry["rating"] == "S"
    assert entry["quotes"] == agent["quotes"]
    assert len(entry["quote_details"]) == 1
    assert entry["quote_details"][0]["quote"] == agent["quotes"][0]
    assert entry["quote_details"][0]["t"] == 16
    # 旧字段必须 absent
    for old in ("anchors", "confidence", "kind", "inferred", "reason"):
        assert old not in entry, f"retired field {old} must be absent"


def test_run_segment1_step04_uses_loop_not_anchors():
    import inspect
    m = _load("run_segment1", "scripts/run_segment1.py")
    assert hasattr(m, "step04")
    src = inspect.getsource(m.step04)
    # 新step04必须是loop调度：须引用step04_loop或per-attr/for-loop语义
    assert ("step04_loop" in src) or ("per_attr" in src) or ("for" in src and "term" in src.lower())
    # 锚规则全删：不得含闭集拿取/窗30/over赢家/负面词表/count上下半
    for banned in ("_ANCHOR_VERBS", "同句共现", "over 前", "neg_sent", "b_set", "上半"):
        assert banned not in src, f"step04 must retire anchor rules ({banned})"


def test_check_segment1_04_shape_only_no_verb_over_cap():
    import inspect
    m = _load("check_segment1", "scripts/check_segment1.py")
    full = inspect.getsource(m)
    # 只查04节（05-weapons仍用锚，属正常）：截取04节区间
    s = full.find("# --- 04-attributes")
    e = full.find("# --- 05-weapons", s)
    src = full[s:e] if s > 0 and e > s else full
    # 新check只卡形状：须查39/逐字/平行/summary/零命中；不查动词/over/数量帽
    assert "39" in src
    assert "quote_details" in src
    assert "summary" in src
    for banned in ("拿取动词", "赢过谁", "S/A 数量", "数量帽", "同句窗", "verified 拿取", "二选一赢家", "over 前"):
        assert banned not in src, f"check_04 must not check verbs/over/caps ({banned})"
    # 旧字段不得再被要求
    # （允许提及retired以便报错，但不得要求它们存在）
    assert "analysis" in src, "check_04 must require analysis (审计全过程)"


def test_context_ratings_section_points_to_fewshot():
    txt = (REPO / "CONTEXT.md").read_text(encoding="utf-8")
    assert "step04-ratings-fewshot" in txt, "CONTEXT ratings段须以fewshot文件为准 (#47/#50作废)"
    for banned in ("同句窗 30", "否定前 20", "over 前 60"):
        assert banned not in txt, f"CONTEXT must retire old anchor口径 ({banned})"


def test_audit_04_shows_analysis_not_anchors():
    html = (REPO / "templates" / "audit.html").read_text(encoding="utf-8")
    assert "audit-04-attributes" in html
    assert "analysis" in html, "audit 04节须展示analysis全过程"
    # 旧锚展示退役：不得再以锚为核心（允许注释提及退役，但不得渲染anchors badge为核心）
    # 放宽：只要含analysis即过，anchors若仍出现须为退役说明而非核心渲染
    assert "summary" in html.lower() or "Summary" in html
