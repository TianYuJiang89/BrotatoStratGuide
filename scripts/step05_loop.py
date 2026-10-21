#!/usr/bin/env python3
"""Step05 three-agent loop (#61): frozen fewshot + discovery/evidence/ranking.

Deterministic-first:
- 固定代码只做: prompt 组装 (任务手册 + 全量整句 + 词汇表/一名/N份evidence) / 输出形状校验 /
  count 回填 (=len(quotes), agent 不填) / quote_details 重建 (sentences lookup, 不信 agent) /
  名在表 (武器词汇表78, 幻觉即 fail) / 去重 / T1+T2==candidates 自洽 / 落盘
  (candidates.json + weapons.json + per_weapon/* + 日志).
- agent judgment 只做: discovery 补全 (completeness 归它, scan 子串已退役) /
  evidence 单把判断 (tier建议+quotes+analysis+note) / ranking 切分 (t1/t2+note定稿, T1>=1由它保,
  可推翻 evidence tier, 切分拿 quote 说话禁数帽).
- 缺件/编 quote/幻觉名即 fail loud, 不回落不补空.

输入:
- fewshot: prompts/step05-{discovery,evidence,ranking}-fewshot.md (FROZEN v2, 按任务拆三本, 各贴各的)
- sentences: steps/01-sentences/sentences.json ([{id,text[,start,end],start_s,end_s,t}])
- vocab: data/wiki-cache.json weapons 78 (全局唯一, 不读 registry-slice, 不读 02-verbs)

输出:
- steps/05-weapons/candidates.json: [{name_en, count, quotes, quote_details}]
- steps/05-weapons/per_weapon/<Safe>.json: evidence 原始 (validated, 无 count)
- steps/05-weapons/weapons.json (+ outputs/weapons.json):
  {t1[], t2[]} 每条 {name_en, count, tier, quotes, analysis, note, quote_details}
  - confidence/kind/inferred/anchors/score/断层/数字词表/verified加分全退役 (出现即 fail).
  - count==len(quotes); note 只查非空 (意图保, 码检不保数字).
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

FEWSHOT_DISCOVERY_REL = "prompts/step05-discovery-fewshot.md"
FEWSHOT_EVIDENCE_REL = "prompts/step05-evidence-fewshot.md"
FEWSHOT_RANKING_REL = "prompts/step05-ranking-fewshot.md"
VALID_TIERS = {"T1", "T2"}
RETIRED_FIELDS = ("anchors", "confidence", "kind", "inferred", "score", "reason")
NOTE_MAX_LEN = 120


def _fail(msg: str) -> NoReturn:
    raise SystemExit(f"step05-loop FAIL: {msg}")


def load_fewshot(rel: str) -> str:
    p = REPO / rel
    if not p.exists():
        _fail(f"missing {rel} (frozen fewshot 缺件即 fail, 不回落)")
    txt = p.read_text(encoding="utf-8")
    if "FROZEN" not in txt:
        _fail(f"{rel} 缺 FROZEN 头 (freeze 完整性 fail)")
    return txt


def load_weapon_vocab() -> list[str]:
    p = REPO / "data" / "wiki-cache.json"
    if not p.exists():
        _fail("missing data/wiki-cache.json (武器词汇表缺件即 fail)")
    try:
        d = json.loads(p.read_text(encoding="utf-8"))
    except Exception as e:
        _fail(f"wiki-cache.json 读失败: {e!r}")
    w = d.get("weapons")
    if not isinstance(w, dict) or not w:
        _fail("wiki-cache weapons 非法 (须为非空对象)")
    names = sorted(w.keys())
    if len(names) < 10:
        _fail(f"weapons vocab 过小: {len(names)} (疑文件损坏)")
    return names


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


def build_discovery_prompt(sentences: list[dict], vocab: list[str], fewshot_text: str) -> str:
    if not isinstance(sentences, list) or not sentences:
        _fail("sentences 为空 (缺件即 fail)")
    if not vocab:
        _fail("武器词汇表为空 (缺件即 fail)")
    blob = _sentences_blob(sentences)
    vocab_line = ", ".join(vocab)
    prompt = (
        fewshot_text
        + "\n\n## 该角色全量整句（含 start/end/t，原样全量，不截断）\n\n"
        + "```json\n" + blob + "\n```\n\n"
        + "## 武器词汇表（78，全局唯一，只认此表，一字不差）\n\n"
        + vocab_line + "\n\n"
        + "---\n\n# TASK_DISCOVERY（只输出候选武器名单，completeness 归你）\n\n"
        + "## 输出契约（只输出一件 JSON 对象，不输出其它文字）\n\n"
        + '{"candidates": [{"name_en": "<词汇表一字不差>", "quotes": ["逐字出自上表，去重，≥1"]}]}\n\n'
        + "- 只收有买/锁/升/留/转 build 意图的真武器；路过名词（开局 trick 即卖/类别口头/子串误触/cursed 犹豫没买/只提一次无后文）一律丢。\n"
        + "- name_en 须与词汇表一字不差；幻觉名即 fail。\n"
        + "- quotes 须逐字等于上表某条 text，去重，每把 ≥1。编 quote 即 fail。\n"
        + "- 你不输出 count。\n"
        + "- 缺件/空名单即 fail，不回落不补空。\n"
    )
    return prompt


def build_evidence_prompt(name_en: str, sentences: list[dict], fewshot_text: str) -> str:
    if not name_en or not isinstance(name_en, str):
        _fail("TASK_EVIDENCE 缺武器名 (缺件即 fail)")
    if not isinstance(sentences, list) or not sentences:
        _fail("sentences 为空 (缺件即 fail)")
    blob = _sentences_blob(sentences)
    prompt = (
        fewshot_text
        + "\n\n## 该角色全量整句（含 start/end/t，原样全量，不截断）\n\n"
        + "```json\n" + blob + "\n```\n\n"
        + "\n\n---\n\n# TASK_EVIDENCE（本轮只判这一把武器，其它一律不判）\n\n"
        + f"TASK_WEAPON: {name_en}\n\n"
        + "## 输出契约（只输出一件 JSON 对象，不输出其它文字）\n\n"
        + '{"name_en": "<与 TASK_WEAPON 一字不差>", "tier": "T1/T2（建议）", '
        + '"quotes": ["逐字出自上表，去重，非空"], '
        + '"analysis": "来源→机制→分档", '
        + '"note": "≤120字人话+短引（含把数/波次数字逐字）"}\n\n'
        + "- name_en 须与 TASK_WEAPON 一字不差；幻觉名即 fail。\n"
        + "- quotes 须逐字等于上表某条 text，去重，非空；空证据即 fail（武器无 `-` 档）。编 quote 即 fail。\n"
        + "- analysis 写全过程（来源→机制→分档）。\n"
        + "- note ≤120 字，人话 + 短引（短引须出自本条 quotes 逐字，含把数/波次数字逐字，不编数字）。\n"
        + "- 你不输出 count。缺件即 fail，不回落不补空。\n"
    )
    return prompt


def build_ranking_prompt(sentences: list[dict], evidences: list[dict], fewshot_text: str) -> str:
    if not isinstance(sentences, list) or not sentences:
        _fail("sentences 为空 (缺件即 fail)")
    if not evidences:
        _fail("evidences 为空 (缺件即 fail)")
    blob = _sentences_blob(sentences)
    ev_blob = json.dumps(evidences, ensure_ascii=False, indent=2)
    names = ", ".join(e.get("name_en", "") for e in evidences)
    prompt = (
        fewshot_text
        + "\n\n## 该角色全量整句（含 start/end/t，原样全量，不截断）\n\n"
        + "```json\n" + blob + "\n```\n\n"
        + "## N 份 evidence（通览，全量，不截断）\n\n"
        + "```json\n" + ev_blob + "\n```\n\n"
        + "\n\n---\n\n# TASK_RANKING（只切分，不编 quote；T1≥1 由你保）\n\n"
        + f"候选名单（须全切分，一把不丢）: {names}\n\n"
        + "## 输出契约（只输出一件 JSON 对象，不输出其它文字）\n\n"
        + '{"t1": [{"name_en": "<候选一字不差>", "note": "≤120字定稿人话+短引"}], '
        + '"t2": [{"name_en": "...", "note": "..."}]}\n\n'
        + "- T1≥1（验收线，由你保）；可推翻 evidence tier；切分拿 quote 说话，禁数帽。\n"
        + "- T1+T2 须 == 候选名单（自洽，一把不多一把不少）；幻觉名即 fail。\n"
        + "- note 每条 ≤120 字，人话 + 短引（短引须出自对应 evidence quotes 逐字）。\n"
        + "- 你不输出 quotes/analysis/count（只定 tier+note）。缺件即 fail。\n"
    )
    return prompt


def validate_discovery(data: dict, sentences: list[dict], vocab: list[str]) -> list[dict]:
    if not isinstance(data, dict):
        _fail(f"discovery 输出须为 JSON 对象, got {type(data)}")
    for f in RETIRED_FIELDS:
        if f in data:
            _fail(f"discovery 字段 {f} 已退役 (#61, 出现即 fail)")
    if "count" in data:
        _fail("discovery 不许填 count (只活代码)")
    if "candidates" not in data:
        _fail("discovery 缺 candidates (缺件即 fail, 不补空)")
    cands = data["candidates"]
    if not isinstance(cands, list) or not cands:
        _fail("discovery candidates 须为非空数组 (空即 fail, completeness 归你)")
    vocab_set = set(vocab)
    sent_texts = {s.get("text") for s in sentences if isinstance(s, dict)}
    seen_names: set[str] = set()
    out: list[dict] = []
    for c in cands:
        if not isinstance(c, dict):
            _fail("discovery candidate 须为对象")
        for k in ("name_en", "quotes"):
            if k not in c:
                _fail(f"discovery candidate 缺 {k} (缺件即 fail)")
        name = c.get("name_en")
        if not isinstance(name, str) or name not in vocab_set:
            _fail(f"discovery 幻觉名即 fail: {name!r} 不在武器词汇表 (逐字)")
        if name in seen_names:
            _fail(f"discovery candidates 须去重: {name!r}")
        seen_names.add(name)
        qs = c.get("quotes")
        if not isinstance(qs, list) or not qs or any(not isinstance(q, str) for q in qs):
            _fail(f"discovery {name} quotes 须为非空字符串数组 (空证据即 fail)")
        if len(qs) != len(set(qs)):
            _fail(f"discovery {name} quotes 须去重")
        for q in qs:
            if q not in sent_texts:
                _fail(f"discovery {name} 编 quote 即 fail: {q[:60]!r} 不在整句内 (逐字)")
        out.append({"name_en": name, "quotes": list(qs)})
    return out


def validate_evidence(data: dict, name_en: str, sentences: list[dict]) -> dict:
    if not isinstance(data, dict):
        _fail(f"{name_en} evidence 输出须为 JSON 对象, got {type(data)}")
    if "count" in data:
        _fail(f"{name_en} evidence 不许填 count (只活代码)")
    for f in RETIRED_FIELDS:
        if f in data:
            _fail(f"{name_en} 字段 {f} 已退役 (#61, 出现即 fail)")
    for k in ("name_en", "tier", "quotes", "analysis", "note"):
        if k not in data:
            _fail(f"{name_en} evidence 缺 {k} (缺件即 fail, 不补空)")
    if data.get("name_en") != name_en:
        _fail(f"evidence name_en 须一字不差: 期望 {name_en!r}, 实得 {data.get('name_en')!r}")
    if data.get("tier") not in VALID_TIERS:
        _fail(f"{name_en} evidence tier 须为 T1/T2 之一, got {data.get('tier')!r}")
    qs = data.get("quotes")
    if not isinstance(qs, list) or not qs or any(not isinstance(q, str) for q in qs):
        _fail(f"{name_en} evidence 空证据即 fail (quotes 须非空)")
    if len(qs) != len(set(qs)):
        _fail(f"{name_en} evidence quotes 须去重")
    sent_texts = {s.get("text") for s in sentences if isinstance(s, dict)}
    for q in qs:
        if q not in sent_texts:
            _fail(f"{name_en} 编 quote 即 fail: {q[:60]!r} 不在整句内 (逐字)")
    ana = data.get("analysis")
    if not isinstance(ana, str) or len(ana.strip()) < 4:
        _fail(f"{name_en} evidence analysis 须为非空人话 (缺件即 fail)")
    note = data.get("note")
    if not isinstance(note, str) or not note.strip():
        _fail(f"{name_en} evidence note 缺件即 fail")
    if len(note) > NOTE_MAX_LEN:
        _fail(f"{name_en} evidence note 须≤{NOTE_MAX_LEN}字, got {len(note)}")
    return {"name_en": name_en, "tier": data.get("tier"),
            "quotes": list(qs), "analysis": str(ana).strip(), "note": str(note).strip()}


def validate_ranking(data: dict, candidate_names: list[str], evidences: list[dict]) -> dict:
    if not isinstance(data, dict):
        _fail(f"ranking 输出须为 JSON 对象, got {type(data)}")
    for f in RETIRED_FIELDS:
        if f in data:
            _fail(f"ranking 字段 {f} 已退役 (#61, 出现即 fail)")
    if "count" in data:
        _fail("ranking 不许填 count (只活代码)")
    for k in ("t1", "t2"):
        if k not in data:
            _fail(f"ranking 缺 {k} (缺件即 fail)")
    t1 = data["t1"]
    t2 = data["t2"]
    if not isinstance(t1, list) or not isinstance(t2, list):
        _fail("ranking t1/t2 须为数组")
    if len(t1) < 1:
        _fail("ranking T1≥1 (验收线, 由 ranking 保)")
    ev_by = {e.get("name_en"): e for e in evidences if isinstance(e, dict)}
    seen: set[str] = set()
    out_t1: list[dict] = []
    out_t2: list[dict] = []
    for tier_key, arr, out_arr in (("t1", t1, out_t1), ("t2", t2, out_t2)):
        for e in arr:
            if not isinstance(e, dict):
                _fail(f"ranking {tier_key} 条目须为对象")
            for k in ("name_en", "note"):
                if k not in e:
                    _fail(f"ranking {tier_key} 缺 {k} (缺件即 fail)")
            name = e.get("name_en")
            note = e.get("note")
            if name in seen:
                _fail(f"ranking {name!r} 重复 (T1+T2 须==candidates 去重)")
            seen.add(name)
            if name not in set(candidate_names):
                _fail(f"ranking 幻觉名即 fail: {name!r} 不在 candidates 内")
            if name not in ev_by:
                _fail(f"ranking {name!r} 无对应 evidence (缺件即 fail)")
            if not isinstance(note, str) or not note.strip():
                _fail(f"ranking {name} note 缺件即 fail (意图保, 码只查非空)")
            if len(note) > NOTE_MAX_LEN:
                _fail(f"ranking {name} note 须≤{NOTE_MAX_LEN}字, got {len(note)}")
            out_arr.append({"name_en": name, "note": str(note).strip()})
    if set(seen) != set(candidate_names):
        _fail(f"ranking T1+T2 须==candidates 自洽: 期望 {sorted(candidate_names)}, 实得 {sorted(seen)}")
    return {"t1": out_t1, "t2": out_t2}


def _safe_term(name_en: str) -> str:
    return re.sub(r"[^A-Za-z0-9]+", "_", name_en).strip("_")


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
        req = {"id": "step05-1", "type": "prompt", "message": prompt_text}
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
    data = None
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


def run_step05_loop(workdir, sentences, agent_fn=None, timeout: float = 1800.0,
                    force: bool = False, max_workers: int = 4, stagger: float = 5.0,
                    model=None, thinking: str = "medium"):
    """三段调度: discovery(串行) → evidence×N(并行) → ranking(串行).

    agent_fn: 测试注入. 为 None 时走真 RPC spawn.
      - discovery: agent_fn("discovery", None, prompt) -> dict
      - evidence: agent_fn("evidence", name_en, prompt) -> dict
      - ranking: agent_fn("ranking", None, prompt) -> dict
      兼容旧口径 agent_fn(name_en, prompt) 仅 evidence? 不兼容, 必须三段签.
      测试请传 (kind, name, prompt) 三参; 若传二参函数, 按 evidence 处理会 fail loud.
    """
    vocab = load_weapon_vocab()
    fewshot_d = load_fewshot(FEWSHOT_DISCOVERY_REL)
    fewshot_e = load_fewshot(FEWSHOT_EVIDENCE_REL)
    fewshot_r = load_fewshot(FEWSHOT_RANKING_REL)
    outdir = workdir / "steps" / "05-weapons"
    per_dir = outdir / "per_weapon"
    outdir.mkdir(parents=True, exist_ok=True)
    per_dir.mkdir(parents=True, exist_ok=True)
    # fewshot 快照进工作区 (#61跟进: 审计只读工作区约定路径, file:///picker/?base= 全通;
    # 快照与 repo FROZEN 文件逐字节一致, check 验相等, 即本次运行 provenance;
    # Windows write_text 默认 \n→\r\n, 必须显式 newline="\n" 否则逐字节永对不上)
    (outdir / "fewshot-discovery.md").write_text(fewshot_d, encoding="utf-8", newline="\n")
    (outdir / "fewshot-evidence.md").write_text(fewshot_e, encoding="utf-8", newline="\n")
    (outdir / "fewshot-ranking.md").write_text(fewshot_r, encoding="utf-8", newline="\n")
    _legacy = outdir / "fewshot.md"
    if _legacy.exists():
        _legacy.unlink()  # v1 单本快照已退役, 删 stale 防混淆

    # ---- discovery (串行) ----
    disc_path = outdir / "candidates.json"
    disc_prompt = build_discovery_prompt(sentences, vocab, fewshot_d)
    disc_log = outdir / "agent-discovery.log"
    disc_rel = "steps/05-weapons/candidates.json"

    def _parse_disc(d):
        return validate_discovery(d, sentences, vocab)

    if disc_path.exists() and not force:
        try:
            raw = json.loads(disc_path.read_text(encoding="utf-8"))
            # candidates.json 落盘形态为数组 (code 回填后); agent 原始为 {candidates: []}.
            # 复用时兼容两种: 若为数组, 视为已回填, 逐条验形状.
            if isinstance(raw, list):
                # 轻验: 每条须有 name_en/quotes, quotes 逐字.
                sent_texts = {s.get("text") for s in sentences if isinstance(s, dict)}
                tmp = {"candidates": [{"name_en": r.get("name_en"),
                                       "quotes": r.get("quotes")} for r in raw]}
                validated = validate_discovery(tmp, sentences, vocab)
                # 用 validated 重建回填 (幂等)
                disc_validated = validated
            elif isinstance(raw, dict):
                disc_validated = _parse_disc(raw)
            else:
                disc_validated = None  # type: ignore
                _fail("candidates.json 非法 (须为数组或 discovery 对象)")
        except SystemExit:
            raise
        except Exception:
            disc_validated = None  # type: ignore
    else:
        disc_validated = None  # type: ignore

    if disc_validated is None:
        full_disc_prompt = (disc_prompt
                            + f"\n\n只写相对路径 `{disc_rel}`，禁 `..` 与绝对盘符。\n")
        if agent_fn is not None:
            try:
                raw_d = agent_fn("discovery", None, disc_prompt)
            except TypeError:
                _fail("agent_fn 须为三参 (kind, name_en, prompt): discovery/evidence/ranking")
            except SystemExit:
                raise
            except Exception as e:
                _fail(f"discovery agent_fn fail: {e!r}")
            disc_validated = _parse_disc(raw_d)
        else:
            if disc_path.exists() and force:
                try:
                    disc_path.unlink()
                except Exception:
                    pass
            disc_validated = _run_single_with_retry(
                workdir, full_disc_prompt, disc_rel, disc_log,
                _parse_disc, timeout, model, thinking, disc_path)

    # discovery 回填 candidates.json (code: count=len(quotes) + quote_details)
    qlookup = _quote_lookup(sentences)
    candidates: list[dict] = []
    for c in disc_validated:
        qs: list[str] = []
        for q in c.get("quotes", []):
            if q not in qs:
                qs.append(q)
        details = []
        for q in qs:
            hits = qlookup.get(q, [])
            h = hits[0] if hits else {"start": None, "end": None, "t": None,
                                      "context": q[:300]}
            if h.get("start") is not None and not isinstance(h.get("t"), int):
                _fail(f"discovery {c.get('name_en')} quote_details t 非法: {q[:40]!r}")
            details.append({"quote": q, "start": h["start"], "end": h["end"],
                            "t": h["t"], "context": h["context"]})
        candidates.append({"name_en": c["name_en"], "count": len(qs),
                           "quotes": qs, "quote_details": details})
    # 按名排序落盘 (幂等)
    candidates = sorted(candidates, key=lambda x: x["name_en"])
    disc_path.write_text(json.dumps(candidates, ensure_ascii=False, indent=2) + "\n",
                         encoding="utf-8")
    candidate_names = [c["name_en"] for c in candidates]

    # ---- evidence×N (并行) ----
    def _do_one(name_en: str):
        safe = _safe_term(name_en)
        per_path = per_dir / f"{safe}.json"
        ev_prompt = build_evidence_prompt(name_en, sentences, fewshot_text=fewshot_e)

        def _parse_ev(d):
            return validate_evidence(d, name_en, sentences)

        if per_path.exists() and not force:
            try:
                cand = json.loads(per_path.read_text(encoding="utf-8"))
                return _parse_ev(cand)
            except SystemExit:
                raise
            except Exception:
                pass
        full_prompt = (ev_prompt
                       + f"\n\n只写相对路径 `steps/05-weapons/per_weapon/{safe}.json`，"
                         f"禁 `..` 与绝对盘符。\n")
        if agent_fn is not None:
            try:
                raw_e = agent_fn("evidence", name_en, ev_prompt)
            except SystemExit:
                raise
            except Exception as e:
                _fail(f"evidence {name_en} agent_fn fail: {e!r}")
            parsed = _parse_ev(raw_e)
            per_path.write_text(json.dumps(parsed, ensure_ascii=False, indent=2) + "\n",
                                encoding="utf-8")
            return parsed
        log_path = outdir / f"agent-evidence-{safe}.log"
        out_rel = f"steps/05-weapons/per_weapon/{safe}.json"
        if per_path.exists() and force:
            try:
                per_path.unlink()
            except Exception:
                pass
        return _run_single_with_retry(workdir, full_prompt, out_rel, log_path,
                                      _parse_ev, timeout, model, thinking, per_path)

    evidences: list[dict] = []
    if agent_fn is not None:
        # 测试注入: 串行即可 (逻辑并行, 测试串行等价)
        for n in candidate_names:
            evidences.append(_do_one(n))
    else:
        with concurrent.futures.ThreadPoolExecutor(max_workers=max_workers) as ex:
            futs = {}
            for n in candidate_names:
                futs[ex.submit(_do_one, n)] = n
                time.sleep(stagger)
            by_name: dict[str, dict] = {}
            for fut in concurrent.futures.as_completed(futs):
                n = futs[fut]
                by_name[n] = fut.result()
            evidences = [by_name[n] for n in candidate_names]

    # ---- ranking (串行) ----
    rank_prompt = build_ranking_prompt(sentences, evidences, fewshot_r)
    rank_path = outdir / "ranking.json"
    rank_log = outdir / "agent-ranking.log"
    rank_rel = "steps/05-weapons/ranking.json"

    def _parse_rank(d):
        return validate_ranking(d, candidate_names, evidences)

    if rank_path.exists() and not force:
        try:
            cand = json.loads(rank_path.read_text(encoding="utf-8"))
            ranking = _parse_rank(cand)
        except SystemExit:
            raise
        except Exception:
            ranking = None  # type: ignore
    else:
        ranking = None  # type: ignore

    if ranking is None:
        full_rank_prompt = (rank_prompt
                            + f"\n\n只写相对路径 `{rank_rel}`，禁 `..` 与绝对盘符。\n")
        if agent_fn is not None:
            try:
                raw_r = agent_fn("ranking", None, rank_prompt)
            except SystemExit:
                raise
            except Exception as e:
                _fail(f"ranking agent_fn fail: {e!r}")
            ranking = _parse_rank(raw_r)
            rank_path.write_text(json.dumps(ranking, ensure_ascii=False, indent=2) + "\n",
                                 encoding="utf-8")
        else:
            if rank_path.exists() and force:
                try:
                    rank_path.unlink()
                except Exception:
                    pass
            ranking = _run_single_with_retry(workdir, full_rank_prompt, rank_rel,
                                             rank_log, _parse_rank,
                                             timeout, model, thinking, rank_path)

    # ---- 合并落盘 (code only) ----
    ev_by = {e["name_en"]: e for e in evidences}
    ql = _quote_lookup(sentences)
    t1_out: list[dict] = []
    t2_out: list[dict] = []
    for tier_key, arr, out_arr in (("T1", ranking["t1"], t1_out), ("T2", ranking["t2"], t2_out)):
        for r in arr:
            name = r["name_en"]
            ev = ev_by.get(name)
            if ev is None:
                _fail(f"合并缺 evidence: {name!r} (缺件即 fail)")
            qs: list[str] = []
            for q in ev.get("quotes", []):
                if q not in qs:
                    qs.append(q)
            details = []
            for q in qs:
                hits = ql.get(q, [])
                h = hits[0] if hits else {"start": None, "end": None, "t": None,
                                          "context": q[:300]}
                if h.get("start") is not None and not isinstance(h.get("t"), int):
                    _fail(f"{name} quote_details t 非法: {q[:40]!r}")
                details.append({"quote": q, "start": h["start"], "end": h["end"],
                                "t": h["t"], "context": h["context"]})
            out_arr.append({"name_en": name, "count": len(qs), "tier": tier_key,
                            "quotes": qs, "analysis": str(ev.get("analysis", "")).strip(),
                            "note": str(r.get("note", "")).strip(),
                            "quote_details": details})
    # 自洽: T1+T2==candidates (ranking 已验, 此处再保)
    got = sorted([w["name_en"] for w in (t1_out + t2_out)])
    if got != sorted(candidate_names):
        _fail(f"T1+T2 须==candidates 自洽: 期望 {sorted(candidate_names)}, 实得 {got}")
    weapons = {"t1": sorted(t1_out, key=lambda x: x["name_en"]),
               "t2": sorted(t2_out, key=lambda x: x["name_en"])}
    (outdir / "weapons.json").write_text(
        json.dumps(weapons, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    (workdir / "outputs").mkdir(parents=True, exist_ok=True)
    (workdir / "outputs" / "weapons.json").write_text(
        json.dumps(weapons, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    return weapons
