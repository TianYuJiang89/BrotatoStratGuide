"""#61 three-agent loop: frozen fewshot + discovery/evidence/ranking.

Seams (deterministic-first, no LLM in tests):
- prompt building: fewshot + full sentences + vocab/one-name/N-evidence, no score/verified/fault/number logic in code
- discovery validation: candidates non-empty/quotes verbatim/name in vocab/dedup
- evidence validation: shape only (tier/quotes/analysis/note<=120), note 短引逐字 (原话"..."须出自 quotes)
- ranking validation: T1>=1/T1+T2==candidates/self-consistency/no number cap, note 短引逐字 (须出自 evidence quotes)
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


def test_fewshot_frozen_per_task_exists():
    # v2: 按任务拆三本手册, 各贴各的 (例子全留、废话全砍)
    specs = {
        "discovery": ("TASK_DISCOVERY", "Slingshot", "claw tree", "禁数帽", "打勾"),
        "evidence": ("TASK_EVIDENCE", "T1/T2", "take a second minigun", "four screwdrivers", "copies", "未提及"),
        "ranking": ("TASK_RANKING", "Blunderbuss", "horde wave", "同句多引", "copies", "终定"),
    }
    for task, needles in specs.items():
        p = REPO / "prompts" / f"step05-{task}-fewshot.md"
        assert p.exists(), f"prompts/step05-{task}-fewshot.md must exist (#61 v2 三本手册)"
        txt = p.read_text(encoding="utf-8")
        assert "FROZEN" in txt
        for needle in needles:
            assert needle in txt, f"step05-{task}-fewshot must contain {needle}"
    # 三本互不串任务: ranking 手册里不许有 discovery 契约
    rtxt = (REPO / "prompts" / "step05-ranking-fewshot.md").read_text(encoding="utf-8")
    assert "TASK_DISCOVERY" not in rtxt and "TASK_EVIDENCE" not in rtxt
    dtxt = (REPO / "prompts" / "step05-discovery-fewshot.md").read_text(encoding="utf-8")
    assert "TASK_RANKING" not in dtxt and "TASK_EVIDENCE" not in dtxt


def test_prompt_build_contains_fewshot_sentences_only():
    m = _load("step05_loop", "scripts/step05_loop.py")
    fewshot_d = (REPO / "prompts" / "step05-discovery-fewshot.md").read_text(encoding="utf-8")
    fewshot_e = (REPO / "prompts" / "step05-evidence-fewshot.md").read_text(encoding="utf-8")
    fewshot_r = (REPO / "prompts" / "step05-ranking-fewshot.md").read_text(encoding="utf-8")
    sents = _sentences()
    vocab = _vocab()
    disc = m.build_discovery_prompt(sents, vocab[:2], 0, 2, fewshot_d)
    assert "Obviously, we'll take a second minigun" in disc
    assert "Minigun" in disc and "Screwdriver" in disc
    sec = disc.split("## 本批名单")[1].split("---")[0]
    assert "Minigun" in sec and "Screwdriver" in sec
    assert "SMG" not in sec, "discovery 只判本批 (动态分片, 不判其它)"
    assert "TASK_DISCOVERY" in disc
    assert "打勾" in disc
    ev = m.build_evidence_prompt("Minigun", sents, fewshot_e)
    assert "TASK_WEAPON: Minigun" in ev
    assert "Obviously, we'll take a second minigun" in ev
    # 一次只判一把: 任务行只提这一把
    assert "TASK_EVIDENCE" in ev
    rank = m.build_ranking_prompt(sents, [
        {"name_en": "Minigun", "tier": "T1", "quotes": [sents[0]["text"]],
         "analysis": "a", "note": "n"}], fewshot_r)
    assert "TASK_RANKING" in rank
    # 语义零进代码: 构建器不得注入退役规则
    import inspect
    for fn_name in ("build_discovery_prompt", "build_evidence_prompt", "build_ranking_prompt"):
        src = inspect.getsource(getattr(m, fn_name))
        for banned in ("verified+5", "score=", "最大断层", "数字词", "拿取动词"):
            assert banned not in src, f"{fn_name} must not encode retired anchor rules ({banned})"


def test_chunk_vocab_partition_covers_all():
    m = _load("step05_loop", "scripts/step05_loop.py")
    assert m.DISCOVERY_CHUNK_SIZE == 40
    vocab = [f"Weapon{i:03d}" for i in range(85)]
    chunks = m.chunk_vocab(vocab)
    assert [len(c) for c in chunks] == [40, 40, 5]
    assert sorted(sum([list(c) for c in chunks], [])) == sorted(vocab)
    # 动态分片: 片数=ceil(n/40), 不写死武器数
    assert len(m.chunk_vocab([f"W{i}" for i in range(78)])) == 2


def test_validate_discovery_chunk_ok_and_fail_loud():
    m = _load("step05_loop", "scripts/step05_loop.py")
    sents = _sentences()
    chunk = ["Minigun", "Screwdriver", "SMG"]
    good = {"收": [{"name_en": "Minigun", "quotes": [sents[0]["text"]]}],
            "丢": ["Screwdriver", "SMG"]}
    out = m.validate_discovery_chunk(good, chunk, sents)
    assert [c["name_en"] for c in out["收"]] == ["Minigun"]
    # 缺一件即fail (沉默遗漏不再可能)
    bad = {"收": [{"name_en": "Minigun", "quotes": [sents[0]["text"]]}],
           "丢": ["Screwdriver"]}
    with pytest.raises(SystemExit):
        m.validate_discovery_chunk(bad, chunk, sents)
    # 幻觉名即fail
    with pytest.raises(SystemExit):
        m.validate_discovery_chunk({"收": [{"name_en": "幻觉枪", "quotes": [sents[0]["text"]]}],
                                    "丢": chunk}, chunk, sents)
    # 收编quote即fail
    with pytest.raises(SystemExit):
        m.validate_discovery_chunk({"收": [{"name_en": "Minigun", "quotes": ["我编的一句"]}],
                                    "丢": ["Screwdriver", "SMG"]}, chunk, sents)
    # 收空quotes即fail
    with pytest.raises(SystemExit):
        m.validate_discovery_chunk({"收": [{"name_en": "Minigun", "quotes": []}],
                                    "丢": ["Screwdriver", "SMG"]}, chunk, sents)
    # 空收可以 (本批全路过), 但缺收键即fail
    out = m.validate_discovery_chunk({"收": [], "丢": chunk}, chunk, sents)
    assert out == {"收": [], "丢": sorted(chunk)}
    with pytest.raises(SystemExit):
        m.validate_discovery_chunk({"丢": chunk}, chunk, sents)
    # 串片/重叠/陌生即fail
    with pytest.raises(SystemExit):
        m.validate_discovery_chunk({"收": [{"name_en": "Minigun", "quotes": [sents[0]["text"]]}],
                                    "丢": ["Minigun", "SMG"]}, chunk, sents)
    # agent填count即fail
    bad = {"收": [{"name_en": "Minigun", "quotes": [sents[0]["text"]]}],
           "丢": ["Screwdriver", "SMG"], "count": 5}
    with pytest.raises(SystemExit):
        m.validate_discovery_chunk(bad, chunk, sents)
    # 退役字段出现即fail
    for old in ("anchors", "confidence", "kind", "inferred", "score", "reason",
                "candidates"):
        bad = {"收": [{"name_en": "Minigun", "quotes": [sents[0]["text"]]}],
               "丢": ["Screwdriver", "SMG"], old: "x"}
        with pytest.raises(SystemExit):
            m.validate_discovery_chunk(bad, chunk, sents)


def test_validate_evidence_ok_and_fail_loud():
    m = _load("step05_loop", "scripts/step05_loop.py")
    sents = _sentences()
    good = {
        "name_en": "Minigun",
        "tier": "T1",
        "quotes": [sents[0]["text"]],
        "analysis": "来源=捡→整局扛把子→T1。",
        "note": "主力连发，原话“take a second minigun”。",
        "copies": "见第二把就拿",
        "copies_quote": "take a second minigun",
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
    # note无短引标记即fail (人话须带逐字短引)
    bad = dict(good)
    bad["note"] = "主力连发，没有引用。"
    with pytest.raises(SystemExit):
        m.validate_evidence(bad, "Minigun", sents)
    # note短引改写即fail
    bad = dict(good)
    bad["note"] = "主力连发原话“take a third minigun”。"
    with pytest.raises(SystemExit):
        m.validate_evidence(bad, "Minigun", sents)
    # copies缺件即fail
    bad = dict(good)
    del bad["copies"]
    with pytest.raises(SystemExit):
        m.validate_evidence(bad, "Minigun", sents)
    # 未提及须空quote
    bad = dict(good)
    bad["copies"] = "未提及"
    with pytest.raises(SystemExit):
        m.validate_evidence(bad, "Minigun", sents)
    # copies_quote编数字即fail
    bad = dict(good)
    bad["copies"] = "八把成型"
    bad["copies_quote"] = "eight screwdrivers"
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
        {"name_en": "Minigun", "tier": "T1", "quotes": ["q1"], "analysis": "a", "note": "n1",
         "copies": "2把起", "copies_quote": "q1"},
        {"name_en": "SMG", "tier": "T2", "quotes": ["q2"], "analysis": "a", "note": "n2",
         "copies": "1把过渡", "copies_quote": "q2"},
    ]
    cands = ["Minigun", "SMG"]
    good = {"t1": [{"name_en": "Minigun", "note": "主力，原话“q1”。",
                      "copies": "2把起", "copies_quote": "q1"}],
            "t2": [{"name_en": "SMG", "note": "过渡，原话“q2”。",
                      "copies": "1把过渡", "copies_quote": "q2"}]}
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
    """Fake三段: discovery 打勾 (收2/丢2, 缺件即fail) → evidence各一把 → ranking切2/2, 自洽落盘."""
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
    收set = {"Minigun", "Screwdriver"}

    def fake_agent(kind, name_en, prompt):
        assert "FROZEN" in prompt or "fewshot" in prompt.lower() or len(prompt) > 100
        if kind == "discovery":
            # name_en == chunk id; 本批逐个打勾, 收+丢==本批
            chunks = m.chunk_vocab(sorted(quotes_by.keys()))
            ch = chunks[name_en]
            assert "打勾" in prompt
            for n in ch:
                assert n in prompt, f"本批名单须进 prompt: {n}"
            return {"收": [{"name_en": n, "quotes": quotes_by[n]} for n in ch if n in 收set],
                    "丢": [n for n in ch if n not in 收set]}
        if kind == "evidence":
            assert name_en in quotes_by
            tier = "T1" if name_en in ("Minigun", "Screwdriver") else "T2"
            return {"name_en": name_en, "tier": tier,
                    "quotes": quotes_by[name_en],
                    "analysis": f"{name_en}来源→机制→{tier}。",
                    "note": f"{name_en}人话原话\"{quotes_by[name_en][0][:12]}\"。",
                    "copies": f"{name_en}2把起",
                    "copies_quote": quotes_by[name_en][0][:12]}
        if kind == "ranking":
            return {"t1": [{"name_en": "Minigun", "note": f"主力原话\"{quotes_by['Minigun'][0][:12]}\"。", "copies": "2把起", "copies_quote": quotes_by['Minigun'][0][:12]},
                           {"name_en": "Screwdriver", "note": f"体系原话\"{quotes_by['Screwdriver'][0][:12]}\"。", "copies": "4把成型", "copies_quote": quotes_by['Screwdriver'][0][:12]}],
                    "t2": []}
        raise AssertionError(f"unknown kind {kind}")

    # 用小词汇表 monkeypatch load_weapon_vocab (+别名表置空, 假 vocab 不含 Gatling/Nuclear, #75)
    orig_vocab = m.load_weapon_vocab
    orig_alias = m.load_weapon_aliases
    m.load_weapon_vocab = lambda: sorted(quotes_by.keys())
    m.load_weapon_aliases = lambda: {}
    try:
        weapons = m.run_step05_loop(workdir, sents, agent_fn=fake_agent, force=True)
    finally:
        m.load_weapon_vocab = orig_vocab
        m.load_weapon_aliases = orig_alias
    assert sorted([w["name_en"] for w in weapons["t1"]]) == ["Minigun", "Screwdriver"]
    assert weapons["t2"] == []
    # 打勾合并: 收==candidates, 丢不进下游; 全表覆盖机检
    disc = json.loads((workdir / "steps" / "05-weapons" / "discovery.json")
                      .read_text(encoding="utf-8"))
    assert sorted(disc["收"]) == ["Minigun", "Screwdriver"]
    assert sorted(disc["丢"]) == ["Nuclear Launcher", "SMG"]
    assert sorted(disc["收"] + disc["丢"]) == sorted(quotes_by.keys())
    ch0 = json.loads((workdir / "steps" / "05-weapons" / "discovery-chunk-0.json")
                     .read_text(encoding="utf-8"))
    assert sorted([c["name_en"] for c in ch0["收"]] + ch0["丢"]) == sorted(quotes_by.keys())
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
    assert sorted(c["name_en"] for c in cands) == sorted(收set)
    for c in cands:
        assert c["count"] == len(c["quotes"])
    # fewshot 运行快照: 三本与 repo FROZEN 文件逐字节一致 (审计离线可读即认此件)
    for task in ("discovery", "evidence", "ranking"):
        snap = (workdir / "steps" / "05-weapons" / f"fewshot-{task}.md").read_text(encoding="utf-8")
        assert snap == (REPO / "prompts" / f"step05-{task}-fewshot.md").read_text(encoding="utf-8")
    # per_weapon 落盘 + ranking 终判落盘 (链: 名==candidates, check 验; 丢不进下游)
    for n in 收set:
        import re
        safe = re.sub(r"[^A-Za-z0-9]+", "_", n).strip("_")
        assert (workdir / "steps" / "05-weapons" / "per_weapon" / f"{safe}.json").exists()
    ranking = json.loads((workdir / "steps" / "05-weapons" / "ranking.json")
                         .read_text(encoding="utf-8"))
    assert sorted(x["name_en"] for x in ranking["t1"]) == ["Minigun", "Screwdriver"]
    assert ranking["t2"] == []


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
    assert "discovery.json" in src, "check_05 must验打勾覆盖 (分片+全表)"
    assert "quote_details" in src
    assert "analysis" in src
    assert "ranking.json" in src, "check_05 must验ranking终判名==candidates"
    assert "per_weapon" in src, "check_05 must验per_weapon evidence原始"
    assert "copies" in src, "check_05 must验配比逐字 (copies/copies_quote)"
    for banned in ("拿取动词", "verified 拿取", "把数/波次", "数字词", "最大断层", "registry-slice",
                   "anchors 须", "confidence须", "kind须", "inferred须"):
        assert banned not in src, f"check_05 must retire anchor/number/slice checks ({banned})"


def test_context_weapons_section_points_to_fewshot():
    txt = (REPO / "CONTEXT.md").read_text(encoding="utf-8")
    assert "step05-discovery-fewshot" in txt, "CONTEXT weapons段须以fewshot文件为准 (#47/#50作废)"
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
    # 审计节点: 每次 LLM 调用一行 (入参 prompt 全文 + 结果原文, 点开展示)
    for marker in ("agent-discovery.log.jsonl", "agent-evidence-",
                   "agent-ranking.log.jsonl", 'data-stepfile',
                   "evidence05", "ranking05", "per_weapon"):
        assert marker in html, f"audit 05节须按调用列节点 (入参+结果) ({marker})"
    assert "ranking.json" in html and "candidates.json" in html
    # 05 输入直达：三项可点击 + modal 弹窗展示内容
    for marker in ('data-fileview="sentences"', 'data-fileview="vocab"',
                   'data-fileview="fewshot"', 'id="fileModal"', 'WEAPON_VOCAB_78'):
        assert marker in html, f"audit 05输入须可点击直达modal ({marker})"
    # fewshot 快照：审计只读工作区（file:///picker/?base= 全通），check 验逐字节一致
    for marker in ('fewshot05', 'steps/05-weapons/fewshot-discovery.md',
                   'steps/05-weapons/fewshot-evidence.md',
                   'steps/05-weapons/fewshot-ranking.md'):
        assert marker in html, f"audit 须经工作区快照读fewshot ({marker})"


def test_ranking_prompt_copies_unmentioned_rule():
    """#71: ranking prompt 须明示 copies 未提及口径 (未提及+空串, 沿 evidence 口径)."""
    src = (REPO / "scripts" / "step05_loop.py").read_text(encoding="utf-8")
    assert "copies=未提及" in src and "copies_quote 空串" in src, \
        "ranking prompt 须写明 copies 未提及+空串口径 (#71)"


def test_selfcheck_frozen_shared_exists():
    """#72: 共享 frozen 自验文案存在 (跑检验→非零读报错→只改报错项→重跑; 禁自评)."""
    p = REPO / "prompts" / "selfcheck-frozen.md"
    assert p.exists(), "prompts/selfcheck-frozen.md must exist (#72 共享 frozen 文案)"
    txt = p.read_text(encoding="utf-8")
    assert "FROZEN" in txt, "共享文案须 FROZEN 头"
    for needle in ("跑检验", "非零", "只改报错项", "重跑检验", "看起来没问题",
                   "自修上限", "2 次", "计数落盘", "超限原样停", "外闸"):
        assert needle in txt, f"共享文案须含 {needle} (#72)"


def test_ranking_prompt_contains_selfcheck():
    """#72: ranking prompt 须含自验指令 (检验→只改报错项→重跑, 禁自评, 上限2+计数)."""
    m = _load("step05_loop", "scripts/step05_loop.py")
    fewshot_r = (REPO / "prompts" / "step05-ranking-fewshot.md").read_text(encoding="utf-8")
    sents = _sentences()
    evs = [{"name_en": "Minigun", "tier": "T1", "quotes": [sents[0]["text"]],
            "analysis": "a", "note": "n", "copies": "x", "copies_quote": sents[0]["text"][:6]}]
    prompt = m.build_ranking_prompt(sents, evs, fewshot_r)
    for needle in ("跑检验", "只改报错项", "重跑检验", "看起来没问题", "2 次"):
        assert needle in prompt, f"ranking prompt 须含自验指令 {needle} (#72 试点05 ranking)"


def test_ranking_loop_embeds_validator_cmd_and_count():
    """#72: ranking 真调后缀须给具体检验命令 + 计数文件 + 上限, 外闸不动."""
    src = (REPO / "scripts" / "step05_loop.py").read_text(encoding="utf-8")
    assert "validate_step05_ranking" in src, "ranking 真调须嵌入检验脚本命令 (#72)"
    assert "ranking.selfcheck.json" in src, "须指示计数落盘 ranking.selfcheck.json (#72)"
    assert "自修上限" in src and "2" in src, "须明示自修上限 2 次 (#72)"
    assert "超限原样停" in src, "须明示超限原样停交外闸 (#72)"
    # 外闸保留是底线: 代码校验 + max-1 cap 不动 (format max1/transient max2)
    assert "format_left = 1" in src, "外闸 max-1 cap 不动 (#72 底线)"
    assert "transient_left = 2" in src, "transient max2 口径不动 (#72)"


def test_ranking_loop_snapshots_selfcheck_provenance(tmp_path):
    """#72: ranking 运行须快照自验文案 (与 repo FROZEN 逐字节一致, 审计可查)."""
    m = _load("step05_loop", "scripts/step05_loop.py")
    sents = _sentences()
    workdir = tmp_path / "cyborg" / "ultimate"
    (workdir / "steps" / "05-weapons" / "per_weapon").mkdir(parents=True, exist_ok=True)
    (workdir / "outputs").mkdir(parents=True, exist_ok=True)
    quotes_by = {"Minigun": [sents[0]["text"]], "Screwdriver": [sents[1]["text"]]}

    def fake_agent(kind, name_en, prompt):
        if kind == "discovery":
            chunks = m.chunk_vocab(sorted(quotes_by.keys()))
            ch = chunks[name_en]
            return {"收": [{"name_en": n, "quotes": quotes_by[n]} for n in ch], "丢": []}
        if kind == "evidence":
            return {"name_en": name_en, "tier": "T1", "quotes": quotes_by[name_en],
                    "analysis": f"{name_en}来源→机制。", "note": f"{name_en}人话原话\"{quotes_by[name_en][0][:12]}\"。",
                    "copies": "未提及", "copies_quote": ""}
        if kind == "ranking":
            return {"t1": [{"name_en": n, "note": f"主力原话\"{quotes_by[n][0][:12]}\"。",
                               "copies": "未提及", "copies_quote": ""} for n in sorted(quotes_by)], "t2": []}
        raise AssertionError(kind)

    orig_vocab = m.load_weapon_vocab
    orig_alias = m.load_weapon_aliases
    m.load_weapon_vocab = lambda: sorted(quotes_by.keys())
    m.load_weapon_aliases = lambda: {}
    try:
        m.run_step05_loop(workdir, sents, agent_fn=fake_agent, force=True)
    finally:
        m.load_weapon_vocab = orig_vocab
        m.load_weapon_aliases = orig_alias
    snap = (workdir / "steps" / "05-weapons" / "selfcheck.md").read_text(encoding="utf-8")
    assert snap == (REPO / "prompts" / "selfcheck-frozen.md").read_text(encoding="utf-8"), \
        "自验快照须与 repo FROZEN 逐字节一致 (#72)"
