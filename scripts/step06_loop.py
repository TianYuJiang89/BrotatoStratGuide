#!/usr/bin/env python3
"""Step06 agent loop (#63): frozen fewshot + segmentation/wording.

Deterministic-first:
- 固定代码只做: prompt 组装 (任务手册 + 全量整句 + 一桶) / 输出形状校验 /
  quotes 逐字 (sentences lookup, 不信 agent) / 去重 / 桶间不重叠 /
  quote_details 重建 (t/start/end/context 由 sentences lookup) /
  小结≠原文 (goal/focus/pivot 不得整句复制) / 落盘
  (buckets.json + wordings.json + per_phase/* + phases.json + 日志).
- agent judgment 只做: segmentation 自定义波次 (phase 运营语言不抄章题 +
  waves 原话作证 + quotes≥1, N 不定, 粒度归它) / wording×N 单桶三问
  (goal/focus/pivot 人话+短引 + extra_quotes 真桶外, 可推翻? 不推翻切分,
  只写三问).
- 缺件/编 quote/编波次即 fail loud, 不回落不补空.

输入:
- fewshot: prompts/step06-phases-fewshot.md (FROZEN 20-shot: 切分8+三问8+负例4)
- sentences: steps/01-sentences/sentences.json ([{id,text[,start,end],start_s,end_s,t}])

输出:
- steps/06-phases/segmentation.json: agent 原始 {"buckets": [{phase,waves,quotes}]}
- steps/06-phases/buckets.json: [{phase,waves,quotes,quote_details}] (code 回填)
- steps/06-phases/per_phase/<Safe>.json: wording 原始 (validated)
- steps/06-phases/wordings.json: [{phase,goal,focus,pivot,extra_quotes}]
- steps/06-phases/phases.json (+ outputs/phases.json):
  [{phase,waves,goal,focus,pivot,quotes,quote_details}] (code 合并: 桶内前缀须等于 buckets, 桶外补标 out_of_window:true)
  - wordings.json schema 不变 (phase/goal/focus/pivot/extra_quotes).
"""

from __future__ import annotations

import concurrent.futures
import hashlib
import json
import re
import subprocess
import sys
import time
from collections import defaultdict
from pathlib import Path
from typing import NoReturn

REPO = Path(__file__).resolve().parent.parent

FEWSHOT_REL = "prompts/step06-phases-fewshot.md"
# segmentation 输出退役字段 (只活 phase/waves/quotes; count/details/三问/章题时间窗全退役)
RETIRED_SEG_FIELDS = ("count", "quote_details", "goal", "focus", "pivot",
                      "extra_quotes", "chapters", "start", "end", "tier",
                      "confidence", "kind", "inferred", "anchors", "score", "reason")
RETIRED_WORDING_FIELDS = ("count", "quotes", "quote_details", "tier", "confidence",
                          "kind", "inferred", "anchors", "score", "reason", "waves",
                          "buckets", "chapters")
NOTE_SHORT_RE = re.compile(r'原话["“]([^"”]+)["”]')


def _fail(msg: str) -> NoReturn:
    raise SystemExit(f"step06-loop FAIL: {msg}")


def _note_shorts(text: str) -> list[str]:
    return [s.strip() for s in NOTE_SHORT_RE.findall(text or "") if s.strip()]


def load_fewshot() -> str:
    p = REPO / FEWSHOT_REL
    if not p.exists():
        _fail(f"missing {FEWSHOT_REL} (frozen fewshot 缺件即 fail, 不回落)")
    txt = p.read_text(encoding="utf-8")
    if "FROZEN" not in txt:
        _fail(f"{FEWSHOT_REL} 缺 FROZEN 头 (freeze 完整性 fail)")
    return txt


def build_context(sentences: list[dict], idx: int) -> str:
    parts: list[str] = []
    if idx > 0:
        parts.append(sentences[idx - 1]["text"])
    parts.append(sentences[idx]["text"])
    if idx + 1 < len(sentences):
        parts.append(sentences[idx + 1]["text"])
    ctx = " … ".join(parts)
    if len(ctx) > 300:
        ctx = ctx[:300]
    return ctx


def _quote_lookup(sentences: list[dict]) -> dict[str, list[dict]]:
    mp: dict[str, list[dict]] = defaultdict(list)
    for i, s in enumerate(sentences):
        mp[s["text"]].append({
            "start": s.get("start"), "end": s.get("end"),
            "t": int(s["start_s"]) if s.get("start_s") is not None else None,
            "context": build_context(sentences, i),
        })
    return mp


def _sentences_blob(sentences: list[dict]) -> str:
    lines: list[str] = []
    for s in sentences:
        lines.append(json.dumps({"id": s.get("id"), "text": s.get("text", ""),
                                 "start": s.get("start"), "end": s.get("end"),
                                 "t": s.get("t")}, ensure_ascii=False))
    return "\n".join(lines)


def build_segmentation_prompt(sentences: list[dict], fewshot_text: str) -> str:
    if not isinstance(sentences, list) or not sentences:
        _fail("sentences 为空 (缺件即 fail)")
    blob = _sentences_blob(sentences)
    prompt = (
        fewshot_text
        + "\n\n## 该角色全量整句（含 start/end/t，原样全量，不截断）\n\n"
        + "```json\n" + blob + "\n```\n\n"
        + "---\n\n# TASK_SEGMENTATION（只切分，不写三问；N 由你定，桶间不重叠）\n\n"
        + "## 输出契约（只输出一件 JSON 对象，不输出其它文字）\n\n"
        + '{"buckets": [{"phase": "<运营语言，不抄作者章题>", '
        + '"waves": "<原话作证，无证据空串>", "quotes": ["逐字，去重，≥1"]}]}\n\n'
        + "- phase 运营语言互异，不抄作者章题；waves 原话作证（须为本桶 quotes 子串或波次关键词出自本桶），无证据空串不编，无波次纯配装转折允许空串。\n"
        + "- quotes 须逐字等于上表某条 text，去重，每桶 ≥1；桶间不重叠（一句只进一桶）。编 quote / 空桶 / 重叠即 fail。\n"
        + "- N 不定（演示 4-8 不进码，码不卡 N，粒度靠人抽）。你不输出 goal/focus/pivot/count。缺件即 fail，不回落不补空。\n"
    )
    return prompt


def build_wording_prompt(bucket: dict, sentences: list[dict], fewshot_text: str) -> str:
    if not isinstance(bucket, dict) or not bucket.get("phase"):
        _fail("TASK_WORDING 缺桶 (缺件即 fail)")
    if not isinstance(sentences, list) or not sentences:
        _fail("sentences 为空 (缺件即 fail)")
    blob = _sentences_blob(sentences)
    b_blob = json.dumps(bucket, ensure_ascii=False, indent=2)
    prompt = (
        fewshot_text
        + "\n\n## 该角色全量整句（含 start/end/t，原样全量，不截断）\n\n"
        + "```json\n" + blob + "\n```\n\n"
        + "## 本桶（只写这一桶的三问，其它桶一律不写）\n\n"
        + "```json\n" + b_blob + "\n```\n\n"
        + "---\n\n# TASK_WORDING（只写本桶三问，不改切分；extra 须真桶外）\n\n"
        + f"TASK_PHASE: {bucket.get('phase')}\n\n"
        + "## 输出契约（只输出一件 JSON 对象，不输出其它文字）\n\n"
        + '{"phase": "<与 TASK_PHASE 一字不差>", "goal": "≤120字人话+短引", '
        + '"focus": "≤120字人话+短引", "pivot": "≤120字人话+短引", '
        + '"extra_quotes": ["逐字，真桶外，无则[]"]}\n\n'
        + "- phase 须与 TASK_PHASE 一字不差；goal/focus/pivot 各 ≥8 字，人话综合多条+短引（短引须出自本桶 quotes 逐字，桶外引须先入 extra 才可引）；整句复制某条 quote 即 fail。\n"
        + "- extra_quotes 须逐字等于全量整句某条 text，去重，且不在本桶 quotes 内（真桶外）；与本桶重复/桶内已收判负；无则 []。编 quote 即 fail。\n"
        + "- 禁模具话/计数泄漏/编数字（原话数字须逐字，未提空出不脑补）。缺件即 fail，不回落不补空。\n"
    )
    return prompt


def _waves_evidenced(waves: str, quotes: list[str]) -> bool:
    """waves 原话作证: 空串允许 (纯配装转折); 非空须证据.

    通过条件 (任一):
    1. waves 整串为某条本桶 quotes 的子串 (case-insensitive), 或
    2. waves 内波次关键词 (wave+数字/horde/elite/boss/final/peacock/mini/whale) 全部出自本桶 quotes.
    否则视为编波次 fail.
    """
    w = (waves or "").strip()
    if not w:
        return True
    joined = " ".join(quotes).lower()
    if w.lower() in joined:
        return True
    wl = w.lower()
    # 提取 waves 内的证据关键词
    want: list[str] = []
    for m in re.finditer(r"wave\s*\d+", wl):
        want.append(m.group(0))
    for kw in ("horde", "elite", "boss", "final", "peacock", "mini", "whale", "wave"):
        if kw in wl and kw not in want:
            want.append(kw)
    if not want:
        return False
    for token in want:
        if token not in joined:
            return False
    return True


def validate_segmentation(data: dict, sentences: list[dict]) -> dict:
    if not isinstance(data, dict):
        _fail(f"segmentation 输出须为 JSON 对象, got {type(data)}")
    for f in RETIRED_SEG_FIELDS:
        if f in data:
            _fail(f"segmentation 字段 {f} 已退役 (#63, 出现即 fail)")
    if "buckets" not in data:
        _fail("segmentation 缺 buckets (缺件即 fail, 不补空)")
    buckets = data["buckets"]
    if not isinstance(buckets, list) or not buckets:
        _fail("segmentation buckets 须为非空数组 (N 不定但 ≥1, 空即 fail)")
    # N 不卡 4-8 (演示数不进码); 只保 ≥1, 粒度靠人抽
    sent_texts = {s.get("text") for s in sentences if isinstance(s, dict)}
    seen_phases: set[str] = set()
    seen_quotes: set[str] = set()
    out: list[dict] = []
    for i, b in enumerate(buckets):
        if not isinstance(b, dict):
            _fail(f"segmentation buckets[{i}] 须为对象")
        for k in ("phase", "waves", "quotes"):
            if k not in b:
                _fail(f"segmentation buckets[{i}] 缺 {k} (缺件即 fail)")
        phase = b.get("phase")
        waves = b.get("waves")
        qs = b.get("quotes")
        if not isinstance(phase, str) or not phase.strip():
            _fail(f"segmentation buckets[{i}] phase 须为非空运营语言")
        phase = phase.strip()
        if phase in seen_phases:
            _fail(f"segmentation phase 须互异 (重复): {phase!r}")
        seen_phases.add(phase)
        if not isinstance(waves, str):
            _fail(f"segmentation {phase} waves 须为字符串 (无证据空串, 不编)")
        waves = waves.strip()
        if not isinstance(qs, list) or not qs or any(not isinstance(q, str) for q in qs):
            _fail(f"segmentation {phase} quotes 须为非空字符串数组 (空桶即 fail)")
        if len(qs) != len(set(qs)):
            _fail(f"segmentation {phase} quotes 须去重")
        for q in qs:
            if q not in sent_texts:
                _fail(f"segmentation {phase} 编 quote 即 fail: {q[:60]!r} 不在整句内 (逐字)")
            if q in seen_quotes:
                _fail(f"segmentation 桶间不重叠即 fail: {q[:60]!r} 已进他桶")
        for q in qs:
            seen_quotes.add(q)
        if not _waves_evidenced(waves, [q for q in qs if isinstance(q, str)]):
            _fail(f"segmentation {phase} 编波次即 fail: waves={waves!r} 无原话作证 (须为本桶子串或关键词出自本桶, 无证据请空串)")
        # 退役字段不得出现在桶内
        for f in RETIRED_SEG_FIELDS:
            if f in b:
                _fail(f"segmentation {phase} 字段 {f} 已退役 (#63, 出现即 fail)")
        out.append({"phase": phase, "waves": waves, "quotes": list(qs)})
    return {"buckets": out}


def validate_wording(data: dict, bucket: dict, sentences: list[dict]) -> dict:
    phase_expect = (bucket or {}).get("phase")
    if not phase_expect:
        _fail("wording 缺桶 phase (缺件即 fail)")
    if not isinstance(data, dict):
        _fail(f"{phase_expect} wording 输出须为 JSON 对象, got {type(data)}")
    for f in RETIRED_WORDING_FIELDS:
        if f in data:
            _fail(f"{phase_expect} 字段 {f} 已退役 (#63, 出现即 fail)")
    for k in ("phase", "goal", "focus", "pivot", "extra_quotes"):
        if k not in data:
            _fail(f"{phase_expect} wording 缺 {k} (缺件即 fail, 不补空)")
    if data.get("phase") != phase_expect:
        _fail(f"wording phase 须一字不差: 期望 {phase_expect!r}, 实得 {data.get('phase')!r}")
    bucket_quotes = list((bucket or {}).get("quotes") or [])
    sent_texts = {s.get("text") for s in sentences if isinstance(s, dict)}
    for k in ("goal", "focus", "pivot"):
        v = data.get(k)
        if not isinstance(v, str) or len(v.strip()) < 8:
            _fail(f"{phase_expect} wording {k} 须人话一句≥8字")
        v = v.strip()
        if v in sent_texts or v in bucket_quotes:
            _fail(f"{phase_expect} wording {k} 整句复制 quote 即 fail (小结须≠原文)")
        shorts = _note_shorts(v)
        if not shorts:
            _fail(f"{phase_expect} wording {k} 缺短引标记 原话\"...\" (三问须带逐字短引, 缺件即 fail)")
        allowed = set(bucket_quotes) | set(data.get("extra_quotes") or [])
        for s in shorts:
            if not any(s in q for q in allowed if isinstance(q, str)):
                _fail(f"{phase_expect} wording {k} 短引须逐字出自本桶或 extra: {s[:60]!r} 改写/编造即 fail")
        # 长度帽 (沿 05/03: note ≤120, 三问同)
        if len(v) > 300:
            _fail(f"{phase_expect} wording {k} 过长 (须≤300), got {len(v)}")
    ex = data.get("extra_quotes")
    if not isinstance(ex, list) or any(not isinstance(q, str) for q in ex):
        _fail(f"{phase_expect} wording extra_quotes 须字符串数组 (无则[])")
    if len(ex) != len(set(ex)):
        _fail(f"{phase_expect} wording extra_quotes 须去重")
    for q in ex:
        if q not in sent_texts:
            _fail(f"{phase_expect} 编 quote 即 fail: {q[:60]!r} 不在整句内 (逐字)")
        if q in bucket_quotes:
            _fail(f"{phase_expect} extra_quotes 须真桶外: {q[:60]!r} 已在本桶内 (重复/桶内已收即 fail)")
    return {"phase": phase_expect,
            "goal": str(data.get("goal")).strip(),
            "focus": str(data.get("focus")).strip(),
            "pivot": str(data.get("pivot")).strip(),
            "extra_quotes": list(ex)}


def _extract_json(text: str, who: str) -> dict:
    t = text.strip()
    if "```" in t:
        m = re.search(r"```(?:json)?\s*(\{.*?\})\s*```", t, re.DOTALL)
        if m:
            t = m.group(1).strip()
    if not t.startswith("{"):
        i = t.find("{")
        j = t.rfind("}")
        if i >= 0 and j > i:
            t = t[i:j + 1]
    try:
        data = json.loads(t)
    except Exception as e:
        _fail(f"{who} 输出非 JSON 即 fail: {e}; head={text[:120]!r}")
        raise  # pragma: no cover
    if not isinstance(data, dict):
        _fail(f"{who} 输出须为对象")
    return data  # type: ignore[return-value]


def _spawn_agent_once(workdir: Path, prompt_text: str, output_rel: str,
                      log_path: Path, timeout: float = 1800.0,
                      model=None, thinking: str = "medium") -> Path:
    import queue
    import threading
    import shutil as _sh

    def build_agent_cmd() -> list[str]:
        base = ["--mode", "rpc", "--no-session",
                "--no-skills", "--no-extensions", "--no-prompt-templates",
                "--no-context-files", "--tools", "read,write,bash",
                "--thinking", thinking]
        if model:
            base += ["--model", model]
        found = _sh.which("pi")
        if found:
            return [found, *base]
        for cand in ("F:/Pi/CLI/pi.cmd", "F:/Pi/CLI/pi", "pi.cmd"):
            if Path(cand).exists():
                return [cand, *base]
        return ["pi", *base]

    def _sha1(s: str) -> str:
        return hashlib.sha1(s.encode("utf-8")).hexdigest()

    start_wall = time.time()
    out_path = workdir / output_rel
    cmd = build_agent_cmd()
    log_path.parent.mkdir(parents=True, exist_ok=True)
    with open(log_path, "a", encoding="utf-8") as lg:
        lg.write(f"[{time.time():.3f}] spawn cwd={workdir} cmd={' '.join(cmd)}\n")
        lg.write(f"prompt_len={len(prompt_text)} prompt_sha={_sha1(prompt_text)}\n")
    try:
        proc = subprocess.Popen(
            cmd, cwd=str(workdir), stdin=subprocess.PIPE, stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT, text=True, encoding="utf-8", errors="replace", bufsize=1)
    except Exception as e:
        raise RuntimeError(f"transient: spawn failed: {e!r}")
    q: queue.Queue[str | None] = queue.Queue()
    raw_lines: list[str] = []

    def _reader() -> None:
        try:
            assert proc.stdout is not None
            for line in proc.stdout:
                raw_lines.append(line)
                q.put(line)
        except Exception:
            pass
        finally:
            q.put(None)

    rt = threading.Thread(target=_reader, daemon=True)
    rt.start()
    try:
        assert proc.stdin is not None
        req = {"id": "step06-1", "type": "prompt", "message": prompt_text}
        try:
            proc.stdin.write(json.dumps(req, ensure_ascii=False) + "\n")
            proc.stdin.flush()
        except Exception as e:
            raise RuntimeError(f"transient: stdin write failed: {e!r}")
        settled = False
        deadline = start_wall + timeout
        import queue as _qq
        while time.time() < deadline:
            try:
                line = q.get(timeout=max(1.0, deadline - time.time()))
            except _qq.Empty:
                continue
            if line is None:
                break
            buf = line.strip()
            if not buf:
                continue
            try:
                evt = json.loads(buf)
            except Exception as e:
                raise RuntimeError(f"transient: JSONL parse failed: {e!r}")
            if isinstance(evt, dict) and evt.get("type") == "agent_settled":
                settled = True
                break
        if not settled:
            raise RuntimeError(f"transient: liveness timeout {timeout:.0f}s")
    finally:
        try:
            with open(str(log_path) + ".jsonl", "a", encoding="utf-8") as jf:
                for ln in raw_lines:
                    jf.write(ln if ln.endswith("\n") else ln + "\n")
        except Exception:
            pass
        try:
            try:
                if proc.stdin is not None:
                    proc.stdin.close()
            except Exception:
                pass
            proc.terminate()
            try:
                proc.wait(timeout=10)
            except Exception:
                try:
                    proc.kill()
                except Exception:
                    pass
        except Exception:
            pass
    for _ in range(50):
        if out_path.exists():
            break
        time.sleep(0.1)
    if not out_path.exists():
        raise RuntimeError(f"missing: {output_rel} after agent_settled (缺件, 不补空)")
    return out_path


def _run_single_with_retry(workdir: Path, prompt: str, output_rel: str,
                           log_path: Path, parse_validate,
                           timeout: float, model, thinking: str,
                           per_path: Path, agent_fn=None):
    transient_left = 2
    format_left = 1
    backoff = (5.0, 15.0)
    bi = 0
    while True:
        try:
            if agent_fn is not None:
                try:
                    data = agent_fn(prompt)
                except SystemExit:
                    raise
                except Exception as e:
                    _fail(f"agent_fn fail: {e!r}")
                parsed = parse_validate(data)
                per_path.write_text(json.dumps(parsed, ensure_ascii=False, indent=2) + "\n",
                                    encoding="utf-8")
                return parsed
            _spawn_agent_once(workdir, prompt, output_rel, log_path,
                              timeout=timeout, model=model, thinking=thinking)
        except RuntimeError as e:
            msg = str(e)
            if msg.startswith("transient:"):
                if transient_left <= 0:
                    _fail(f"transient top: {msg}")
                wait = backoff[bi] if bi < len(backoff) else 15.0
                bi += 1
                transient_left -= 1
                time.sleep(wait)
                continue
            else:
                if format_left <= 0:
                    _fail(f"missing top: {msg}")
                format_left -= 1
                continue
        try:
            txt = per_path.read_text(encoding="utf-8")
            cand = _extract_json(txt, output_rel)
            parsed = parse_validate(cand)
            per_path.write_text(json.dumps(parsed, ensure_ascii=False, indent=2) + "\n",
                                encoding="utf-8")
            return parsed
        except SystemExit:
            if format_left <= 0:
                raise
            format_left -= 1
            try:
                if per_path.exists():
                    per_path.unlink()
            except Exception:
                pass
            continue


def run_step06_loop(workdir, sentences, agent_fn=None, timeout: float = 1800.0,
                    force: bool = False, max_workers: int = 4, stagger: float = 5.0,
                    model=None, thinking: str = "medium"):
    """06 两段调度: segmentation(串行) → wording×N(并行) → 合并落盘.

    agent_fn: 测试注入. 为 None 时走真 RPC spawn.
      - segmentation: agent_fn("segmentation", None, prompt) -> dict
      - wording: agent_fn("wording", phase, prompt) -> dict
    """
    fewshot = load_fewshot()
    outdir = workdir / "steps" / "06-phases"
    per_dir = outdir / "per_phase"
    outdir.mkdir(parents=True, exist_ok=True)
    per_dir.mkdir(parents=True, exist_ok=True)
    # fewshot 运行快照进工作区 (审计只读工作区约定路径; 快照与 repo FROZEN 文件逐字节一致, check 验相等)
    (outdir / "fewshot.md").write_text(fewshot, encoding="utf-8", newline="\n")

    # ---- segmentation (串行, 自定义波次) ----
    seg_prompt = build_segmentation_prompt(sentences, fewshot)
    seg_path = outdir / "segmentation.json"
    seg_log = outdir / "agent-segmentation.log"
    seg_rel = "steps/06-phases/segmentation.json"

    def _parse_seg(d):
        return validate_segmentation(d, sentences)

    seg = None
    if seg_path.exists() and not force:
        try:
            seg = _parse_seg(json.loads(seg_path.read_text(encoding="utf-8")))
        except SystemExit:
            raise
        except Exception:
            seg = None  # type: ignore
    if seg is None:
        full_seg = seg_prompt + f"\n\n只写相对路径 `{seg_rel}`，禁 `..` 与绝对盘符。\n"
        if agent_fn is not None:
            try:
                raw_s = agent_fn("segmentation", None, seg_prompt)
            except TypeError:
                _fail("agent_fn 须为三参 (kind, name_en, prompt)")
            except SystemExit:
                raise
            except Exception as e:
                _fail(f"segmentation agent_fn fail: {e!r}")
            seg = _parse_seg(raw_s)
            seg_path.write_text(json.dumps(seg, ensure_ascii=False, indent=2) + "\n",
                                encoding="utf-8")
        else:
            if seg_path.exists() and force:
                try:
                    seg_path.unlink()
                except Exception:
                    pass
            seg = _run_single_with_retry(workdir, full_seg, seg_rel, seg_log,
                                         _parse_seg, timeout, model, thinking, seg_path)
    buckets_raw: list[dict] = list(seg.get("buckets", []))

    # ---- buckets 回填 (code: quote_details) ----
    qlookup = _quote_lookup(sentences)
    buckets: list[dict] = []
    for b in buckets_raw:
        qs: list[str] = []
        for q in b.get("quotes", []):
            if q not in qs:
                qs.append(q)
        details = []
        for q in qs:
            hits = qlookup.get(q, [])
            h = hits[0] if hits else {"start": None, "end": None, "t": None,
                                      "context": q[:300]}
            if h.get("start") is not None and not isinstance(h.get("t"), int):
                _fail(f"segmentation {b.get('phase')} quote_details t 非法: {q[:40]!r}")
            details.append({"quote": q, "start": h["start"], "end": h["end"],
                            "t": h["t"], "context": h["context"]})
        buckets.append({"phase": b["phase"], "waves": b.get("waves", ""),
                        "quotes": qs, "quote_details": details})
    (outdir / "buckets.json").write_text(
        json.dumps(buckets, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")

    # ---- wording×N (并行, 每桶独立单 agent) ----
    # per_phase/log 按桶序号命名 (00.json/01.json, agent-wording-00.log), 不按 phase 名 (运营语言多为中文, safe 会碰撞)
    def _do_one(bucket: dict, idx: int):
        phase = bucket["phase"]
        tag = f"{idx:02d}"
        per_path = per_dir / f"{tag}.json"
        w_prompt = build_wording_prompt(
            {"phase": phase, "waves": bucket.get("waves", ""),
             "quotes": bucket.get("quotes", [])}, sentences, fewshot_text=fewshot)

        def _parse_w(d):
            return validate_wording(d, bucket, sentences)

        if per_path.exists() and not force:
            try:
                return _parse_w(json.loads(per_path.read_text(encoding="utf-8")))
            except SystemExit:
                raise
            except Exception:
                pass
        full_prompt = (w_prompt
                       + f"\n\n只写相对路径 `steps/06-phases/per_phase/{tag}.json`，"
                         f"禁 `..` 与绝对盘符。\n")
        if agent_fn is not None:
            try:
                raw_w = agent_fn("wording", phase, w_prompt)
            except SystemExit:
                raise
            except Exception as e:
                _fail(f"wording {phase} agent_fn fail: {e!r}")
            parsed = _parse_w(raw_w)
            per_path.write_text(json.dumps(parsed, ensure_ascii=False, indent=2) + "\n",
                                encoding="utf-8")
            return parsed
        log_path = outdir / f"agent-wording-{tag}.log"
        out_rel = f"steps/06-phases/per_phase/{tag}.json"
        if per_path.exists() and force:
            try:
                per_path.unlink()
            except Exception:
                pass
        return _run_single_with_retry(workdir, full_prompt, out_rel, log_path,
                                      _parse_w, timeout, model, thinking, per_path)

    wordings: list[dict] = []
    if agent_fn is not None:
        for _i, _b in enumerate(buckets):
            wordings.append(_do_one(_b, _i))
    else:
        with concurrent.futures.ThreadPoolExecutor(max_workers=max_workers) as ex:
            futs = {}
            for _i, _b in enumerate(buckets):
                futs[ex.submit(_do_one, _b, _i)] = _b["phase"]
                time.sleep(stagger)
            by_name: dict[str, dict] = {}
            for fut in concurrent.futures.as_completed(futs):
                ph = futs[fut]
                by_name[ph] = fut.result()
            wordings = [by_name[b["phase"]] for b in buckets]

    # 自洽: wordings N == buckets N, phase 对齐
    if len(wordings) != len(buckets):
        _fail(f"wordings N 须==buckets N: 期望 {len(buckets)}, 实得 {len(wordings)}")
    w_by = {w.get("phase"): w for w in wordings}
    if set(w_by.keys()) != set(b["phase"] for b in buckets):
        _fail(f"wordings phase 须==buckets 自洽: 期望 {sorted(b['phase'] for b in buckets)}, 实得 {sorted(w_by.keys())}")
    wordings_sorted = [w_by[b["phase"]] for b in buckets]
    (outdir / "wordings.json").write_text(
        json.dumps(wordings_sorted, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")

    # ---- 合并落盘 (code only) ----
    ql = _quote_lookup(sentences)
    phases: list[dict] = []
    for b in buckets:
        w = w_by.get(b["phase"])
        if w is None:
            _fail(f"合并缺 wording: {b['phase']!r} (缺件即 fail)")
        bqs: list[str] = list(b.get("quotes", []))
        ex: list[str] = list(w.get("extra_quotes") or [])
        # extra 已验真桶外; 此处再保去重保序 (桶内前缀须等于 buckets)
        merged_qs: list[str] = []
        for q in bqs + ex:
            if q not in merged_qs:
                merged_qs.append(q)
        if merged_qs[:len(bqs)] != bqs:
            _fail(f"合并桶内前缀须等于 buckets (不可改写): {b['phase']}")
        details = []
        for q in merged_qs:
            hits = ql.get(q, [])
            h = hits[0] if hits else {"start": None, "end": None, "t": None,
                                      "context": q[:300]}
            if h.get("start") is not None and not isinstance(h.get("t"), int):
                _fail(f"{b['phase']} quote_details t 非法: {q[:40]!r}")
            d = {"quote": q, "start": h["start"], "end": h["end"],
                 "t": h["t"], "context": h["context"]}
            if q in ex:
                d["out_of_window"] = True
            details.append(d)
        phases.append({"phase": b["phase"], "waves": b.get("waves", ""),
                       "goal": str(w.get("goal", "")).strip(),
                       "focus": str(w.get("focus", "")).strip(),
                       "pivot": str(w.get("pivot", "")).strip(),
                       "quotes": merged_qs, "quote_details": details})
    (outdir / "phases.json").write_text(
        json.dumps(phases, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    (workdir / "outputs").mkdir(parents=True, exist_ok=True)
    (workdir / "outputs" / "phases.json").write_text(
        json.dumps(phases, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    return phases
