"""#61 three-agent loop: frozen fewshot + discovery/evidence/ranking.

Seams (deterministic-first, no LLM in tests):
- prompt building: fewshot + full sentences + vocab/one-name/N-evidence, no score/verified/fault/number logic in code
- discovery validation: candidates non-empty/quotes verbatim/name in vocab/dedup
- evidence validation: shape only (tier/quotes/analysis/note<=120, empty evidence fail)
- ranking validation: T1>=1/T1+T2==candidates/self-consistency/no number cap
- count backfill by code (agent must not fill count)
- old anchor fields retired (confidence/kind/inferred/anchors/score/reason must be absent)
- fail loud on missing/fabricated/hallucinated (no fallback, no blank补)
"""
from __future__ import annotations

import importlib.util
import json
from pathlib import Path

import pytest

REPO = Path(__file__).resolve().parent.parent


def _load(name: str, rel: str):
    spec = importlib.util.spec_from_file_location(name, str(REPO / rel))
    assert spec is not None and spec.loader is not None
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


def _sentences():
    return [
        {"id": 1, "text": "Obviously, we'll take a second minigun if a second minigun shows up.",
         "start": "00:02:42.080", "end": "00:02:47.509", "start_s": 162.08, "end_s": 167.509, "t": 162},
        {"id": 2, "text": "But we have four screwdrivers reducing its effect.",
         "start": "00:10:00.000", "end": "00:10:05.000", "start_s": 600.0, "end_s": 605.0, "t": 600},
        {"id": 3, "text": "That would be the ideal, but SMG does a a reasonable minigun impression.",
         "start": "00:02:45.599", "end": "00:02:53.589", "start_s": 165.599, "end_s": 173.589, "t": 165},
        {"id": 4, "text": "Obviously, we're taking the nuke launcher for the horde wave because it's much better than an upgraded minigun on a horde wave since it clears it's an explosion.",
         "start": "00:12:00.000", "end": "00:12:10.000", "start_s": 720.0, "end_s": 730.0, "t": 720},
    ]


def _vocab():
    return ["Minigun", "Screwdriver", "SMG", "Nuclear Launcher"]


def test_step05_loop_module_exists():
    p = REPO / "scripts" / "step05_loop.py"
    assert p.exists(), "scripts/step05_loop.py must exist (#61 three-agent调度)"


def test_fewshot_frozen_20shot_exists():
    p = REPO / "prompts" / "step05-weapons-fewshot.md"
    assert p.exists(), "prompts/step05-weapons-fewshot.md must exist (#61 frozen 20-shot)"
    txt = p.read_text(encoding="utf-8")
    assert "FROZEN" in txt
    # 20-shot 只读: 发现段 + T1/T2 + note 示范须齐
    for needle in ("TASK_DISCOVERY", "TASK_EVIDENCE", "TASK_RANKING",
                   "Slingshot", "second minigun", "four screwdrivers", "horde wave"):
        assert needle in txt, f"fewshot must contain {needle}"


def test_prompt_build_contains_fewshot_sentences_only():
    m = _load("step05_loop", "scripts/step05_loop.py")
    fewshot = (REPO / "prompts" / "step05-weapons-fewshot.md").read_text(encoding="utf-8")
    sents = _sentences()
    vocab = _vocab()
    disc = m.build_discovery_prompt(sents, vocab, fewshot)
    assert "Obviously, we'll take a second minigun" in disc
    assert "Minigun" in disc and "Screwdriver" in disc
    assert "TASK_DISCOVERY" in disc
    ev = m.build_evidence_prompt("Minigun", sents, fewshot)
    assert "TASK_WEAPON: Minigun" in ev
    assert "Obviously, we'll take a second minigun" in ev
    # 一次只判一把: 任务行只提这一把
    assert "TASK_EVIDENCE" in ev
    rank = m.build_ranking_prompt(sents, [
        {"name_en": "Minigun", "tier": "T1", "quotes": [sents[0]["text"]],
         "analysis": "a", "note": "n"}], fewshot)
    assert "TASK_RANKING" in rank
    # 语义零进代码: 构建器不得注入退役规则
    import inspect
    for fn_name in ("build_discovery_prompt", "build_evidence_prompt", "build_ranking_prompt"):
        src = inspect.getsource(getattr(m, fn_name))
        for banned in ("verified+5", "score=", "最大断层", "数字词", "拿取动词"):
            assert banned not in src, f"{fn_name} must not encode retired anchor rules ({banned})"


def test_validate_discovery_ok_and_fail_loud():
    m = _load("step05_loop", "scripts/step05_loop.py")
    sents = _sentences()
    vocab = _vocab()
    good = {"candidates": [
        {"name_en": "Minigun", "quotes": [sents[0]["text"]]},
        {"name_en": "Screwdriver", "quotes": [sents[1]["text"]]},
    ]}
    out = m.validate_discovery(good, sents, vocab)
    assert [c["name_en"] for c in out] == ["Minigun", "Screwdriver"]
    # 幻觉名即fail
    bad = {"candidates": [{"name_en": "幻觉枪", "quotes": [sents[0]["text"]]}]}
    with pytest.raises(SystemExit):
        m.validate_discovery(bad, sents, vocab)
    # 编quote即fail
    bad2 = {"candidates": [{"name_en": "Minigun", "quotes": ["我编的一句根本不在字幕里"]}]}
    with pytest.raises(SystemExit):
        m.validate_discovery(bad2, sents, vocab)
    # 空证据/空名单即fail
    with pytest.raises(SystemExit):
        m.validate_discovery({"candidates": []}, sents, vocab)
    with pytest.raises(SystemExit):
        m.validate_discovery({"candidates": [{"name_en": "Minigun", "quotes": []}]},
                              sents, vocab)
    # agent填count即fail
    bad3 = {"candidates": [], "count": 5}
    with pytest.raises(SystemExit):
        m.validate_discovery(bad3, sents, vocab)
    # 退役字段出现即fail
    for old in ("anchors", "confidence", "kind", "inferred", "score", "reason"):
        bad = {"candidates": [{"name_en": "Minigun", "quotes": [sents[0]["text"]]}],
               old: "x"}
        with pytest.raises(SystemExit):
            m.validate_discovery(bad, sents, vocab)


def test_validate_evidence_ok_and_fail_loud():
    m = _load("step05_loop", "scripts/step05_loop.py")
    sents = _sentences()
    good = {
        "name_en": "Minigun",
        "tier": "T1",
        "quotes": [sents[0]["text"]],
        "analysis": "来源=捡→整局扛把子→T1。",
        "note": "主力连发，原话“take a second minigun”。",
    }
    out = m.validate_evidence(good, "Minigun", sents)
    assert out["tier"] == "T1"
    # 空证据即fail (武器无 `-` 档)
    bad = dict(good)
    bad["quotes"] = []
    with pytest.raises(SystemExit):
        m.validate_evidence(bad, "Minigun", sents)
    # 名不对即fail
    bad = dict(good)
    bad["name_en"] = "SMG"
    with pytest.raises(SystemExit):
        m.validate_evidence(bad, "Minigun", sents)
    # 编quote即fail
    bad = dict(good)
    bad["quotes"] = ["编的一句"]
    with pytest.raises(SystemExit):
        m.validate_evidence(bad, "Minigun", sents)
    # note超120即fail
    bad = dict(good)
    bad["note"] = "x" * 121
    with pytest.raises(SystemExit):
        m.validate_evidence(bad, "Minigun", sents)
    # agent填count即fail
    bad = dict(good)
    bad["count"] = 5
    with pytest.raises(SystemExit):
        m.validate_evidence(bad, "Minigun", sents)
    for old in ("anchors", "confidence", "kind", "inferred", "score", "reason"):
        bad = dict(good)
        bad[old] = "x"
        with pytest.raises(SystemExit):
            m.validate_evidence(bad, "Minigun", sents)


def test_validate_ranking_ok_and_fail_loud():
    m = _load("step05_loop", "scripts/step05_loop.py")
    evs = [
        {"name_en": "Minigun", "tier": "T1", "quotes": ["q1"], "analysis": "a", "note": "n1"},
        {"name_en": "SMG", "tier": "T2", "quotes": ["q2"], "analysis": "a", "note": "n2"},
    ]
    cands = ["Minigun", "SMG"]
    good = {"t1": [{"name_en": "Minigun", "note": "主力，原话“q1”。"}],
            "t2": [{"name_en": "SMG", "note": "过渡，原话“q2”。"}]}
    out = m.validate_ranking(good, cands, evs)
    assert [x["name_en"] for x in out["t1"]] == ["Minigun"]
    # T1>=1 验收线
    bad = {"t1": [], "t2": [{"name_en": "Minigun", "note": "n"},
                            {"name_en": "SMG", "note": "n"}]}
    with pytest.raises(SystemExit):
        m.validate_ranking(bad, cands, evs)
    # T1+T2须==candidates (丢一把即fail)
    bad = {"t1": [{"name_en": "Minigun", "note": "n"}], "t2": []}
    with pytest.raises(SystemExit):
        m.validate_ranking(bad, cands, evs)
    # 幻觉名即fail
    bad = {"t1": [{"name_en": "幻觉枪", "note": "n"}],
           "t2": [{"name_en": "SMG", "note": "n"}]}
    with pytest.raises(SystemExit):
        m.validate_ranking(bad, cands, evs)
    # note空即fail (意图保, 码只查非空)
    bad = {"t1": [{"name_en": "Minigun", "note": ""}],
           "t2": [{"name_en": "SMG", "note": "n"}]}
    with pytest.raises(SystemExit):
        m.validate_ranking(bad, cands, evs)


def test_run_loop_with_fake_agents_cyborg_shape(tmp_path):
    """Fake三段: discovery 4把 → evidence各一把 → ranking切2/2, 自洽落盘."""
    m = _load("step05_loop", "scripts/step05_loop.py")
    sents = _sentences()
    workdir = tmp_path / "cyborg" / "ultimate"
    (workdir / "steps" / "05-weapons" / "per_weapon").mkdir(parents=True, exist_ok=True)
    (workdir / "outputs").mkdir(parents=True, exist_ok=True)

    quotes_by = {
        "Minigun": [sents[0]["text"]],
        "Screwdriver": [sents[1]["text"]],
        "SMG": [sents[2]["text"]],
        "Nuclear Launcher": [sents[3]["text"]],
    }

    def fake_agent(kind, name_en, prompt):
        assert "FROZEN" in prompt or "fewshot" in prompt.lower() or len(prompt) > 100
        if kind == "discovery":
            return {"candidates": [{"name_en": k, "quotes": v}
                                   for k, v in quotes_by.items()]}
        if kind == "evidence":
            assert name_en in quotes_by
            tier = "T1" if name_en in ("Minigun", "Screwdriver") else "T2"
            return {"name_en": name_en, "tier": tier,
                    "quotes": quotes_by[name_en],
                    "analysis": f"{name_en}来源→机制→{tier}。",
                    "note": f"{name_en}人话，原话短引。"}
        if kind == "ranking":
            return {"t1": [{"name_en": "Minigun", "note": "主力，原话短引。"},
                           {"name_en": "Screwdriver", "note": "体系，原话短引。"}],
                    "t2": [{"name_en": "SMG", "note": "过渡，原话短引。"},
                           {"name_en": "Nuclear Launcher", "note": "horde位，原话短引。"}]}
        raise AssertionError(f"unknown kind {kind}")

    # 用小词汇表 monkeypatch load_weapon_vocab
    orig_vocab = m.load_weapon_vocab
    m.load_weapon_vocab = lambda: sorted(quotes_by.keys())
    try:
        weapons = m.run_step05_loop(workdir, sents, agent_fn=fake_agent, force=True)
    finally:
        m.load_weapon_vocab = orig_vocab
    assert sorted([w["name_en"] for w in weapons["t1"]]) == ["Minigun", "Screwdriver"]
    assert sorted([w["name_en"] for w in weapons["t2"]]) == ["Nuclear Launcher", "SMG"]
    # count==len(quotes, 现场回填)
    for w in weapons["t1"] + weapons["t2"]:
        assert w["count"] == len(w["quotes"]) == 1
        assert len(w["quote_details"]) == 1
        assert w["quote_details"][0]["t"] in (162, 600, 165, 720)
        for old in ("anchors", "confidence", "kind", "inferred", "score", "reason"):
            assert old not in w, f"retired field {old} must be absent"
        assert w["analysis"] and w["note"]
    # candidates.json 自洽
    cands = json.loads((workdir / "steps" / "05-weapons" / "candidates.json")
                       .read_text(encoding="utf-8"))
    assert sorted(c["name_en"] for c in cands) == sorted(quotes_by.keys())
    for c in cands:
        assert c["count"] == len(c["quotes"])
    # per_weapon 落盘
    for n in quotes_by:
        import re
        safe = re.sub(r"[^A-Za-z0-9]+", "_", n).strip("_")
        assert (workdir / "steps" / "05-weapons" / "per_weapon" / f"{safe}.json").exists()


def test_run_segment1_step05_uses_loop_not_anchors():
    import inspect
    m = _load("run_segment1", "scripts/run_segment1.py")
    assert hasattr(m, "step05")
    src = inspect.getsource(m.step05)
    assert ("step05_loop" in src) or ("per_weapon" in src) or ("discovery" in src.lower())
    # 功能性退役 (读 slice/verbs、加分、断层切分、数字词表、锚动词): 文档提及退役不算，代码出现才算
    for banned in ('"registry-slice', "verified+5", "_NUM_TOKENS",
                   '"02-verbs', '"registry_slice', "拿取动词"):
        assert banned not in src, f"step05 must retire anchor/slice rules ({banned})"
    # 断层/数字词若出现必须是退役说明 (含 退役/已删/禁)，不许是实现逻辑
    for line in src.splitlines():
        if ("断层" in line or "数字词" in line) and ("退役" not in line and "已删" not in line and "禁" not in line):
            raise AssertionError(f"step05 must not implement retired logic: {line.strip()[:80]}")


def test_check_segment1_05_shape_only_no_anchors_numbers():
    import inspect
    m = _load("check_segment1", "scripts/check_segment1.py")
    full = inspect.getsource(m)
    s = full.find("# --- 05-weapons")
    assert s > 0, "check_segment1 must have 05 section"
    src = full[s:s + 12000]
    assert "candidates" in src, "check_05 must认candidates (T1+T2==candidates)"
    assert "quote_details" in src
    assert "analysis" in src
    for banned in ("拿取动词", "verified 拿取", "把数/波次", "数字词", "最大断层", "registry-slice",
                   "anchors 须", "confidence须", "kind须", "inferred须"):
        assert banned not in src, f"check_05 must retire anchor/number/slice checks ({banned})"


def test_context_weapons_section_points_to_fewshot():
    txt = (REPO / "CONTEXT.md").read_text(encoding="utf-8")
    assert "step05-weapons-fewshot" in txt, "CONTEXT weapons段须以fewshot文件为准 (#47/#50作废)"
    # 只查 weapons.json + candidates.json 段落 (07 priorities 的断层动态保留，不在此卡)
    lines = txt.splitlines()
    wsec = "\n".join([ln for ln in lines if ("weapons.json" in ln or "candidates.json" in ln or "05-weapons" in ln)])
    for banned in ("verified+5", "is_core_gun"):
        assert banned not in wsec, f"CONTEXT must retire old 05口径 ({banned})"
    assert "断层" not in wsec or "禁数帽" in txt, "CONTEXT 05段不得再有断层切分 (须禁数帽)"


def test_audit_05_shows_analysis_not_anchors():
    html = (REPO / "templates" / "audit.html").read_text(encoding="utf-8")
    assert "audit-05-weapons" in html
    assert "analysis" in html, "audit 05节须展示analysis全过程"
    assert "discovery" in html.lower() and "ranking" in html.lower()
    assert "weaponCandidates" in html or "candidates.json" in html
    # discovery 结果必须有独立展示块（不止来源行），与 08 种子漏斗同级
    assert "Discovery candidates" in html, "audit 05节须独立展示discovery candidates（completeness可验）"
    assert "steps/05-weapons/candidates.json" in html
    # 05 输入直达：三项可点击 + modal 弹窗展示内容
    for marker in ('data-fileview="sentences"', 'data-fileview="vocab"',
                   'data-fileview="fewshot"', 'id="fileModal"', 'WEAPON_VOCAB_78'):
        assert marker in html, f"audit 05输入须可点击直达modal ({marker})"
