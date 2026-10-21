"""#64 two-agent loop for 08: frozen fewshot + discovery/wording.

Seams (deterministic-first, no LLM in tests):
- prompt building: fewshot + full sentences + one-pit/ban, no warning-marker/N-cap/anchor logic in code
- discovery validation: pits array (N不定可空)/title non-empty/seeds>=1 verbatim/extra verbatim/disjoint/global non-overlap/ban scope
- wording validation: title/severity/why/how/reason/seeds/extra, severity fatal|risky|trap only, ban scope, extra disjoint
- merge: wordings N==candidates N/phase aligned/quotes==seeds+extra/quote_details backfill
- retired: warning-marker substring recall/N>=3/anchors/inferred/take-closed-verbs/window rules must be absent
- fail loud on missing/fabricated/ban-in-pit/extra-overlap (no fallback)
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
        {"id": 141, "text": "I've also put myself in an awkward position in this wave cuz I I went to the left of the map, uh, which is where the projectiles were spawning from.",
         "start": "00:10:59.120", "end": "00:11:09.910", "start_s": 659.12, "end_s": 669.91, "t": 659},
        {"id": 142, "text": "If I had fled to the right of the map when I went to the engineering phase, I'd have taken less damage from projectiles spawning on top of me.",
         "start": "00:11:07.760", "end": "00:11:19.430", "start_s": 667.76, "end_s": 679.43, "t": 667},
        {"id": 300, "text": "I do not want to let a bunch of mini bosses spawn because this is a peacock wave, so enemies are doing 30% more damage than normal.",
         "start": "00:23:31.600", "end": "00:23:42.390", "start_s": 1411.6, "end_s": 1422.39, "t": 1411},
        {"id": 402, "text": "The peacock and bean teacher let us hit level 27 which was pretty awesome.",
         "start": "00:32:28.559", "end": "00:32:36.230", "start_s": 1948.559, "end_s": 1956.23, "t": 1948},
        {"id": 235, "text": "But now we also have some turrets cuz we have significantly increased tree spawns.",
         "start": "00:00:00.000", "end": "00:00:05.000", "start_s": 0.0, "end_s": 5.0, "t": 0},
        {"id": 342, "text": "I walked into every single projectile there for no reason at all.",
         "start": "00:27:08.080", "end": "00:27:13.110", "start_s": 1628.08, "end_s": 1633.11, "t": 1628},
    ]


def test_step08_loop_module_exists():
    p = REPO / "scripts" / "step08_loop.py"
    assert p.exists(), "scripts/step08_loop.py must exist (#64 discovery/wording)"


def test_fewshot_frozen_20_shot_exists():
    p = REPO / "prompts" / "step08-pitfalls-fewshot.md"
    assert p.exists(), "prompts/step08-pitfalls-fewshot.md must exist (#64 FROZEN 20-shot)"
    txt = p.read_text(encoding="utf-8")
    assert "FROZEN" in txt
    for needle in ("TASK_DISCOVERY", "TASK_WORDING", "发现", "分级",
                   "take", "ban", "N 不定", "空数组",
                   "fatal", "risky", "trap", "看着赚"):
        assert needle in txt, f"step08 fewshot must contain {needle}"
    # 发现8 + 分级8 + 负例4 = 20 例标记
    assert txt.count("DIS-") >= 8, "fewshot must have >=8 discovery examples"
    assert txt.count("LVL-") >= 8, "fewshot must have >=8 grading examples"
    assert txt.count("NEG-") >= 4, "fewshot must have >=4 negative examples"
    # 负例4: take当坑/无seed硬塞/跨事件硬并/整句复制当why
    assert "take" in txt.lower() and "NEG-" in txt


def test_prompt_build_contains_fewshot_sentences_only():
    m = _load("step08_loop", "scripts/step08_loop.py")
    fewshot = (REPO / "prompts" / "step08-pitfalls-fewshot.md").read_text(encoding="utf-8")
    sents = _sentences()
    disc = m.build_discovery_prompt(sents, fewshot)
    assert "I've also put myself in an awkward position" in disc
    assert "TASK_DISCOVERY" in disc
    assert "N 不定" in disc or "空数组" in disc
    pit = {"title": "站位吃弹", "seeds": [sents[0]["text"]], "extra": [sents[1]["text"]]}
    w = m.build_wording_prompt(pit, sents, fewshot_text=fewshot)
    assert "TASK_WORDING" in w or "TASK_PIT" in w
    assert "站位吃弹" in w
    assert "I've also put myself in an awkward position" in w
    # 语义零进代码：构建器不得注入退役规则
    import inspect
    for fn_name in ("build_discovery_prompt", "build_wording_prompt"):
        src = inspect.getsource(getattr(m, fn_name))
        for banned in ("MARKER_SIGNALS", "make sure", "don't", "can't",
                       "N>=3", "anchors", "inferred", "拿取动词", "闭集动词"):
            assert banned not in src, f"{fn_name} must not encode retired rules ({banned})"


def test_validate_discovery_ok_and_fail_loud():
    m = _load("step08_loop", "scripts/step08_loop.py")
    sents = _sentences()
    good = {"pits": [
        {"title": "站位吃弹", "seeds": [sents[0]["text"]], "extra": [sents[1]["text"]]},
        {"title": "孔雀产怪", "seeds": [sents[2]["text"]], "extra": [sents[3]["text"]]},
    ]}
    out = m.validate_discovery(good, sents)
    assert [p["title"] for p in out["pits"]] == ["站位吃弹", "孔雀产怪"]
    # 空数组诚实交允许 (N不定，无事件空数组)
    out = m.validate_discovery({"pits": []}, sents)
    assert out == {"pits": []}
    # 空证据即fail (每坑seeds>=1)
    with pytest.raises(SystemExit):
        m.validate_discovery({"pits": [
            {"title": "空坑", "seeds": [], "extra": []}]}, sents)
    # 编quote即fail
    with pytest.raises(SystemExit):
        m.validate_discovery({"pits": [
            {"title": "编坑", "seeds": ["我编的一句"], "extra": []}]}, sents)
    # extra交叠即fail (seeds/extra不交)
    with pytest.raises(SystemExit):
        m.validate_discovery({"pits": [
            {"title": "交叠坑", "seeds": [sents[0]["text"]], "extra": [sents[0]["text"]]}]}, sents)
    # 桶间重叠即fail (一句只进一坑)
    with pytest.raises(SystemExit):
        m.validate_discovery({"pits": [
            {"title": "A", "seeds": [sents[0]["text"]], "extra": []},
            {"title": "B", "seeds": [sents[0]["text"]], "extra": []}]}, sents)
    # 退役字段出现即fail
    for old in ("anchors", "inferred", "signals", "count", "severity", "kind", "anchor", "quote"):
        bad = {"pits": [{"title": "A", "seeds": [sents[0]["text"]], "extra": [], old: "x"}]}
        with pytest.raises(SystemExit):
            m.validate_discovery(bad, sents)


def test_validate_wording_ok_and_fail_loud():
    m = _load("step08_loop", "scripts/step08_loop.py")
    sents = _sentences()
    pit = {"title": "站位吃弹", "seeds": [sents[0]["text"]], "extra": []}
    good = {
        "title": "站位吃弹",
        "severity": "risky",
        "why": "站错弹幕出生点白吃伤害，人话一句。",
        "how_to_avoid": "进工程相位往弹幕反侧站位，人话一句。",
        "reason": "同属同一站位事件，故合成一条。",
        "seeds": [sents[0]["text"]],
        "extra": [sents[1]["text"]],
    }
    out = m.validate_wording(good, pit, sents)
    assert out["severity"] == "risky"
    # severity非法即fail (三档保留，码只验合法值)
    bad = dict(good)
    bad["severity"] = "medium"
    with pytest.raises(SystemExit):
        m.validate_wording(bad, pit, sents)
    # 空证据即fail
    bad = dict(good)
    bad["seeds"] = []
    with pytest.raises(SystemExit):
        m.validate_wording(bad, pit, sents)
    # extra交叠即fail
    bad = dict(good)
    bad["seeds"] = [sents[0]["text"]]
    bad["extra"] = [sents[0]["text"]]
    with pytest.raises(SystemExit):
        m.validate_wording(bad, pit, sents)
    # 编quote即fail
    bad = dict(good)
    bad["seeds"] = ["我编的一句"]
    with pytest.raises(SystemExit):
        m.validate_wording(bad, pit, sents)
    # ban名进坑即fail (scope约束)
    bad = dict(good)
    bad["seeds"] = [sents[0]["text"]]
    bad["extra"] = []
    with pytest.raises(SystemExit):
        m.validate_wording(bad, pit, sents, ban_names=["projectiles"])
    # 退役字段出现即fail
    for old in ("anchors", "inferred", "kind", "anchor", "quote", "signals"):
        bad = dict(good)
        bad[old] = "x"
        with pytest.raises(SystemExit):
            m.validate_wording(bad, pit, sents)


def test_run_loop_with_fake_agents_cyborg_shape(tmp_path):
    m = _load("step08_loop", "scripts/step08_loop.py")
    sents = _sentences()
    workdir = tmp_path / "cyborg" / "ultimate"
    (workdir / "steps" / "08-pitfalls" / "per_pitfall").mkdir(parents=True, exist_ok=True)
    (workdir / "outputs").mkdir(parents=True, exist_ok=True)
    grouping = [
        {"name_en": "Boxing Glove", "group": "ban", "quotes": [sents[4]["text"]]},
        {"name_en": "Turret", "group": "must_take", "quotes": [sents[0]["text"]]},
    ]
    s1, s2, s3, s4 = sents[0]["text"], sents[1]["text"], sents[2]["text"], sents[3]["text"]

    def fake_agent(kind, name, prompt):
        assert "FROZEN" in prompt or len(prompt) > 100
        if kind == "discovery":
            assert "TASK_DISCOVERY" in prompt
            assert "I've also put myself in an awkward position" in prompt
            return {"pits": [
                {"title": "站位吃弹", "seeds": [s1], "extra": [s2]},
                {"title": "孔雀产怪", "seeds": [s3], "extra": [s4]},
            ]}
        if kind == "wording":
            assert name in ("站位吃弹", "孔雀产怪")
            if name == "站位吃弹":
                return {"title": name, "severity": "risky",
                        "why": "站错弹幕出生点白吃伤害，人话一句。",
                        "how_to_avoid": "进工程相位往反侧站位，人话一句。",
                        "reason": "同属站位事件，故合成一条。",
                        "seeds": [s1], "extra": [s2]}
            return {"title": name, "severity": "trap",
                    "why": "看着赚回本实则增伤先死，人话一句。",
                    "how_to_avoid": "孔雀波清孵化怪，人话一句。",
                    "reason": "trap看着赚在level 27升级血赚，实则30%增伤会崩。",
                    "seeds": [s3], "extra": [s4]}
        raise AssertionError(f"unknown kind {kind}")

    pitfalls = m.run_step08_loop(workdir, sents, grouping=grouping, agent_fn=fake_agent, force=True)
    assert len(pitfalls) == 2
    assert [p["title"] for p in pitfalls] == ["站位吃弹", "孔雀产怪"]
    # 自洽: wordings N==candidates N
    cands = json.loads((workdir / "steps" / "08-pitfalls" / "candidates.json").read_text(encoding="utf-8"))
    words = json.loads((workdir / "steps" / "08-pitfalls" / "wordings.json").read_text(encoding="utf-8"))
    assert len(cands) == len(words) == len(pitfalls) == 2
    # quotes==seeds+extra原序 + quote_details平行
    for p in pitfalls:
        assert p["quotes"] == p["seeds"] + p["extra"]
        assert len(p["quote_details"]) == len(p["quotes"])
        assert p["quote_details"][0]["t"] in (659, 667, 1411, 1948)
        for old in ("anchors", "inferred", "kind", "anchor", "quote", "signals"):
            assert old not in p, f"retired field {old} must be absent"
        assert p["severity"] in ("fatal", "risky", "trap")
    # per_pitfall落盘
    assert (workdir / "steps" / "08-pitfalls" / "per_pitfall" / "00.json").exists()
    assert (workdir / "steps" / "08-pitfalls" / "per_pitfall" / "01.json").exists()
    assert (workdir / "steps" / "08-pitfalls" / "discovery.json").exists()
    # fewshot快照逐字节一致
    snap = (workdir / "steps" / "08-pitfalls" / "fewshot.md").read_text(encoding="utf-8")
    assert snap == (REPO / "prompts" / "step08-pitfalls-fewshot.md").read_text(encoding="utf-8")


def test_loop_sweeps_stale_files_when_N_shrinks(tmp_path):
    m = _load("step08_loop", "scripts/step08_loop.py")
    sents = _sentences()
    workdir = tmp_path / "cyborg" / "ultimate"
    outdir = workdir / "steps" / "08-pitfalls"
    (outdir / "per_pitfall").mkdir(parents=True, exist_ok=True)
    (workdir / "outputs").mkdir(parents=True, exist_ok=True)
    # 上一轮 N=5 的残留：第 04 号 per 文件 + wording log
    (outdir / "per_pitfall" / "04.json").write_text("{}", encoding="utf-8")
    (outdir / "agent-wording-04.log").write_text("x", encoding="utf-8")
    (outdir / "agent-wording-04.log.jsonl").write_text("x", encoding="utf-8")
    s1 = sents[0]["text"]

    def fake_agent(kind, name, prompt):
        if kind == "discovery":
            return {"pits": [{"title": "站位吃弹", "seeds": [s1], "extra": []}]}
        if kind == "wording":
            return {"title": name, "severity": "risky",
                    "why": "站错弹幕出生点白吃伤害，人话一句。",
                    "how_to_avoid": "进工程相位往反侧站位，人话一句。",
                    "reason": "单坑自成一条，无扩展跟走。",
                    "seeds": [s1], "extra": []}
        raise AssertionError(f"unknown kind {kind}")

    pitfalls = m.run_step08_loop(workdir, sents, grouping=[], agent_fn=fake_agent, force=True)
    assert len(pitfalls) == 1
    assert (outdir / "per_pitfall" / "00.json").exists()
    assert not (outdir / "per_pitfall" / "04.json").exists(), "超编 per_pitfall 残留须清掉"
    assert not (outdir / "agent-wording-04.log").exists()
    assert not (outdir / "agent-wording-04.log.jsonl").exists()


def test_run_segment2_step08_uses_loop_not_markers():
    import inspect
    m = _load("run_segment2", "scripts/run_segment2.py")
    assert hasattr(m, "step08")
    src = inspect.getsource(m.step08)
    assert "step08_loop" in src or "run_step08_loop" in src, "step08 must delegate to step08_loop (#64)"
    full = inspect.getsource(m)
    for banned in ("MARKER_SIGNALS", "_MODAL_SIGNALS", "_recall_08", "_load_wordings_08",
                   "pure warnings", "警告标记产种子池"):
        assert banned not in full, f"step08 must retire marker recall ({banned})"


def test_check_segment2_08_new_caliber_no_anchors_n3():
    import inspect
    m = _load("check_segment2", "scripts/check_segment2.py")
    full = inspect.getsource(m)
    s = full.find("# --- 08-pitfalls")
    assert s > 0, "check_segment2 must have 08 section"
    src = full[s:s + 25000]
    assert "candidates" in src, "check_08 must认新candidates"
    assert "wordings" in src, "check_08 must验wordings N==candidates"
    assert "per_pitfall" in src, "check_08 must验per_pitfall"
    assert "fewshot" in src, "check_08 must验fewshot快照"
    assert "ban" in src.lower(), "check_08 must验ban scope"
    for banned in ("must be >=3", "kind must be anchor/discretion",
                   "non-empty signals", "种子池"):
        assert banned not in src, f"check_08 must retire old caliber ({banned})"


def test_context_pitfalls_points_to_fewshot():
    txt = (REPO / "CONTEXT.md").read_text(encoding="utf-8")
    assert "step08-pitfalls-fewshot" in txt, "CONTEXT pitfalls段须以fewshot文件为准 (#64)"
    lines = txt.splitlines()
    psec = "\n".join([ln for ln in lines if ("pitfalls.json" in ln or "08-pitfalls" in ln)])
    for banned in ("纯警告标记产种子池", "inferred=false", "inferred=true", "anchors每条"):
        assert banned not in psec, f"CONTEXT must retire old 08口径 ({banned})"


def test_audit_08_shows_nodes_not_markers():
    html = (REPO / "templates" / "audit.html").read_text(encoding="utf-8")
    assert "audit-08-pitfalls" in html
    for marker in ("discovery", "wording", "candidates.json", "wordings.json", "fewshot", "per_pitfall", "W wording/"):
        assert marker.lower() in html.lower(), f"audit 08节须按调用列节点 ({marker})"
    # 新口径：来源 discovery + wording；描述禁警告标记/禁N≥3/禁锚字样
    import re as _re
    seg = _re.search(r'id="audit-08-pitfalls".*?(?=<div class="pipeline-step)', html, _re.DOTALL)
    seg08 = seg.group(0) if seg else ""
    assert "discovery" in seg08.lower() and "wording" in seg08.lower()
    assert "警告标记" not in seg08, "audit 08节须清掉警告标记字样 (#64)"
    assert "N>=3" not in seg08 and ">=3" not in seg08, "audit 08节须清掉N>=3字样 (#64)"
    # 审计节点公约：08节无过程描述、无加工视图（漏斗/卡片/成因摘要已删，只留D/W节点）
    for banned in ("发现漏斗", "种子漏斗", "找坑漏斗", "成因", "pitfallsSectionHtml", "recallPanelHtml"):
        assert banned not in seg08, f"audit 08节须无加工视图 ({banned})"
