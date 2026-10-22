"""#62 three-agent loop for 03+07: frozen fewshot + discovery/evidence/ranking.

Seams (deterministic-first, no LLM in tests):
- prompt building: fewshot + full sentences + vocab/one-name/N-evidence (03) and
  grouping+ratings+weapons+phases+sentences (07), no slice/verb/gap logic in code
- discovery validation: item candidates non-empty/quotes verbatim/name in items vocab/dedup
- evidence validation: shape only (group suggestion/quotes/analysis/note<=120), note short-quote verbatim
- grouping-ranking validation: 4 groups cover candidates exactly, ban/shop consistency, note short-quote verbatim
- 07 validation: upgrades/shop non-empty (N dynamic by agent), names in ratings/candidates,
  ban exclusion, quotes verbatim, why/how_to_get non-empty
- count backfill by code (agent must not fill count)
- old anchor fields retired (tier/confidence/inferred/has_verb/verb/verb_type/mapped_to/surface_*,
  refusal list, max-gap cut) must be absent
- fail loud on missing/fabricated/hallucinated/ban-in-TopN (no fallback, no blank补)
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
        {"id": 1, "text": "We would really have liked to be able to pick up a pocket factory.",
         "start": "00:01:00.000", "end": "00:01:05.000", "start_s": 60.0, "end_s": 65.0, "t": 60},
        {"id": 2, "text": "Uh, I'm going to ban the boxing glove.",
         "start": "00:02:00.000", "end": "00:02:05.000", "start_s": 120.0, "end_s": 125.0, "t": 120},
        {"id": 3, "text": "Also, I'm just pretty much ignoring what the landmines are doing.",
         "start": "00:03:00.000", "end": "00:03:05.000", "start_s": 180.0, "end_s": 185.0, "t": 180},
        {"id": 4, "text": "I'll lock acid as well.",
         "start": "00:04:00.000", "end": "00:04:05.000", "start_s": 240.0, "end_s": 245.0, "t": 240},
    ]


def _vocab():
    return ["Pocket Factory", "Boxing Glove", "Landmines", "Acid", "Turret"]


def test_step0307_loop_module_exists():
    p = REPO / "scripts" / "step0307_loop.py"
    assert p.exists(), "scripts/step0307_loop.py must exist (#62 discovery/evidence/ranking + 07-ranking)"


def test_fewshot_frozen_03_and_07_exist():
    p03 = REPO / "prompts" / "step03-grouping-fewshot.md"
    assert p03.exists(), "prompts/step03-grouping-fewshot.md must exist (#62 FROZEN 20-shot)"
    t03 = p03.read_text(encoding="utf-8")
    assert "FROZEN" in t03
    for needle in ("TASK_DISCOVERY", "must_take", "mentioned_not_taken", "ban", "casual_mention",
                   "原话", "Top1", "打勾"):
        assert needle in t03, f"step03 fewshot must contain {needle}"
    # ban 语义样例替代拒绝动词表：须有 ban/recycle/sell 语义例，不许出现“拒绝动词表逐字”码味
    assert "recycle" in t03.lower() or "ban the boxing glove" in t03.lower()
    assert "拒绝动词表" not in t03 or "替代" in t03
    p07 = REPO / "prompts" / "step07-priorities-fewshot.md"
    assert p07.exists(), "prompts/step07-priorities-fewshot.md must exist (#62 07-ranking)"
    t07 = p07.read_text(encoding="utf-8")
    assert "FROZEN" in t07
    for needle in ("upgrades", "shop", "ban", "推翻", "断层"):
        assert needle in t07, f"step07 fewshot must contain {needle}"


def test_prompt_build_contains_fewshot_sentences_only():
    m = _load("step0307_loop", "scripts/step0307_loop.py")
    fewshot03 = (REPO / "prompts" / "step03-grouping-fewshot.md").read_text(encoding="utf-8")
    fewshot07 = (REPO / "prompts" / "step07-priorities-fewshot.md").read_text(encoding="utf-8")
    sents = _sentences()
    vocab = _vocab()
    chunks = m.chunk_vocab(vocab)
    assert len(chunks) >= 1 and sorted(sum(chunks, [])) == sorted(vocab)
    disc = m.build_discovery_prompt(sents, chunks[0], 0, len(chunks), fewshot03)
    assert "pick up a pocket factory" in disc
    assert "Pocket Factory" in disc and "Acid" in disc
    assert "TASK_DISCOVERY" in disc
    assert "打勾" in disc
    ev = m.build_evidence_prompt("Acid", sents, fewshot03)
    assert "TASK_ITEM: Acid" in ev or "Acid" in ev
    assert "pick up a pocket factory" in ev
    rank = m.build_grouping_ranking_prompt(sents, [
        {"name_en": "Acid", "group": "must_take", "quotes": [sents[3]["text"]],
         "analysis": "a", "note": "n"}], fewshot03)
    assert "TASK_GROUPING" in rank or "TASK_RANKING" in rank
    pri = m.build_priority_ranking_prompt(
        sents,
        [{"name_en": "Acid", "count": 1, "group": "must_take",
          "quotes": [sents[3]["text"]], "analysis": "a", "note": "n",
          "quote_details": []}],
        [{"term_en": "Ranged Damage", "rating": "S", "count": 2}],
        {"t1": [], "t2": []}, [], fewshot07)
    assert "TASK_PRIORITY" in pri
    # 语义零进代码：构建器不得注入退役规则
    import inspect
    for fn_name in ("build_discovery_prompt", "build_evidence_prompt",
                    "build_grouping_ranking_prompt", "build_priority_ranking_prompt"):
        src = inspect.getsource(getattr(m, fn_name))
        for banned in ("registry-slice", "最大断层", "拒绝动词", "拿取动词", "mean+stdev",
                       "mean + stdev", "pstdev", "gaps="):
            assert banned not in src, f"{fn_name} must not encode retired rules ({banned})"


def test_validate_discovery_chunk_ok_and_fail_loud():
    m = _load("step0307_loop", "scripts/step0307_loop.py")
    sents = _sentences()
    chunk = ["Acid", "Boxing Glove", "Landmines"]
    good = {"收": [{"name_en": "Acid", "quotes": [sents[3]["text"]]}],
            "丢": ["Boxing Glove", "Landmines"]}
    out = m.validate_discovery_chunk(good, chunk, sents)
    assert [c["name_en"] for c in out["收"]] == ["Acid"]
    assert sorted(out["丢"]) == ["Boxing Glove", "Landmines"]
    # 收幻觉名即fail
    with pytest.raises(SystemExit):
        m.validate_discovery_chunk({"收": [{"name_en": "幻觉道具", "quotes": [sents[0]["text"]]}],
                                    "丢": chunk}, chunk, sents)
    # 收编quote即fail
    with pytest.raises(SystemExit):
        m.validate_discovery_chunk({"收": [{"name_en": "Acid", "quotes": ["我编的一句"]}],
                                    "丢": ["Boxing Glove", "Landmines"]}, chunk, sents)
    # 收空证据即fail
    with pytest.raises(SystemExit):
        m.validate_discovery_chunk({"收": [{"name_en": "Acid", "quotes": []}],
                                    "丢": ["Boxing Glove", "Landmines"]}, chunk, sents)
    # 覆盖不全即fail (Landmines 无 verdict)
    with pytest.raises(SystemExit):
        m.validate_discovery_chunk({"收": [{"name_en": "Acid", "quotes": [sents[3]["text"]]}],
                                    "丢": ["Boxing Glove"]}, chunk, sents)
    # 收丢重叠即fail
    with pytest.raises(SystemExit):
        m.validate_discovery_chunk({"收": [{"name_en": "Acid", "quotes": [sents[3]["text"]]}],
                                    "丢": ["Acid", "Boxing Glove", "Landmines"]}, chunk, sents)
    # 陌生名即fail
    with pytest.raises(SystemExit):
        m.validate_discovery_chunk({"收": [],
                                    "丢": ["Acid", "Boxing Glove", "陌生道具"]}, chunk, sents)
    # agent填count即fail
    bad = {"收": [{"name_en": "Acid", "quotes": [sents[3]["text"]]}],
           "丢": ["Boxing Glove", "Landmines"], "count": 5}
    with pytest.raises(SystemExit):
        m.validate_discovery_chunk(bad, chunk, sents)
    for old in ("tier", "confidence", "inferred", "has_verb", "verb", "verb_type", "reason"):
        bad = {"收": [{"name_en": "Acid", "quotes": [sents[3]["text"]]}],
               "丢": ["Boxing Glove", "Landmines"], old: "x"}
        with pytest.raises(SystemExit):
            m.validate_discovery_chunk(bad, chunk, sents)


def test_validate_evidence_ok_and_fail_loud():
    m = _load("step0307_loop", "scripts/step0307_loop.py")
    sents = _sentences()
    good = {
        "name_en": "Acid",
        "group": "must_take",
        "quotes": [sents[3]["text"]],
        "analysis": "来源=锁→复购→体系位。",
        "note": "血少复购补血，原话“lock acid”。",
    }
    out = m.validate_evidence(good, "Acid", sents)
    assert out["group"] == "must_take"
    bad = dict(good)
    bad["quotes"] = []
    with pytest.raises(SystemExit):
        m.validate_evidence(bad, "Acid", sents)
    bad = dict(good)
    bad["name_en"] = "Turret"
    with pytest.raises(SystemExit):
        m.validate_evidence(bad, "Acid", sents)
    bad = dict(good)
    bad["quotes"] = ["编的一句"]
    with pytest.raises(SystemExit):
        m.validate_evidence(bad, "Acid", sents)
    bad = dict(good)
    bad["note"] = "x" * 121
    with pytest.raises(SystemExit):
        m.validate_evidence(bad, "Acid", sents)
    bad = dict(good)
    bad["note"] = "血少复购补血，没有引用。"
    with pytest.raises(SystemExit):
        m.validate_evidence(bad, "Acid", sents)
    bad = dict(good)
    bad["group"] = "乱分组"
    with pytest.raises(SystemExit):
        m.validate_evidence(bad, "Acid", sents)
    bad = dict(good)
    bad["count"] = 3
    with pytest.raises(SystemExit):
        m.validate_evidence(bad, "Acid", sents)


def test_validate_grouping_ranking_ok_and_fail_loud():
    m = _load("step0307_loop", "scripts/step0307_loop.py")
    evs = [
        {"name_en": "Acid", "group": "must_take", "quotes": ["q1"],
         "analysis": "a", "note": "n1"},
        {"name_en": "Boxing Glove", "group": "ban", "quotes": ["q2"],
         "analysis": "a", "note": "n2"},
    ]
    cands = ["Acid", "Boxing Glove"]
    good = {
        "must_take": [{"name_en": "Acid", "note": "复购原话“q1”。"}],
        "mentioned_not_taken": [],
        "ban": [{"name_en": "Boxing Glove", "note": "ban 出局原话“q2”。"}],
        "casual_mention": [],
    }
    out = m.validate_grouping_ranking(good, cands, evs)
    assert [x["name_en"] for x in out["must_take"]] == ["Acid"]
    # 四组须覆盖 candidates，一把不多一把不少
    bad = {"must_take": [{"name_en": "Acid", "note": "n原话“q1”。"}],
           "mentioned_not_taken": [], "ban": [], "casual_mention": []}
    with pytest.raises(SystemExit):
        m.validate_grouping_ranking(bad, cands, evs)
    bad = {"must_take": [{"name_en": "幻觉道具", "note": "n原话“q1”。"}],
           "mentioned_not_taken": [], "ban": [{"name_en": "Boxing Glove", "note": "n原话“q2”。"}],
           "casual_mention": []}
    with pytest.raises(SystemExit):
        m.validate_grouping_ranking(bad, cands, evs)
    bad = {"must_take": [{"name_en": "Acid", "note": "没有短引"}],
           "mentioned_not_taken": [], "ban": [{"name_en": "Boxing Glove", "note": "n原话“q2”。"}],
           "casual_mention": []}
    with pytest.raises(SystemExit):
        m.validate_grouping_ranking(bad, cands, evs)


def test_validate_priority_ok_and_ban_in_topn_fail():
    m = _load("step0307_loop", "scripts/step0307_loop.py")
    sents = _sentences()
    grouping = [
        {"name_en": "Acid", "count": 1, "group": "must_take", "quotes": [sents[3]["text"]]},
        {"name_en": "Boxing Glove", "count": 1, "group": "ban", "quotes": [sents[1]["text"]]},
    ]
    ratings = [{"term_en": "Ranged Damage", "rating": "S", "count": 2}]
    good = {
        "upgrades": [{"name": "Ranged Damage", "why": "三倍率原话“triple” motto",
                      "how_to_get": "商店见即买", "quotes": [sents[0]["text"]],
                      "analysis": "来源=捡→入口→Top。"}],
        "shop": [{"name": "Acid", "why": "复购原话“lock acid”。",
                  "how_to_get": "roll 到即锁", "quotes": [sents[3]["text"]],
                  "analysis": "来源=锁→Top。"}],
    }
    # why 短引须逐字：上面的 why 不含 quotes 短引，修正为合法
    good["upgrades"][0]["why"] = "三倍率入口，原话“pick up a pocket factory”。"
    out = m.validate_priority(good, sents, grouping, ratings)
    assert [u["name"] for u in out["upgrades"]] == ["Ranged Damage"]
    # ban 件进 TopN 即 fail
    bad = {"upgrades": good["upgrades"],
           "shop": [{"name": "Boxing Glove", "why": "x原话“ban the boxing glove”。",
                     "how_to_get": "拿", "quotes": [sents[1]["text"]], "analysis": "a"}]}
    with pytest.raises(SystemExit):
        m.validate_priority(bad, sents, grouping, ratings)
    # 空 TopN 即 fail（码只验非空，不验断层）
    with pytest.raises(SystemExit):
        m.validate_priority({"upgrades": [], "shop": good["shop"]}, sents, grouping, ratings)
    with pytest.raises(SystemExit):
        m.validate_priority({"upgrades": good["upgrades"], "shop": []}, sents, grouping, ratings)
    # 幻觉名即 fail
    bad2 = {"upgrades": [{"name": "幻觉升级", "why": "x原话“pick up a pocket factory”。",
                          "how_to_get": "拿", "quotes": [sents[0]["text"]], "analysis": "a"}],
            "shop": good["shop"]}
    with pytest.raises(SystemExit):
        m.validate_priority(bad2, sents, grouping, ratings)
    # 编 quote 即 fail
    bad3 = {"upgrades": [{"name": "Ranged Damage", "why": "x原话“pick up a pocket factory”。",
                          "how_to_get": "拿", "quotes": ["编的一句"], "analysis": "a"}],
            "shop": good["shop"]}
    with pytest.raises(SystemExit):
        m.validate_priority(bad3, sents, grouping, ratings)


def test_chunk_vocab_partition_covers_all():
    m = _load("step0307_loop", "scripts/step0307_loop.py")
    vocab = [f"Item{i:03d}" for i in range(85)]
    chunks = m.chunk_vocab(vocab, size=40)
    assert len(chunks) == 3
    assert all(len(c) <= 40 for c in chunks)
    assert sorted(sum(chunks, [])) == sorted(vocab)
    # 动态：任意数量自动分片，不写死片数
    assert len(m.chunk_vocab(["a", "b"])) == 1


def test_run_loops_with_fake_agents_cyborg_shape(tmp_path):
    m = _load("step0307_loop", "scripts/step0307_loop.py")
    sents = _sentences()
    workdir = tmp_path / "cyborg" / "ultimate"
    (workdir / "steps" / "03-grouping" / "per_item").mkdir(parents=True, exist_ok=True)
    (workdir / "steps" / "07-priorities").mkdir(parents=True, exist_ok=True)
    (workdir / "outputs").mkdir(parents=True, exist_ok=True)

    quotes_by = {
        "Acid": [sents[3]["text"]],
        "Boxing Glove": [sents[1]["text"]],
        "Landmines": [sents[2]["text"]],
    }

    def fake03(kind, name_en, prompt):
        if kind == "discovery":
            # name_en 为分片 id；本轮 vocab 3 件只切出 1 片：收 2 丢 1
            assert name_en == 0, f"expect single chunk, got {name_en}"
            assert "打勾" in prompt
            return {"收": [{"name_en": "Acid", "quotes": quotes_by["Acid"]},
                            {"name_en": "Boxing Glove", "quotes": quotes_by["Boxing Glove"]}],
                    "丢": ["Landmines"]}
        if kind == "evidence":
            assert name_en in quotes_by
            grp = {"Acid": "must_take", "Boxing Glove": "ban",
                   "Landmines": "mentioned_not_taken"}[name_en]
            return {"name_en": name_en, "group": grp, "quotes": quotes_by[name_en],
                    "analysis": f"{name_en}来源→分组→{grp}。",
                    "note": f"{name_en}人话原话\"{quotes_by[name_en][0][:12]}\"。"}
        if kind == "grouping-ranking":
            return {"must_take": [{"name_en": "Acid", "note": f"复购原话\"{quotes_by['Acid'][0][:12]}\"。"}],
                    "mentioned_not_taken": [],
                    "ban": [{"name_en": "Boxing Glove", "note": f"ban出局原话\"{quotes_by['Boxing Glove'][0][:12]}\"。"}],
                    "casual_mention": []}
        raise AssertionError(f"unknown kind {kind}")

    orig_vocab = m.load_item_vocab
    m.load_item_vocab = lambda: sorted(quotes_by.keys())
    try:
        grouping = m.run_step03_loop(workdir, sents, agent_fn=fake03, force=True)
    finally:
        m.load_item_vocab = orig_vocab
    got = sorted(g["name_en"] for g in grouping)
    assert got == ["Acid", "Boxing Glove"]
    for g in grouping:
        assert g["count"] == len(g["quotes"]) == 1
        assert len(g["quote_details"]) == 1
        for old in ("tier", "confidence", "inferred", "has_verb", "verb",
                     "verb_type", "mapped_to", "reason"):
            assert old not in g, f"retired field {old} must be absent"
        assert g["analysis"] and g["note"]
    cands = json.loads((workdir / "steps" / "03-grouping" / "candidates.json")
                       .read_text(encoding="utf-8"))
    assert sorted(c["name_en"] for c in cands) == ["Acid", "Boxing Glove"]
    # 打勾覆盖证明：收+丢 == 全表，一个不许漏
    discov = json.loads((workdir / "steps" / "03-grouping" / "discovery.json")
                        .read_text(encoding="utf-8"))
    assert sorted(discov["收"] + discov["丢"]) == sorted(quotes_by.keys())
    assert (workdir / "steps" / "03-grouping" / "discovery-chunk-0.json").exists()
    # snapshots
    assert (workdir / "steps" / "03-grouping" / "fewshot.md").read_text(encoding="utf-8") == \
        (REPO / "prompts" / "step03-grouping-fewshot.md").read_text(encoding="utf-8")

    # 07 loop fake
    ratings = [{"term_en": "Ranged Damage", "rating": "S", "count": 2}]

    def fake07(kind, name_en, prompt):
        assert kind == "priority-ranking"
        return {"upgrades": [{"name": "Ranged Damage",
                              "why": f"三倍率原话\"{sents[0]['text'][:12]}\"。",
                              "how_to_get": "商店见即买",
                              "quotes": [sents[0]["text"]],
                              "analysis": "来源=捡→入口→Top。"}],
                "shop": [{"name": "Acid",
                          "why": f"复购原话\"{quotes_by['Acid'][0][:12]}\"。",
                          "how_to_get": "roll 到即锁",
                          "quotes": quotes_by["Acid"],
                          "analysis": "来源=锁→Top。"}]}

    pri = m.run_step07_loop(workdir, sents, grouping, ratings,
                            {"t1": [], "t2": []}, [], agent_fn=fake07, force=True)
    assert [u["name"] for u in pri["upgrades"]] == ["Ranged Damage"]
    assert [s["name"] for s in pri["shop"]] == ["Acid"]
    assert (workdir / "steps" / "07-priorities" / "fewshot.md").read_text(encoding="utf-8") == \
        (REPO / "prompts" / "step07-priorities-fewshot.md").read_text(encoding="utf-8")


def test_run_segment1_step03_uses_loop_not_anchors():
    import inspect
    m = _load("run_segment1", "scripts/run_segment1.py")
    assert hasattr(m, "step03")
    src = inspect.getsource(m.step03)
    assert "step0307_loop" in src or "per_item" in src or "discovery" in src.lower()
    for banned in ('"registry-slice', '"registry_slice', '"02-verbs',
                   "mean+stdev", "pstdev", "_BAN", "_TAKE", "_SKIP"):
        assert banned not in src, f"step03 must retire anchor/slice rules ({banned})"


def test_run_segment2_step07_uses_loop_not_gaps():
    import inspect
    m = _load("run_segment2", "scripts/run_segment2.py")
    assert hasattr(m, "step07")
    src = inspect.getsource(m.step07)
    assert "step0307_loop" in src or "step07_loop" in src or "priority" in src.lower() or "priorities" in src.lower()
    for banned in ("gaps=", "最大断层", "_REJECT", "通用顺延", "sa[:3]", "断层切分"):
        assert banned not in src, f"step07 must retire gap/refusal code rules ({banned})"


def test_check_segment1_03_shape_only_no_verb_gap_refusal():
    import inspect
    m = _load("check_segment1", "scripts/check_segment1.py")
    full = inspect.getsource(m)
    s = full.find("# --- 03-grouping")
    assert s > 0, "check_segment1 must have 03 section"
    e = full.find("# --- 04-attributes", s)
    src = full[s:e] if e > s else full[s:s + 12000]
    assert "candidates" in src, "check_03 must认candidates (grouping==candidates)"
    assert "discovery.json" in src, "check_03 must验打勾覆盖 (分片+全表)"
    assert "quote_details" in src
    assert "analysis" in src
    assert "per_item" in src or "ranking.json" in src
    for banned in ("拿取动词", "拒绝动词", "最大断层", "68 (count>0", "verified 拿取",
                   "must_take must have take-verb", "ban must have rejection"):
        assert banned not in src, f"check_03 must retire anchor/number/slice checks ({banned})"


def test_check_segment2_07_no_gap_no_refusal_list():
    import inspect
    m = _load("check_segment2", "scripts/check_segment2.py")
    full = inspect.getsource(m)
    s = full.find("# --- 07-priorities")
    assert s > 0, "check_segment2 must have 07 section"
    src = full[s:s + 15000]
    assert "candidates" in src or "grouping" in src
    assert "ban" in src.lower()
    for banned in ("最大断层", "gaps=", "_REJECT", "通用顺延", "断层 TopN (期望"):
        assert banned not in src, f"check_07 must retire gap/refusal checks ({banned})"


def test_context_groups_priorities_point_to_fewshot():
    txt = (REPO / "CONTEXT.md").read_text(encoding="utf-8")
    assert "step03-grouping-fewshot" in txt, "CONTEXT groups段须以fewshot文件为准 (#62)"
    assert "step07-priorities-fewshot" in txt, "CONTEXT priorities段须以fewshot文件为准 (#62)"
    wsec = "\n".join([ln for ln in txt.splitlines()
                       if ("groups.json" in ln or "priorities.json" in ln or "candidates.json" in ln
                           or "03-grouping" in ln or "07-priorities" in ln)])
    for banned in ("mean+stdev", "最大断层", "拒绝动词", "拿取系动词"):
        assert banned not in wsec, f"CONTEXT must retire old 03/07口径 ({banned})"


def test_audit_03_07_show_nodes_not_anchors():
    html = (REPO / "templates" / "audit.html").read_text(encoding="utf-8")
    assert "audit-03-grouping" in html
    assert "audit-07-priorities" in html
    assert "analysis" in html
    assert "discovery" in html.lower() and "ranking" in html.lower()
    for marker in ("agent-discovery.log.jsonl", "agent-evidence-",
                   "agent-ranking.log.jsonl", "per_item", "fewshot.md"):
        assert marker in html, f"audit 03节须按调用列节点 ({marker})"


def test_discovery_chunk_suffix_file_write_takes_precedence():
    """#70: discovery chunk 后缀须写明文件落盘优先 (消歧 JSON-only vs 写文件)."""
    src = (REPO / "scripts" / "step0307_loop.py").read_text(encoding="utf-8")
    assert "文件落盘为必须" in src, "discovery chunk prompt 须声明落盘必须 (#70)"
    assert "只输出一件 JSON" in src and "文件内容格式" in src, \
        "须说明 JSON-only 指文件内容格式 (#70)"
