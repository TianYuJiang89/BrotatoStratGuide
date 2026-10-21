"""#63 two-agent loop for 06: frozen fewshot + segmentation/wording.

Seams (deterministic-first, no LLM in tests):
- prompt building: fewshot + full sentences + one-bucket (wording), no chapters/time-window/N-cap logic in code
- segmentation validation: buckets non-empty/quotes verbatim/no-overlap/waves evidenced/phase unique
- wording validation: phase aligned/goal-focus-pivot>=8/not-whole-copy/short verbatim/extra true-outside-bucket
- merge: wordings N==buckets N/phase aligned/bucket prefix==buckets/out_of_window flag
- retired: meta chapters input/window lock/N cap/code bucketing must be absent from loop
- fail loud on missing/fabricated quote/fabricated waves (no fallback)
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
        {"id": 1, "text": "So for the first half of the wave, you're a very powerful ranged attacker.",
         "start": "00:00:10.000", "end": "00:00:15.000", "start_s": 10.0, "end_s": 15.0, "t": 10},
        {"id": 2, "text": "We need to kill elites really quickly before our damage swaps over.",
         "start": "00:01:47.920", "end": "00:01:52.000", "start_s": 107.92, "end_s": 112.0, "t": 107},
        {"id": 3, "text": "So, given that we're going into the horde wave, I'm going to take the nuke launcher.",
         "start": "00:13:36.399", "end": "00:13:42.000", "start_s": 816.399, "end_s": 822.0, "t": 816},
        {"id": 4, "text": "Obviously, we're taking the nuke launcher for the horde wave because it's much better.",
         "start": "00:14:07.360", "end": "00:14:12.000", "start_s": 847.36, "end_s": 852.0, "t": 847},
        {"id": 5, "text": "I can't take a scarf going into a horde wave.",
         "start": "00:18:14.080", "end": "00:18:18.000", "start_s": 1094.08, "end_s": 1098.0, "t": 1094},
        {"id": 6, "text": "And then we'll we'll go to wave 20.",
         "start": "00:30:26.000", "end": "00:30:30.000", "start_s": 1826.0, "end_s": 1830.0, "t": 1826},
    ]


def test_step06_loop_module_exists():
    p = REPO / "scripts" / "step06_loop.py"
    assert p.exists(), "scripts/step06_loop.py must exist (#63 segmentation/wording)"


def test_fewshot_frozen_20_shot_exists():
    p = REPO / "prompts" / "step06-phases-fewshot.md"
    assert p.exists(), "prompts/step06-phases-fewshot.md must exist (#63 FROZEN 20-shot)"
    txt = p.read_text(encoding="utf-8")
    assert "FROZEN" in txt
    for needle in ("TASK_SEGMENTATION", "TASK_WORDING", "切分", "三问",
                   "只复读一条", "模具话", "编数字", "计数泄漏", "整句复制",
                   "桶间不重叠", "真桶外", "不抄"):
        assert needle in txt, f"step06 fewshot must contain {needle}"
    # 切分8 + 三问8 + 负例4 = 20 例标记
    assert txt.count("SEG-") >= 8, "fewshot must have >=8 segmentation examples"
    assert txt.count("WRD-") >= 8, "fewshot must have >=8 wording examples"
    assert txt.count("NEG-") >= 4, "fewshot must have >=4 negative examples"


def test_prompt_build_contains_fewshot_sentences_only():
    m = _load("step06_loop", "scripts/step06_loop.py")
    fewshot = (REPO / "prompts" / "step06-phases-fewshot.md").read_text(encoding="utf-8")
    sents = _sentences()
    seg = m.build_segmentation_prompt(sents, fewshot)
    assert "So for the first half of the wave" in seg
    assert "TASK_SEGMENTATION" in seg
    assert "桶间不重叠" in seg
    bucket = {"phase": "horde 波转核弹清场", "waves": "horde wave",
              "quotes": [sents[2]["text"], sents[3]["text"]]}
    w = m.build_wording_prompt(bucket, sents, fewshot_text=fewshot)
    assert "TASK_WORDING" in w or "TASK_PHASE" in w
    assert "horde 波转核弹清场" in w
    assert "So, given that we're going into the horde wave" in w
    # 语义零进代码：构建器不得注入退役规则
    import inspect
    for fn_name in ("build_segmentation_prompt", "build_wording_prompt"):
        src = inspect.getsource(getattr(m, fn_name))
        for banned in ("chapters", "meta.json", "[start, end)", "末章含end",
                       "N=8", "一章一段", "最大断层", "registry-slice"):
            assert banned not in src, f"{fn_name} must not encode retired rules ({banned})"


def test_validate_segmentation_ok_and_fail_loud():
    m = _load("step06_loop", "scripts/step06_loop.py")
    sents = _sentences()
    good = {"buckets": [
        {"phase": "前期远程攒伤", "waves": "",
         "quotes": [sents[0]["text"], sents[1]["text"]]},
        {"phase": "horde 波转核弹清场", "waves": "horde wave",
         "quotes": [sents[2]["text"], sents[3]["text"]]},
    ]}
    out = m.validate_segmentation(good, sents)
    assert [b["phase"] for b in out["buckets"]] == ["前期远程攒伤", "horde 波转核弹清场"]
    # 空桶即fail (quotes≥1)
    with pytest.raises(SystemExit):
        m.validate_segmentation({"buckets": [
            {"phase": "空桶", "waves": "", "quotes": []}]}, sents)
    # 编quote即fail
    with pytest.raises(SystemExit):
        m.validate_segmentation({"buckets": [
            {"phase": "前期", "waves": "", "quotes": ["我编的一句"]}]}, sents)
    # 桶间重叠即fail
    with pytest.raises(SystemExit):
        m.validate_segmentation({"buckets": [
            {"phase": "A", "waves": "", "quotes": [sents[0]["text"]]},
            {"phase": "B", "waves": "", "quotes": [sents[0]["text"]]}]}, sents)
    # 编波次即fail (waves无原话作证)
    with pytest.raises(SystemExit):
        m.validate_segmentation({"buckets": [
            {"phase": "前期", "waves": "wave 25", "quotes": [sents[0]["text"]]}]}, sents)
    # 无证据空串允许 (纯配装转折)
    out = m.validate_segmentation({"buckets": [
        {"phase": "过渡补位", "waves": "", "quotes": [sents[0]["text"]]}]}, sents)
    assert out["buckets"][0]["waves"] == ""
    # phase重复即fail
    with pytest.raises(SystemExit):
        m.validate_segmentation({"buckets": [
            {"phase": "同名", "waves": "", "quotes": [sents[0]["text"]]},
            {"phase": "同名", "waves": "", "quotes": [sents[1]["text"]]}]}, sents)
    # N不定：单桶允许 (码不卡4-8)，空数组才fail
    out = m.validate_segmentation({"buckets": [
        {"phase": "单桶", "waves": "", "quotes": [sents[0]["text"]]}]}, sents)
    assert len(out["buckets"]) == 1
    with pytest.raises(SystemExit):
        m.validate_segmentation({"buckets": []}, sents)
    # 退役字段出现即fail
    for old in ("count", "quote_details", "goal", "chapters"):
        bad = {"buckets": [{"phase": "A", "waves": "", "quotes": [sents[0]["text"]], old: "x"}]}
        with pytest.raises(SystemExit):
            m.validate_segmentation(bad, sents)


def test_validate_wording_ok_and_fail_loud():
    m = _load("step06_loop", "scripts/step06_loop.py")
    sents = _sentences()
    bucket = {"phase": "horde 波转核弹清场", "waves": "horde wave",
              "quotes": [sents[2]["text"], sents[3]["text"]]}
    good = {
        "phase": "horde 波转核弹清场",
        "goal": "horde 波核弹清场最优解，原话“taking the nuke launcher for the horde wave”。",
        "focus": "进 horde 合核弹留 minigun 打 elite，原话“going into the horde wave”。",
        "pivot": "清完 horde 回 elite 狩猎，原话“horde wave”。",
        "extra_quotes": [sents[4]["text"]],
    }
    out = m.validate_wording(good, bucket, sents)
    assert out["phase"] == "horde 波转核弹清场"
    # phase不对即fail (自洽)
    bad = dict(good)
    bad["phase"] = "别的桶"
    with pytest.raises(SystemExit):
        m.validate_wording(bad, bucket, sents)
    # 三问太短即fail
    bad = dict(good)
    bad["goal"] = "太短"
    with pytest.raises(SystemExit):
        m.validate_wording(bad, bucket, sents)
    # 整句复制即fail (小结≠原文)
    bad = dict(good)
    bad["goal"] = sents[2]["text"]
    with pytest.raises(SystemExit):
        m.validate_wording(bad, bucket, sents)
    # 缺短引即fail
    bad = dict(good)
    bad["goal"] = "horde 波核弹清场最优解，没有引用标记。"
    with pytest.raises(SystemExit):
        m.validate_wording(bad, bucket, sents)
    # 短引改写即fail
    bad = dict(good)
    bad["goal"] = "horde 波核弹清场，原话“taking the super gun”。。"
    with pytest.raises(SystemExit):
        m.validate_wording(bad, bucket, sents)
    # extra编quote即fail
    bad = dict(good)
    bad["extra_quotes"] = ["我编的一句"]
    with pytest.raises(SystemExit):
        m.validate_wording(bad, bucket, sents)
    # extra桶内重复即fail (须真桶外)
    bad = dict(good)
    bad["extra_quotes"] = [sents[2]["text"]]
    with pytest.raises(SystemExit):
        m.validate_wording(bad, bucket, sents)
    # 空extra允许 (无则[])
    ok = dict(good)
    ok["extra_quotes"] = []
    out = m.validate_wording(ok, bucket, sents)
    assert out["extra_quotes"] == []


def test_run_loop_with_fake_agents_cyborg_shape(tmp_path):
    m = _load("step06_loop", "scripts/step06_loop.py")
    sents = _sentences()
    workdir = tmp_path / "cyborg" / "ultimate"
    (workdir / "steps" / "06-phases" / "per_phase").mkdir(parents=True, exist_ok=True)
    (workdir / "outputs").mkdir(parents=True, exist_ok=True)

    b1_quotes = [sents[0]["text"], sents[1]["text"]]
    b2_quotes = [sents[2]["text"], sents[3]["text"]]
    extra_for_b2 = sents[4]["text"]

    def fake_agent(kind, name, prompt):
        assert "FROZEN" in prompt or "fewshot" in prompt.lower() or len(prompt) > 100
        if kind == "segmentation":
            assert "TASK_SEGMENTATION" in prompt or "桶间不重叠" in prompt
            assert "So for the first half of the wave" in prompt
            return {"buckets": [
                {"phase": "前期远程攒伤", "waves": "", "quotes": b1_quotes},
                {"phase": "horde 波转核弹清场", "waves": "horde wave", "quotes": b2_quotes},
            ]}
        if kind == "wording":
            assert name in ("前期远程攒伤", "horde 波转核弹清场")
            if name == "前期远程攒伤":
                return {"phase": name,
                        "goal": "前半波远程爆发 elite 转前秒掉，原话“kill elites really quickly”。",
                        "focus": "补远程保速杀，原话“ranged attacker”。",
                        "pivot": "攒伤不断档，原话“damage swaps over”。",
                        "extra_quotes": []}
            return {"phase": name,
                    "goal": "horde 波核弹清场最优解，原话“taking the nuke launcher for the horde wave”。",
                    "focus": "进 horde 合核弹，原话“going into the horde wave”。",
                    "pivot": "清完回 elite，原话“horde wave”。",
                    "extra_quotes": [extra_for_b2]}
        raise AssertionError(f"unknown kind {kind}")

    phases = m.run_step06_loop(workdir, sents, agent_fn=fake_agent, force=True)
    assert len(phases) == 2
    assert [p["phase"] for p in phases] == ["前期远程攒伤", "horde 波转核弹清场"]
    # 桶内前缀须等于 buckets
    buckets = json.loads((workdir / "steps" / "06-phases" / "buckets.json").read_text(encoding="utf-8"))
    assert len(buckets) == 2
    assert buckets[0]["quotes"] == b1_quotes
    assert buckets[1]["quotes"] == b2_quotes
    for b in buckets:
        assert len(b["quote_details"]) == len(b["quotes"])
        assert b["quote_details"][0]["t"] in (10, 107, 816, 847)
    # wordings N==buckets N, phase 对齐
    wordings = json.loads((workdir / "steps" / "06-phases" / "wordings.json").read_text(encoding="utf-8"))
    assert len(wordings) == 2
    assert [w["phase"] for w in wordings] == ["前期远程攒伤", "horde 波转核弹清场"]
    for w in wordings:
        for k in ("phase", "goal", "focus", "pivot", "extra_quotes"):
            assert k in w
        for retired in ("count", "quotes", "quote_details", "waves"):
            assert retired not in w
    # phases 合并：桶内前缀 + 桶外补标 out_of_window
    assert phases[0]["quotes"] == b1_quotes
    assert phases[1]["quotes"] == b2_quotes + [extra_for_b2]
    assert len(phases[1]["quote_details"]) == 3
    assert phases[1]["quote_details"][-1].get("out_of_window") is True
    assert phases[0]["quote_details"][0].get("out_of_window") is not True
    # 小结≠原文
    for p in phases:
        for k in ("goal", "focus", "pivot"):
            assert p[k] not in [s["text"] for s in sents]
    # fewshot 快照逐字节一致
    snap = (workdir / "steps" / "06-phases" / "fewshot.md").read_text(encoding="utf-8")
    assert snap == (REPO / "prompts" / "step06-phases-fewshot.md").read_text(encoding="utf-8")
    # per_phase 落盘
    import re
    for ph in ("前期远程攒伤", "horde 波转核弹清场"):
        safe = re.sub(r"[^A-Za-z0-9]+", "_", ph).strip("_") or "phase"
        assert (workdir / "steps" / "06-phases" / "per_phase" / f"{safe}.json").exists() or \
               len(list((workdir / "steps" / "06-phases" / "per_phase").glob("*.json"))) == 2


def test_run_segment2_step06_uses_loop_not_code_buckets():
    import inspect
    m = _load("run_segment2", "scripts/run_segment2.py")
    assert hasattr(m, "step06")
    src = inspect.getsource(m.step06)
    assert "step06_loop" in src or "run_step06_loop" in src, "step06 must delegate to step06_loop (#63)"
    for banned in ('_bucket_by_chapter', '_load_chapters', '末章含end', '落窗', 'N=章节数'):
        assert banned not in src, f"step06 must retire code bucketing ({banned})"


def test_check_segment2_06_new_caliber_no_chapters_window():
    import inspect
    m = _load("check_segment2", "scripts/check_segment2.py")
    full = inspect.getsource(m)
    s = full.find("# --- 06-phases")
    assert s > 0, "check_segment2 must have 06 section"
    src = full[s:s + 15000]
    assert "buckets.json" in src, "check_06 must认新buckets"
    assert "wordings.json" in src or "wordings" in src
    assert "per_phase" in src or "per-phase" in src or "fewshot" in src
    assert "out_of_window" in src
    for banned in ("N=8", "一章一段", "章标题原文", "末章含end", "左闭右开",
                   "chapters timed", "meta.json chapters"):
        assert banned not in src, f"check_06 must retire chapter/window caliber ({banned})"


def test_context_phases_points_to_fewshot():
    txt = (REPO / "CONTEXT.md").read_text(encoding="utf-8")
    assert "step06-phases-fewshot" in txt, "CONTEXT phases段须以fewshot文件为准 (#63)"
    lines = txt.splitlines()
    psec = "\n".join([ln for ln in lines if ("phases.json" in ln or "06-phases" in ln)])
    for banned in ("一章一段", "章标题原文", "[start,end)", "末章含end", "作者 chapters"):
        assert banned not in psec, f"CONTEXT must retire old 06口径 ({banned})"


def test_audit_06_shows_nodes_not_chapters():
    html = (REPO / "templates" / "audit.html").read_text(encoding="utf-8")
    assert "audit-06-phases" in html
    # 审计节点：segmentation + wording 按调用列节点
    for marker in ("segmentation", "wording", "buckets.json", "fewshot"):
        assert marker.lower() in html.lower(), f"audit 06节须按调用列节点 ({marker})"
    # 新口径：来源 segmentation + wording；禁chapter/禁窗字样（06节内清掉）
    import re as _re
    # 找到 06 节块 (pipeline-step audit-06-phases 到下一个 pipeline-step)
    m = _re.search(r'id="audit-06-phases".*?(?=<div class="pipeline-step)', html, _re.DOTALL)
    seg06 = m.group(0) if m else ""
    assert "chapter" not in seg06.lower(), "audit 06节须清掉 chapter 字样 (#63)"
    assert "窗" not in seg06, "audit 06节须清掉 窗 字样 (#63)"
