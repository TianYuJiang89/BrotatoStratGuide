"""#65 two-agent loop for 07: frozen fewshot + selection/wording.

Seams (deterministic-first, no LLM in tests):
- prompt building: fewshot + full sentences + grouping/ratings/weapons/phases summaries (no count/gap/verb/verified logic in code)
- selection validation: upgrades/shop non-empty (N dynamic)/names in ratings/candidates/ban+T1 exclusion/quotes verbatim/dedup
- wording validation: name aligned/why+how non-empty/why short verbatim/no invented numbers/not-whole-copy
- merge: wordings N==selection N/name aligned/quotes==selection/quote_details backfill
- retired: count max-gap both sides/refusal verb table/verified gate/T1-code-rule/Top1-code-rule/why-along-reason/07-read-verbs must be absent
- fail loud on missing/fabricated/hallucinated/ban-in-TopN/T1-in-shop/empty-TopN (no fallback)
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
        {"id": 1, "text": "You buy ranged damage at triple the normal rate, uh, which is of course incredibly strong.",
         "start": "00:01:07.760", "end": "00:01:15.510", "start_s": 67.76, "end_s": 75.51, "t": 67},
        {"id": 2, "text": "Minigun gives you the ability to use life steal extremely efficiently.",
         "start": "00:01:30.000", "end": "00:01:35.109", "start_s": 90.0, "end_s": 95.109, "t": 90},
        {"id": 3, "text": "So, our turrets are actually contributing some reasonable damage as well.",
         "start": "00:19:00.160", "end": "00:19:08.390", "start_s": 1140.16, "end_s": 1148.39, "t": 1140},
        {"id": 4, "text": "Uh, I'm going to ban the boxing glove.",
         "start": "00:02:00.000", "end": "00:02:05.000", "start_s": 120.0, "end_s": 125.0, "t": 120},
        {"id": 5, "text": "Even the Tyler that we got pretty near the end of the game dealt 11,000 damage because it scales off of our engineering at 90% and that stat is so high.",
         "start": "00:32:33.039", "end": "00:32:45.110", "start_s": 1953.039, "end_s": 1965.11, "t": 1953},
        {"id": 6, "text": "And I'll buy the blindfold cuz 128 for five crit chance isn't great, but we actually have some pretty significant benefits from crit chance.",
         "start": "00:05:00.000", "end": "00:05:05.000", "start_s": 300.0, "end_s": 305.0, "t": 300},
    ]


def _grouping():
    s = _sentences()
    return [
        {"name_en": "Turret", "group": "must_take", "note": "工程转后跟上原话“turrets are actually contributing”。",
         "quotes": [s[2]["text"]], "count": 1},
        {"name_en": "Pocket Factory", "group": "must_take", "note": "后半保险原话“really good damage”。",
         "quotes": [s[2]["text"]], "count": 1},
        {"name_en": "Boxing Glove", "group": "ban", "note": "ban出局原话“ban the boxing glove”。",
         "quotes": [s[3]["text"]], "count": 1},
        {"name_en": "Tyler", "group": "must_take", "note": "残局伤害原话“11,000 damage”。",
         "quotes": [s[4]["text"]], "count": 1},
    ]


def _ratings():
    return [
        {"term_en": "Ranged Damage", "rating": "S", "count": 6},
        {"term_en": "Life Steal", "rating": "A", "count": 6},
        {"term_en": "Crit Chance", "rating": "B", "count": 5},
        {"term_en": "Engineering", "rating": "A", "count": 5},
    ]


def _weapons():
    return {"t1": [{"name_en": "Minigun"}, {"name_en": "Screwdriver"}], "t2": []}


def _phases():
    return [{"phase": "前期远程攒伤转工程", "waves": "", "goal": "前半波远程爆发"}]


def test_step07_loop_module_exists():
    p = REPO / "scripts" / "step07_loop.py"
    assert p.exists(), "scripts/step07_loop.py must exist (#65 selection/wording)"


def test_fewshot_frozen_20_shot_exists():
    p = REPO / "prompts" / "step07-priorities-fewshot.md"
    assert p.exists(), "prompts/step07-priorities-fewshot.md must exist (#65 FROZEN 20-shot)"
    txt = p.read_text(encoding="utf-8")
    assert "FROZEN" in txt
    for needle in ("TASK_SELECTION", "TASK_WORDING", "选择", "文案",
                   "upgrades", "shop", "ban", "T1", "N 动态",
                   "B 级", "原话", "数字不丢", "未提空出", "推翻", "禁断层"):
        assert needle in txt, f"step07 fewshot must contain {needle}"
    # 选择8 + 文案8 + 负例4 = 20 例标记
    assert txt.count("SEL-") >= 8, "fewshot must have >=8 selection examples"
    assert txt.count("WRD-") >= 8, "fewshot must have >=8 wording examples"
    assert txt.count("NEG-") >= 4, "fewshot must have >=4 negative examples"
    # 负例4: 数断层 TopN/动词表顺延/整句复制/T1 进商店
    assert "断层" in txt and "NEG-" in txt
    assert "动词表" in txt or "拒绝动词" in txt or "动词" in txt


def test_prompt_build_contains_fewshot_sentences_only():
    m = _load("step07_loop", "scripts/step07_loop.py")
    fewshot = (REPO / "prompts" / "step07-priorities-fewshot.md").read_text(encoding="utf-8")
    sents = _sentences()
    sel = m.build_selection_prompt(sents, _grouping(), _ratings(), _weapons(), _phases(), fewshot)
    assert "You buy ranged damage at triple the normal rate" in sel
    assert "TASK_SELECTION" in sel
    assert "N 动态" in sel or "Top1" in sel or "非空" in sel
    item = {"name": "Ranged Damage", "quotes": [sents[0]["text"]]}
    w = m.build_wording_prompt(item, sents, fewshot_text=fewshot)
    assert "TASK_WORDING" in w or "TASK_ITEM" in w
    assert "Ranged Damage" in w
    assert "triple the normal rate" in w
    # 语义零进代码：构建器不得注入退役规则
    import inspect
    for fn_name in ("build_selection_prompt", "build_wording_prompt"):
        src = inspect.getsource(getattr(m, fn_name))
        for banned in ("registry-slice", "最大断层", "拒绝动词", "拿取动词", "mean+stdev",
                       "mean + stdev", "pstdev", "gaps=", "verified", "02-verbs"):
            assert banned not in src, f"{fn_name} must not encode retired rules ({banned})"


def _syn_for(names):
    j = "、".join(names)
    return {"tradeoff": f"跨侧取舍覆盖{j}：升级先保，商店让路",
            "rhythm": f"按06排先后覆盖{j}：前期拿中期转后期守",
            "exceptions": f"例外覆盖{j}：B进有据，丢掉的暂放"}


def test_validate_selection_ok_and_fail_loud():
    m = _load("step07_loop", "scripts/step07_loop.py")
    sents = _sentences()
    grouping, ratings, weapons = _grouping(), _ratings(), _weapons()
    good = {"upgrades": [{"name": "Ranged Damage", "quotes": [sents[0]["text"]]}],
            "shop": [{"name": "Turret", "quotes": [sents[2]["text"]]}],
            "synthesis": _syn_for(["Ranged Damage", "Turret"])}
    out = m.validate_selection(good, sents, grouping, ratings, weapons)
    assert [u["name"] for u in out["upgrades"]] == ["Ranged Damage"]
    # B 级例外允许 (S/A 优先但 B 可例外, 码只验名在表)
    b_good = {"upgrades": [{"name": "Crit Chance", "quotes": [sents[5]["text"]]}],
              "shop": [{"name": "Turret", "quotes": [sents[2]["text"]]}],
              "synthesis": _syn_for(["Crit Chance", "Turret"])}
    out = m.validate_selection(b_good, sents, grouping, ratings, weapons)
    assert [u["name"] for u in out["upgrades"]] == ["Crit Chance"]
    # 空 TopN 即 fail (码只验非空, 不验断层)
    with pytest.raises(SystemExit):
        m.validate_selection({"upgrades": [], "shop": good["shop"], "synthesis": good["synthesis"]}, sents, grouping, ratings, weapons)
    with pytest.raises(SystemExit):
        m.validate_selection({"upgrades": good["upgrades"], "shop": [], "synthesis": good["synthesis"]}, sents, grouping, ratings, weapons)
    # synthesis 缺件即 fail (三句非空+点名)
    with pytest.raises(SystemExit):
        m.validate_selection({"upgrades": good["upgrades"], "shop": good["shop"]}, sents, grouping, ratings, weapons)
    with pytest.raises(SystemExit):
        m.validate_selection({"upgrades": good["upgrades"], "shop": good["shop"],
                              "synthesis": {"tradeoff": "", "rhythm": "x", "exceptions": "y"}}, sents, grouping, ratings, weapons)
    with pytest.raises(SystemExit):
        m.validate_selection({"upgrades": good["upgrades"], "shop": good["shop"],
                              "synthesis": {"tradeoff": "没点名", "rhythm": "没点名", "exceptions": "没点名"}}, sents, grouping, ratings, weapons)
    # 幻觉名即 fail
    with pytest.raises(SystemExit):
        m.validate_selection({"upgrades": [{"name": "幻觉升级", "quotes": [sents[0]["text"]]}],
"shop": good["shop"], "synthesis": good["synthesis"]}, sents, grouping, ratings, weapons)
    with pytest.raises(SystemExit):
        m.validate_selection({"upgrades": good["upgrades"],
                              "shop": [{"name": "幻觉道具", "quotes": [sents[0]["text"]]}],
                              "synthesis": good["synthesis"]},
                             sents, grouping, ratings, weapons)
    # 编 quote 即 fail
    with pytest.raises(SystemExit):
        m.validate_selection({"upgrades": [{"name": "Ranged Damage", "quotes": ["我编的一句"]}],
                              "shop": good["shop"], "synthesis": good["synthesis"]}, sents, grouping, ratings, weapons)
    # 空证据即 fail
    with pytest.raises(SystemExit):
        m.validate_selection({"upgrades": [{"name": "Ranged Damage", "quotes": []}],
                              "shop": good["shop"], "synthesis": good["synthesis"]}, sents, grouping, ratings, weapons)
    # ban 件进 TopN 即 fail
    with pytest.raises(SystemExit):
        m.validate_selection({"upgrades": good["upgrades"],
                              "shop": [{"name": "Boxing Glove", "quotes": [sents[3]["text"]]}],
                              "synthesis": _syn_for(["Ranged Damage", "Boxing Glove"])}, sents, grouping, ratings, weapons)
    # T1 入 shop 即 fail (shop∩T1=∅)
    t1_grouping = grouping + [{"name_en": "Minigun", "group": "must_take",
                               "note": "x", "quotes": [sents[1]["text"]], "count": 1}]
    with pytest.raises(SystemExit):
        m.validate_selection({"upgrades": good["upgrades"],
                              "shop": [{"name": "Minigun", "quotes": [sents[1]["text"]]}],
                              "synthesis": _syn_for(["Ranged Damage", "Minigun"])},
                             sents, t1_grouping, ratings, weapons)
    # 重复即 fail (upgrades+shop 去重)
    with pytest.raises(SystemExit):
        m.validate_selection({"upgrades": [{"name": "Ranged Damage", "quotes": [sents[0]["text"]]}],
"shop": [{"name": "Ranged Damage", "quotes": [sents[0]["text"]]}],
                              "synthesis": _syn_for(["Ranged Damage", "Ranged Damage"])},
                             sents,
                             grouping + [{"name_en": "Ranged Damage", "group": "must_take",
                                          "note": "x", "quotes": [sents[0]["text"]], "count": 1}],
                             ratings + [{"term_en": "Turret", "rating": "S", "count": 1}],
                             weapons)
    # 退役字段出现即 fail (why/how/count/analysis 只活 wording/代码)
    for old in ("count", "why", "how_to_get", "analysis", "quote_details", "verified"):
        bad = {"upgrades": [{"name": "Ranged Damage", "quotes": [sents[0]["text"]], old: "x"}],
               "shop": good["shop"], "synthesis": good["synthesis"]}
        with pytest.raises(SystemExit):
            m.validate_selection(bad, sents, grouping, ratings, weapons)


def test_validate_wording_ok_and_fail_loud():
    m = _load("step07_loop", "scripts/step07_loop.py")
    sents = _sentences()
    item = {"name": "Tyler", "quotes": [sents[4]["text"]]}
    good = {"name": "Tyler",
            "why": "残局吃工程打出伤害，原话“dealt 11,000 damage because it scales off of our engineering at 90%”。",
            "how_to_get": "与包横幅同波商店买入"}
    out = m.validate_wording(good, item, sents)
    assert out["name"] == "Tyler"
    # name 不对即 fail (自洽)
    bad = dict(good)
    bad["name"] = "别的项"
    with pytest.raises(SystemExit):
        m.validate_wording(bad, item, sents)
    # why 太短即 fail
    bad = dict(good)
    bad["why"] = "太短"
    with pytest.raises(SystemExit):
        m.validate_wording(bad, item, sents)
    # why 缺短引即 fail
    bad = dict(good)
    bad["why"] = "残局吃工程打出伤害，没有引用标记。"
    with pytest.raises(SystemExit):
        m.validate_wording(bad, item, sents)
    # 短引改写即 fail
    bad = dict(good)
    bad["why"] = "残局伤害，原话“dealt 99,999 damage”。。"
    with pytest.raises(SystemExit):
        m.validate_wording(bad, item, sents)
    # 整句复制即 fail (小结≠原文)
    bad = dict(good)
    bad["why"] = sents[4]["text"]
    with pytest.raises(SystemExit):
        m.validate_wording(bad, item, sents)
    # 编数字即 fail (≥2 位数字须出自 quotes)
    bad = dict(good)
    bad["why"] = "残局伤害 99,999，原话“dealt 11,000 damage”。。"
    with pytest.raises(SystemExit):
        m.validate_wording(bad, item, sents)
    bad = dict(good)
    bad["how_to_get"] = "wave 99 商店买入"
    with pytest.raises(SystemExit):
        m.validate_wording(bad, item, sents)
    # 数字不丢通过 (11,000/90% 出自 quotes)
    ok = dict(good)
    out = m.validate_wording(ok, item, sents)
    assert "11,000" in out["why"]
    # 未提空出通过 (无数字 quotes, 文案不写数字)
    item2 = {"name": "Ranged Damage", "quotes": [sents[0]["text"]]}
    good2 = {"name": "Ranged Damage",
             "why": "三倍率入口全程堆，原话“triple the normal rate”。",
             "how_to_get": "升级优先拿"}
    out = m.validate_wording(good2, item2, sents)
    assert out["name"] == "Ranged Damage"
    # 退役字段出现即 fail
    for old in ("quotes", "analysis", "count", "quote_details", "verified"):
        bad = dict(good)
        bad[old] = "x" if old not in ("quotes", "quote_details") else [sents[4]["text"]]
        with pytest.raises(SystemExit):
            m.validate_wording(bad, item, sents)


def test_run_loop_with_fake_agents_cyborg_shape(tmp_path):
    m = _load("step07_loop", "scripts/step07_loop.py")
    sents = _sentences()
    workdir = tmp_path / "cyborg" / "ultimate"
    (workdir / "steps" / "07-priorities" / "per_item").mkdir(parents=True, exist_ok=True)
    (workdir / "outputs").mkdir(parents=True, exist_ok=True)
    grouping, ratings, weapons, phases = _grouping(), _ratings(), _weapons(), _phases()

    def fake_agent(kind, name, prompt):
        assert "FROZEN" in prompt or len(prompt) > 100
        if kind == "selection":
            assert "TASK_SELECTION" in prompt
            assert "You buy ranged damage at triple the normal rate" in prompt
            assert "synthesis" in prompt
            return {"upgrades": [{"name": "Ranged Damage", "quotes": [sents[0]["text"]]}],
"shop": [{"name": "Turret", "quotes": [sents[2]["text"]]}],
                    "synthesis": {"tradeoff": "覆盖Ranged Damage、Turret：升级先保商店让路",
                                  "rhythm": "覆盖Ranged Damage、Turret：按06排先后",
                                  "exceptions": "覆盖Ranged Damage、Turret：无B例外"}}
        if kind == "wording":
            assert name in ("Ranged Damage", "Turret")
            if name == "Ranged Damage":
                return {"name": name,
                        "why": "三倍率入口全程堆，原话“triple the normal rate”。",
                        "how_to_get": "升级优先拿"}
            return {"name": name,
                    "why": "工程转后炮塔跟上，原话“turrets are actually contributing”。",
                    "how_to_get": "商店见即买"}
        raise AssertionError(f"unknown kind {kind}")

    pri = m.run_step07_loop(workdir, sents, grouping, ratings, weapons, phases,
                            agent_fn=fake_agent, force=True)
    assert [u["name"] for u in pri["upgrades"]] == ["Ranged Damage"]
    assert [s["name"] for s in pri["shop"]] == ["Turret"]
    # 自洽: priorities N==selection N, quotes==selection, quote_details 平行
    sel = json.loads((workdir / "steps" / "07-priorities" / "selection.json").read_text(encoding="utf-8"))
    assert len(sel["upgrades"]) == len(pri["upgrades"]) == 1
    assert len(sel["shop"]) == len(pri["shop"]) == 1
    for u in pri["upgrades"] + pri["shop"]:
        assert u["kind"] in ("upgrade", "shop")
        assert len(u["why"]) >= 8 and len(u["how_to_get"]) >= 2
        assert len(u["quotes"]) >= 1 and len(u["quote_details"]) == len(u["quotes"])
        assert u["quote_details"][0]["t"] in (67, 90, 1140, 120, 1953, 300)
        for old in ("count", "analysis", "verified", "verb"):
            assert old not in u, f"retired field {old} must be absent"
    # per_item 落盘 (00/01, upgrades 先 shop 后)
    assert (workdir / "steps" / "07-priorities" / "per_item" / "00.json").exists()
    assert (workdir / "steps" / "07-priorities" / "per_item" / "01.json").exists()
    w0 = json.loads((workdir / "steps" / "07-priorities" / "per_item" / "00.json").read_text(encoding="utf-8"))
    assert w0["name"] == "Ranged Damage" and "原话" in w0["why"]
    # fewshot 快照逐字节一致
    snap = (workdir / "steps" / "07-priorities" / "fewshot.md").read_text(encoding="utf-8")
    assert snap == (REPO / "prompts" / "step07-priorities-fewshot.md").read_text(encoding="utf-8")
    # 旧 ranking.json 已清 (新链只认 selection.json)
    assert not (workdir / "steps" / "07-priorities" / "ranking.json").exists()


def test_loop_sweeps_stale_files_when_N_shrinks(tmp_path):
    m = _load("step07_loop", "scripts/step07_loop.py")
    sents = _sentences()
    workdir = tmp_path / "cyborg" / "ultimate"
    outdir = workdir / "steps" / "07-priorities"
    (outdir / "per_item").mkdir(parents=True, exist_ok=True)
    (workdir / "outputs").mkdir(parents=True, exist_ok=True)
    # 上一轮 N=3 的残留: 02 号 per 文件 + wording log
    (outdir / "per_item" / "02.json").write_text("{}", encoding="utf-8")
    (outdir / "agent-wording-02.log").write_text("x", encoding="utf-8")
    (outdir / "agent-wording-02.log.jsonl").write_text("x", encoding="utf-8")
    grouping, ratings, weapons, phases = _grouping(), _ratings(), _weapons(), _phases()

    def fake_agent(kind, name, prompt):
        if kind == "selection":
            return {"upgrades": [{"name": "Ranged Damage", "quotes": [sents[0]["text"]]}],
"shop": [{"name": "Turret", "quotes": [sents[2]["text"]]}],
                    "synthesis": {"tradeoff": "覆盖Ranged Damage、Turret",
                                  "rhythm": "覆盖Ranged Damage、Turret",
                                  "exceptions": "覆盖Ranged Damage、Turret"}}
        if kind == "wording":
            return {"name": name,
                    "why": "人话一句带短引，原话“triple the normal rate”。" if name == "Ranged Damage"
                           else "人话一句带短引，原话“turrets are actually contributing”。",
                    "how_to_get": "见即拿"}
        raise AssertionError(f"unknown kind {kind}")

    pri = m.run_step07_loop(workdir, sents, grouping, ratings, weapons, phases,
                            agent_fn=fake_agent, force=True)
    assert len(pri["upgrades"]) + len(pri["shop"]) == 2
    assert (outdir / "per_item" / "00.json").exists()
    assert (outdir / "per_item" / "01.json").exists()
    assert not (outdir / "per_item" / "02.json").exists(), "超编 per_item 残留须清掉"
    assert not (outdir / "agent-wording-02.log").exists()
    assert not (outdir / "agent-wording-02.log.jsonl").exists()


def test_run_segment2_step07_uses_new_loop_not_gaps():
    import inspect
    m = _load("run_segment2", "scripts/run_segment2.py")
    assert hasattr(m, "step07")
    src = inspect.getsource(m.step07)
    assert "from step07_loop" in src or "scripts/step07_loop" in src, "step07 must delegate to step07_loop (#65)"
    for banned in ("gaps=", "最大断层", "_REJECT", "通用顺延", "sa[:3]", "断层切分",
                   "registry-slice", "02-verbs"):
        assert banned not in src, f"step07 must retire gap/refusal/slice code rules ({banned})"


def test_check_segment2_07_new_caliber_no_gap_no_refusal():
    import inspect
    m = _load("check_segment2", "scripts/check_segment2.py")
    full = inspect.getsource(m)
    s = full.find("# --- 07-priorities")
    assert s > 0, "check_segment2 must have 07 section"
    src = full[s:s + 25000]
    assert "selection.json" in src, "check_07 must认新selection"
    assert "per_item" in src, "check_07 must验per_item"
    assert "fewshot" in src, "check_07 must验fewshot快照"
    assert "ban" in src.lower(), "check_07 must验ban scope"
    assert "T1" in src or "t1" in src.lower(), "check_07 must验shop∩T1"
    for banned in ("最大断层", "gaps=", "_REJECT", "通用顺延", "断层 TopN"):
        assert banned not in src, f"check_07 must retire gap/refusal checks ({banned})"


def test_context_priorities_points_to_fewshot():
    txt = (REPO / "CONTEXT.md").read_text(encoding="utf-8")
    assert "step07-priorities-fewshot" in txt, "CONTEXT priorities段须以fewshot文件为准 (#65)"
    lines = txt.splitlines()
    psec = "\n".join([ln for ln in lines if ("priorities.json" in ln or "07-priorities" in ln)])
    for banned in ("最大断层", "拒绝动词", "拿取系动词"):
        assert banned not in psec, f"CONTEXT must retire old 07口径 ({banned})"


def test_audit_07_shows_nodes_not_gaps():
    html = (REPO / "templates" / "audit.html").read_text(encoding="utf-8")
    assert "audit-07-priorities" in html
    for marker in ("selection", "wording", "selection.json", "priorities.json", "fewshot", "per_item",
                   "S selection", "W wording/"):
        assert marker.lower() in html.lower(), f"audit 07节须按调用列节点 ({marker})"
    # 新口径：来源 selection + wording；描述禁断层/禁动词表/禁verified字样
    import re as _re
    seg = _re.search(r'id="audit-07-priorities".*?(?=<div class="pipeline-step)', html, _re.DOTALL)
    seg07 = seg.group(0) if seg else ""
    assert "selection" in seg07.lower() and "wording" in seg07.lower()
    assert "断层" not in seg07, "audit 07节须清掉断层字样 (#65)"
    assert "拒绝动词" not in seg07 and "动词表" not in seg07, "audit 07节须清掉动词表字样 (#65)"
    # badge-verified 是全站徽标类名, 不算口径残留; 只查 verified 门/信号等口径字样
    _no_badge = seg07.lower().replace("badge-verified", "")
    assert "verified" not in _no_badge, "audit 07节须清掉verified字样 (#65)"
    # 审计节点公约：07节无过程描述、无加工视图，只留S/W节点
    for banned in ("升级卡片", "商店卡片", " fancy ", "继承自"):
        assert banned not in seg07, f"audit 07节须无加工视图 ({banned})"
