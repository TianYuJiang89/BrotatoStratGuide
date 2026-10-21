#!/usr/bin/env python3
"""Step04 per-attribute loop (#60): frozen fewshot + for-loop 单属性 agent x39.

Deterministic-first:
- 固定代码只做: prompt 组装 (fewshot + 全量整句 + 一个属性名) / 输出形状校验 /
  count 回填 (现场扫 sentences, agent 不填) / quote_details 重建 (t/start/end/context 由 sentences lookup, 不信 agent).
- agent judgment 只做: rating + quotes + analysis + summary (语义零进代码, 不查动词/over/数量帽).
- 缺件/编 quote 即 fail loud, 不回落不补空.

输入:
- fewshot: prompts/step04-ratings-fewshot.md (FROZEN, 30-shot, 5职业x6档, 引文全机验)
- sentences: steps/01-sentences/sentences.json ([{id,text[,start,end],start_s,end_s,t}], 含 t/context)
- terms: data/terms.csv (主17+次22, 共39)

输出 (每属性 agent 原始):
- {term_en, rating, quotes, analysis, summary} (count 由代码回填, agent 不填)

落盘 (最终):
- steps/04-attributes/ratings.json (+ outputs/ratings.json): 数组39全量, 每条
  {term_en, term_zh, type, count, rating, quotes, analysis, summary, quote_details}
  - anchors/confidence/kind/inferred/reason 四件退役 (出现即 fail).
  - count==0 必 - 且 quotes==[] (作者未提及); count>0 必 S-D.
"""

from __future__ import annotations

import csv
import hashlib
import json
import re
import subprocess
import sys
import time
from pathlib import Path
from collections import defaultdict
from typing import NoReturn

REPO = Path(__file__).resolve().parent.parent

FEWSHOT_REL = "prompts/step04-ratings-fewshot.md"
VALID_RATINGS = {"S", "A", "B", "C", "D", "-"}
RETIRED_FIELDS = ("anchors", "confidence", "kind", "inferred", "reason")
SUMMARY_MAX_LEN = 120
_TS_RE = re.compile(r"^\d{2}:\d{2}:\d{2}[.,]\d{3}$")


def _fail(msg: str) -> NoReturn:
    raise SystemExit(f"step04-loop FAIL: {msg}")


def load_terms() -> list[dict]:
    p = REPO / "data" / "terms.csv"
    if not p.exists():
        _fail(f"missing data/terms.csv (39全量输入缺件即 fail)")
    rows = list(csv.DictReader(p.open(encoding="utf-8")))
    if len(rows) != 39:
        _fail(f"terms.csv must be 39 (主17+次级22), got {len(rows)}")
    return rows


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


def build_attribute_prompt(term_en: str, sentences: list[dict], fewshot_text: str) -> str:
    """组装单属性任务 prompt: 基准fewshot + 全量整句 + 这一个属性名.

    语义零进代码: 本函数只做拼接, 不注入任何动词闭集/窗/over/负面/count 规则.
    """
    if not term_en or not isinstance(term_en, str):
        _fail("TASK_ATTR 缺属性名 (缺件即 fail)")
    if not isinstance(sentences, list) or not sentences:
        _fail("sentences 为空 (缺件即 fail)")
    # 全量整句 (含 start/end/t/context, 原样全给, 不截断不 cap)
    lines: list[str] = []
    for s in sentences:
        sid = s.get("id")
        txt = s.get("text", "")
        start = s.get("start")
        end = s.get("end")
        t = s.get("t")
        # context 只读: 前后1句 (与 run_segment1.build_context 同口径)
        lines.append(json.dumps({"id": sid, "text": txt, "start": start, "end": end, "t": t},
                                ensure_ascii=False))
    blob = "\n".join(lines)
    prompt = (
        fewshot_text
        + "## 该角色全量整句（含 start/end/t/context，原样全量，不截断）\n\n"
        + "```json\n" + blob + "\n```\n\n"
        + "\n\n---\n\n# TASK_ATTR（本轮只评这一个属性，其它属性一律不评）\n\n"
        + f"TASK_ATTR: {term_en}\n\n"
        + "## 输出契约（只输出一件 JSON 对象，不输出其它文字）\n\n"
        + '{"term_en": "<与 TASK_ATTR 一字不差>", "rating": "S/A/B/C/D/-", '
        + '"quotes": ["逐字出自上表 text，去重"], '
        + '"analysis": "来源（捡/转/自带/不买·无/缺席）→机制效果→评级", '
        + '"summary": "≤120字中文人话"}\n\n'
        + "- term_en 须与 TASK_ATTR 一字不差；你不输出 count。\n"
        + "- quotes 须逐字等于上表某条 text，去重；编 quote 即 fail。\n"
        + "- 若你判定作者未提及，rating 必 `-`，quotes 必 []，summary 写作者未提及。\n"
        + "- analysis 写全过程（来源→机制→评级），犹豫/tradeoff/未知一律写进 analysis。\n"
        + "- 缺句/编 quote 即 fail，不回落不补空。\n"
    )
    return prompt




def validate_attribute_output(data: dict, term_en: str, sentences: list[dict]) -> None:
    """形状校验 (只卡形状, 不查动词/over/S数量帽).

    - term_en 一字不差; rating 合法; count 由调用方传入 (agent 不填 count, 含 count 即 fail).
    - 旧四件+reason 退役: 出现即 fail.
    - quotes 逐字出自整句 + 去重; count==0 ⇔ - 且 quotes==[].
    - analysis 非空; summary 非空 ≤120 + 禁计数泄漏.
    - 编 quote/缺件即 fail loud.
    """
    if not isinstance(data, dict):
        _fail(f"{term_en} agent 输出须为 JSON 对象, got {type(data)}")
    # count 只活代码 (code = len(quotes), 无扫描): agent 不许填
    if "count" in data:
        _fail(f"{term_en} agent 不许填 count")
    # 退役字段: 出现即 fail
    for f in RETIRED_FIELDS:
        if f in data:
            _fail(f"{term_en} 字段 {f} 已退役 (#60, 出现即 fail)")
    for k in ("term_en", "rating", "quotes", "analysis", "summary"):
        if k not in data:
            _fail(f"{term_en} 缺字段 {k} (缺件即 fail, 不补空)")
    if data.get("term_en") != term_en:
        _fail(f"term_en 须与 TASK_ATTR 一字不差: 期望 {term_en!r}, 实得 {data.get('term_en')!r}")
    rating = data.get("rating")
    if rating not in VALID_RATINGS:
        _fail(f"{term_en} rating 须为 S/A/B/C/D/- 之一, got {rating!r}")
    quotes = data.get("quotes")
    if not isinstance(quotes, list) or any(not isinstance(q, str) for q in quotes):
        _fail(f"{term_en} quotes 须为字符串数组")
    if len(quotes) != len(set(quotes)):
        _fail(f"{term_en} quotes 须去重")
    # 逐字出自整句
    sent_texts = {s.get("text") for s in sentences if isinstance(s, dict)}
    for q in quotes:
        if q not in sent_texts:
            _fail(f"{term_en} 编 quote 即 fail: {q[:60]!r} 不在整句内 (逐字)")
    analysis = data.get("analysis")
    if not isinstance(analysis, str) or len(analysis.strip()) < 4:
        _fail(f"{term_en} analysis 须为非空人话 (审计全过程, 缺件即 fail)")
    summary = data.get("summary")
    if not isinstance(summary, str) or not summary.strip():
        _fail(f"{term_en} summary 缺件即 fail")
    if len(summary) > SUMMARY_MAX_LEN:
        _fail(f"{term_en} summary 须≤{SUMMARY_MAX_LEN}字, got {len(summary)}")
    # 短引若含 “...” 则须出自 quotes (含短引约束: 有引号即验, 无引号不强制)
    for m in re.finditer(r"[“\"'](.{4,}?)[”\"']", summary):
        inner = m.group(1).strip()
        if inner and inner != "作者未提及":
            qall = " ".join(quotes)
            if inner not in qall and not any(inner[:10] in q for q in quotes if len(inner) >= 10):
                # 放宽: 短引允许截断/改写标点？不，须逐字。短引不在 quotes 内即 fail。
                # 但 frozen 例 summary 无短引，故无引号时不判；有引号才判。
                _fail(f"{term_en} summary 短引须出自本条 quotes 逐字: {inner[:30]!r}")
    # agent 自洽 (无扫描, 全权 agent): '-' ⇔ quotes==[]
    if rating == "-":
        if quotes:
            _fail(f"{term_en} '-' 必 quotes==[] (自洽)")
        if "作者未提及" not in str(summary):
            _fail(f"{term_en} '-' summary 须写作者未提及")
    else:
        if not quotes:
            _fail(f"{term_en} S-D 必有 quotes (缺件即 fail)")


def build_final_entry(term_en: str, term_zh: str, typ: str,
                      agent_data: dict, sentences: list[dict]) -> dict:
    """合并最终条目: 代码回填 term_zh/type/count + 重建 quote_details.

    quote_details 由 sentences lookup 重建 (t/start/end/context), 不信 agent,
    保证 t 合法 + 等长平行. 旧字段永不写入.
    """
    quotes: list[str] = list(agent_data.get("quotes") or [])
    # 去重保序 (validate 已验, 此处再保)
    seen: list[str] = []
    for q in quotes:
        if q not in seen:
            seen.append(q)
    qlookup = _quote_lookup(sentences)
    details: list[dict] = []
    for q in seen:
        hits = qlookup.get(q, [])
        h = hits[0] if hits else {"start": None, "end": None, "t": None, "context": q[:300]}
        # t 合法: 有 start 必有 int t (沿 check_segment1 ?t= 约束)
        if h.get("start") is not None and not isinstance(h.get("t"), int):
            _fail(f"{term_en} quote_details t 非法 (有 start 必有 int t): {q[:40]!r}")
        details.append({"quote": q, "start": h["start"], "end": h["end"],
                        "t": h["t"], "context": h["context"]})
    return {
        "term_en": term_en,
        "term_zh": term_zh,
        "type": typ,
        "count": len(seen),
        "rating": agent_data.get("rating"),
        "quotes": seen,
        "analysis": str(agent_data.get("analysis", "")).strip(),
        "summary": str(agent_data.get("summary", "")).strip(),
        "quote_details": details,
    }


def _safe_term(term_en: str) -> str:
    return re.sub(r"[^A-Za-z0-9]+", "_", term_en).strip("_")


def _spawn_agent_once(workdir: Path, prompt_text: str, output_rel: str,
                      log_path: Path, timeout: float = 1800.0, model=None, thinking="medium") -> Path:
    """单次 RPC spawn (复用 run_chain 口径: transient/缺件/格式由调用方重试).

    本函数只做单次, 不重试. transient 抛 RuntimeError("transient: ..."),
    settled 后无落盘抛 RuntimeError("missing: ...").
    """
    import queue
    import threading

    import shutil as _sh
    def build_agent_cmd() -> list[str]:
        # #60 04-loop 纯 judgment, thinking 必须开 (xhigh 对齐主 session).
        # 不复用 run_chain.build_agent_cmd (off, 确定性步用;改它会碰 06/08).
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

    import threading as _th
    rt = _th.Thread(target=_reader, daemon=True)
    rt.start()
    try:
        assert proc.stdin is not None
        req = {"id": "step04-1", "type": "prompt", "message": prompt_text}
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


def _do_one_term(workdir, sentences, fewshot, per_dir, t, agent_fn=None, timeout=1800.0, force=False, model=None, thinking="medium"):
    import json
    import time
    en = t["en"].strip()
    zh = t.get("zh", "")
    typ = t.get("type", "")
    per_path = per_dir / f"{_safe_term(en)}.json"
    agent_data = None
    if per_path.exists() and not force:
        try:
            cand = json.loads(per_path.read_text(encoding="utf-8"))
            validate_attribute_output(cand, en, sentences)
            agent_data = cand
        except SystemExit:
            raise
        except Exception:
            agent_data = None
    if agent_data is None:
        prompt = build_attribute_prompt(en, sentences, fewshot)
        if agent_fn is not None:
            try:
                agent_data = agent_fn(en, prompt)
            except SystemExit:
                raise
            except Exception as e:
                _fail(f"{en} agent_fn fail: {e!r}")
        else:
            full_prompt = prompt + f"\n\n只写相对路径 `steps/04-attributes/per_attr/{_safe_term(en)}.json`，禁 `..` 与绝对盘符。\n"
            log_path = workdir / "steps" / "04-attributes" / f"agent-{_safe_term(en)}.log"
            out_rel = f"steps/04-attributes/per_attr/{_safe_term(en)}.json"
            if per_path.exists() and force:
                try:
                    per_path.unlink()
                except Exception:
                    pass
            transient_left = 2
            format_left = 1
            backoff = (5.0, 15.0)
            bi = 0
            while True:
                try:
                    _spawn_agent_once(workdir, full_prompt, out_rel, log_path, timeout=timeout, model=model, thinking=thinking)
                except RuntimeError as e:
                    msg = str(e)
                    if msg.startswith("transient:"):
                        if transient_left <= 0:
                            _fail(f"{en} transient top: {msg}")
                        wait = backoff[bi] if bi < len(backoff) else 15.0
                        bi += 1
                        transient_left -= 1
                        time.sleep(wait)
                        continue
                    else:
                        if format_left <= 0:
                            _fail(f"{en} missing top: {msg}")
                        format_left -= 1
                        continue
                try:
                    txt = per_path.read_text(encoding="utf-8")
                    cand = _extract_json(txt, en)
                    validate_attribute_output(cand, en, sentences)
                    agent_data = cand
                    per_path.write_text(json.dumps(agent_data, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
                    break
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
        if agent_fn is not None and agent_data is not None:
            validate_attribute_output(agent_data, en, sentences)
            per_path.write_text(json.dumps(agent_data, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    assert agent_data is not None
    return build_final_entry(en, zh, typ, agent_data, sentences)


def run_step04_loop(workdir, sentences, agent_fn=None, timeout=1800.0, force=False, max_workers=4, stagger=5.0, model=None, thinking="medium"):
    import concurrent.futures
    import json
    terms = load_terms()
    fewshot = load_fewshot()
    per_dir = workdir / "steps" / "04-attributes" / "per_attr"
    per_dir.mkdir(parents=True, exist_ok=True)
    import time as _tm
    with concurrent.futures.ThreadPoolExecutor(max_workers=max_workers) as ex:
        futs = {}
        for t in terms:
            futs[ex.submit(_do_one_term, workdir, sentences, fewshot, per_dir, t, agent_fn, timeout, force, model, thinking)] = t["en"].strip()
            _tm.sleep(stagger)
        by_en = {}
        for fut in concurrent.futures.as_completed(futs):
            en = futs[fut]
            by_en[en] = fut.result()
    ratings = [by_en[t["en"].strip()] for t in terms]
    if len(ratings) != 39:
        _fail(f"ratings must be 39, got {len(ratings)}")
    outdir = workdir / "steps" / "04-attributes"
    outdir.mkdir(parents=True, exist_ok=True)
    (outdir / "ratings.json").write_text(json.dumps(ratings, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    (workdir / "outputs").mkdir(parents=True, exist_ok=True)
    (workdir / "outputs" / "ratings.json").write_text(json.dumps(ratings, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    return ratings

def _extract_json(text: str, term_en: str) -> dict:
    """剥离 ```json 包裹并解析, 非 JSON 即 fail loud."""
    t = text.strip()
    # 剥 markdown fence
    if "```" in t:
        m = re.search(r"```(?:json)?\s*(\{.*?\})\s*```", t, re.DOTALL)
        if m:
            t = m.group(1).strip()
    # 首 { 尾 } 截取 (防前后废话)
    if not t.startswith("{"):
        i = t.find("{")
        j = t.rfind("}")
        if i >= 0 and j > i:
            t = t[i:j + 1]
    try:
        data = json.loads(t)
    except Exception as e:
        _fail(f"{term_en} agent 输出非 JSON 即 fail: {e}; head={text[:120]!r}")
        raise  # pragma: no cover
    if not isinstance(data, dict):
        _fail(f"{term_en} agent 输出须为对象")
    return data  # type: ignore[return-value]
