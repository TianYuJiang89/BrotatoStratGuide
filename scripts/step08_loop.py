#!/usr/bin/env python3
"""Step08 agent loop (#64): frozen fewshot + discovery/wording.

Deterministic-first:
- 固定代码只做: prompt 组装 (任务手册 + 全量整句 + 一条/ ban 组) / 输出形状校验 /
  seeds+extra 逐字 (sentences lookup, 不信 agent) / 去重 / extra 与 seeds 不交 /
  桶间不重叠 (一句只进一坑) / quote_details 重建 (t/start/end/context 由 sentences lookup) /
  ban 反向 allowlist (坑证据不含新 grouping ban 名, scope 约束) / 落盘
  (candidates.json + wordings.json + per_pitfall/* + fewshot 快照 + 日志).
- agent judgment 只做: discovery (全量整句→candidates[{title建议,seeds≥1,extra}], N 不定,
  无事件空数组诚实交, completeness 归它) → wording×N (每条独立单 agent→
  {title,severity,why,how_to_avoid,reason,seeds,extra}, trap 须论证看着赚,
  take 已拿不算坑意图进 fewshot).
- 缺件/编 quote/编坑/ban 名进坑即 fail loud, 不回落不补空.

输入:
- fewshot: prompts/step08-pitfalls-fewshot.md (FROZEN 20-shot: 发现8+分级8+负例4)
- sentences: steps/01-sentences/sentences.json ([{id,text[,start,end],start_s,end_s,t}])
- grouping: steps/03-grouping/grouping.json (ban 组 scope 约束, 只读 ban 名)

输出:
- steps/08-pitfalls/candidates.json: [{title,seeds,extra}] (discovery, N 不定, 可空数组诚实交)
- steps/08-pitfalls/per_pitfall/<NN>.json: wording 原始 (validated)
- steps/08-pitfalls/wordings.json: [{title,severity,why,how_to_avoid,reason,seeds,extra}]
- steps/08-pitfalls/pitfalls.json (+ outputs/pitfalls.json):
  [{title,severity,why,how_to_avoid,reason,seeds,extra,quotes,quote_details}]
  (code 合并: quotes=seeds+extra 原序, quote_details 平行)
  - anchors/inferred/kind/anchor/quote/signals/N>=3/窗位规则全退役 (出现即 fail).
  - severity 三档保留 (码只验合法值, 质量靠人抽).
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

FEWSHOT_REL = "prompts/step08-pitfalls-fewshot.md"
VALID_SEVERITIES = {"fatal", "risky", "trap"}
# discovery 输出只活 title/seeds/extra (+pits wrapper); 其它全退役
RETIRED_DISCOVERY_FIELDS = ("signals", "count", "quote_details", "severity",
                            "why", "how_to_avoid", "reason",
                            "anchors", "inferred", "kind", "anchor", "quote")
# wording 输出只活 title/severity/why/how_to_avoid/reason/seeds/extra; 其它全退役
RETIRED_WORDING_FIELDS = ("anchors", "inferred", "kind", "anchor", "quote",
                          "signals", "count", "quote_details")


def _fail(msg: str) -> NoReturn:
    raise SystemExit(f"step08-loop FAIL: {msg}")


def load_fewshot() -> str:
    p = REPO / FEWSHOT_REL
    if not p.exists():
        _fail(f"missing {FEWSHOT_REL} (frozen fewshot 缺件即 fail, 不回落)")
    txt = p.read_text(encoding="utf-8")
    if "FROZEN" not in txt:
        _fail(f"{FEWSHOT_REL} 缺 FROZEN 头 (freeze 完整性 fail)")
    return txt


def _ban_names_from_grouping(grouping) -> list[str]:
    if not isinstance(grouping, list):
        return []
    out: list[str] = []
    for g in grouping:
        if isinstance(g, dict) and g.get("group") == "ban":
            n = g.get("name_en")
            if isinstance(n, str) and n.strip():
                out.append(n.strip())
    return sorted(set(out))


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


def build_discovery_prompt(sentences: list[dict], fewshot_text: str,
                           ban_names: list[str] | None = None) -> str:
    if not isinstance(sentences, list) or not sentences:
        _fail("sentences 为空 (缺件即 fail)")
    blob = _sentences_blob(sentences)
    ban_line = ""
    if ban_names:
        ban_line = ("\n\n## ban 组 scope 约束（坑不重复进，只读）\n\n"
                    + "grouping ban: " + ", ".join(ban_names)
                    + "\n坑证据 seeds/extra 不得含 ban 名原文（子串即 fail，码验）。\n")
    prompt = (
        fewshot_text
        + "\n\n## 该角色全量整句（含 start/end/t，原样全量，不截断）\n\n"
        + "```json\n" + blob + "\n```\n"
        + ban_line
        + "\n---\n\n# TASK_DISCOVERY（只发现，不分级；N 不定，无事件空数组诚实交）\n\n"
        + "## 输出契约（只输出一件 JSON 对象，不输出其它文字）\n\n"
        + '{"pits": [{"title": "<短标题，8字内，建议>", '
        + '"seeds": ["逐字，去重，≥1"], "extra": ["逐字，去重，可空，真坑外"]}, ...]}\n\n'
        + "- 每坑至少一句 seeds（≥1）；无事件则 `{\"pits\": []}` 诚实交，不硬凑。\n"
        + "- seeds/extra 须逐字等于上表某条 text，去重；extra 与 seeds 不交；跨坑不重叠（一句只进一坑）。编 quote / 空 seeds / 交叠 / 重叠即 fail。\n"
        + "- 无警告词真坑也收（事件同一性归你判）；利好句/已拿句/泛泛抱怨一律丢。take 系已拿不算坑（拿不是坑）。\n"
        + "- N 不定（码不卡 N，粒度靠人抽）。你不输出 severity/why/how_to_avoid/reason/count。缺件即 fail，不回落不补空。\n"
    )
    return prompt


def build_wording_prompt(pit: dict, sentences: list[dict], fewshot_text: str,
                         ban_names: list[str] | None = None) -> str:
    if not isinstance(pit, dict) or not pit.get("title"):
        _fail("TASK_WORDING 缺坑 (缺件即 fail)")
    if not isinstance(sentences, list) or not sentences:
        _fail("sentences 为空 (缺件即 fail)")
    blob = _sentences_blob(sentences)
    b_blob = json.dumps(pit, ensure_ascii=False, indent=2)
    ban_line = ""
    if ban_names:
        ban_line = ("\n\n## ban 组 scope 约束（坑不重复进，只读）\n\n"
                    + "grouping ban: " + ", ".join(ban_names)
                    + "\n本条 seeds/extra 不得含 ban 名原文（子串即 fail，码验）。\n")
    prompt = (
        fewshot_text
        + "\n\n## 该角色全量整句（含 start/end/t，原样全量，不截断）\n\n"
        + "```json\n" + blob + "\n```\n\n"
        + "## 本条（只写这一坑的分级+人话，其它坑一律不写）\n\n"
        + "```json\n" + b_blob + "\n```\n"
        + ban_line
        + "\n---\n\n# TASK_WORDING（只写本条分级+人话，不改坑数；trap 须论证看着赚）\n\n"
        + f"TASK_PIT: {pit.get('title')}\n\n"
        + "## 输出契约（只输出一件 JSON 对象，不输出其它文字）\n\n"
        + '{"title": "<短标题，8字内>", "severity": "fatal/risky/trap", '
        + '"why": "人话一句：代价+短引", "how_to_avoid": "人话一句：动作+条件", '
        + '"reason": "人话一句：为什么合成一条+扩展凭什么跟走", '
        + '"seeds": ["逐字，去重，≥1"], "extra": ["逐字，去重，可空"]}\n\n'
        + "- severity 绝对档（fatal=会崩盘，risky=会亏，trap=看似赚实则亏）；trap 须在 reason 论证看着赚在哪，不然一律按 risky（意图进 fewshot，码只验合法值）。\n"
        + "- why/how_to_avoid/reason 各人话一句（≥8字）；why 须带短引（短引须出自本条 seeds+extra 逐字）；整句复制某条 quote 当 why 即 fail。\n"
        + "- seeds 非空（≥1，逐字），extra 可空（逐字，真坑外）；extra 与 seeds 不交；编 quote / 空 seeds / 交叠即 fail。\n"
        + "- take 系已拿不算坑（拿不是坑）；ban 组不重复进（证据含 ban 名即 fail，码验）。缺件即 fail，不回落不补空。\n"
    )
    return prompt


def _check_verbatim(who: str, quotes: list[str], sent_texts: set[str]) -> None:
    for q in quotes:
        if q not in sent_texts:
            _fail(f"{who} 编 quote 即 fail: {q[:60]!r} 不在整句内 (逐字)")


def _check_ban(who: str, quotes: list[str], ban_names: list[str]) -> None:
    for b in ban_names or []:
        bl = b.lower()
        if not bl:
            continue
        for q in quotes:
            if bl in q.lower():
                _fail(f"{who} 坑证据含 ban 名即 fail (scope 约束, 坑不重复进): {b!r} in {q[:60]!r}")


def validate_discovery(data: dict, sentences: list[dict],
                       ban_names: list[str] | None = None) -> dict:
    if not isinstance(data, dict):
        _fail(f"discovery 输出须为 JSON 对象, got {type(data)}")
    for f in RETIRED_DISCOVERY_FIELDS:
        if f in data:
            _fail(f"discovery 字段 {f} 已退役 (#64, 出现即 fail)")
    if "pits" not in data:
        _fail("discovery 缺 pits (缺件即 fail, 不补空)")
    pits = data["pits"]
    if not isinstance(pits, list):
        _fail("discovery pits 须为数组 (N 不定, 无事件空数组诚实交)")
    # N 不卡 (可空数组); 粒度靠人抽
    sent_texts: set[str] = {s["text"] for s in sentences if isinstance(s, dict) and isinstance(s.get("text"), str)}
    seen_titles: set[str] = set()
    seen_quotes: set[str] = set()
    out: list[dict] = []
    for i, p in enumerate(pits):
        if not isinstance(p, dict):
            _fail(f"discovery pits[{i}] 须为对象")
        for k in ("title", "seeds", "extra"):
            if k not in p:
                _fail(f"discovery pits[{i}] 缺 {k} (缺件即 fail)")
        title = p.get("title")
        seeds = p.get("seeds")
        extra = p.get("extra")
        if not isinstance(title, str) or not title.strip():
            _fail(f"discovery pits[{i}] title 须为非空短标题")
        title = title.strip()
        if title in seen_titles:
            _fail(f"discovery title 须互异 (重复): {title!r}")
        seen_titles.add(title)
        if not isinstance(seeds, list) or not seeds or any(not isinstance(q, str) for q in seeds):
            _fail(f"discovery {title} seeds 须为非空字符串数组 (空证据即 fail, 每坑≥1)")
        if not isinstance(extra, list) or any(not isinstance(q, str) for q in extra):
            _fail(f"discovery {title} extra 须字符串数组 (无则[])")
        if len(seeds) != len(set(seeds)):
            _fail(f"discovery {title} seeds 须去重")
        if len(extra) != len(set(extra)):
            _fail(f"discovery {title} extra 须去重")
        if set(seeds) & set(extra):
            _fail(f"discovery {title} seeds/extra 须不交 (交叠即 fail)")
        _check_verbatim(f"discovery {title}", [q for q in seeds + extra if isinstance(q, str)], sent_texts)
        for q in list(seeds) + list(extra):
            if q in seen_quotes:
                _fail(f"discovery 桶间不重叠即 fail: {q[:60]!r} 已进他坑")
        for q in list(seeds) + list(extra):
            seen_quotes.add(q)
        _check_ban(f"discovery {title}", [q for q in seeds + extra if isinstance(q, str)], ban_names or [])
        for f in RETIRED_DISCOVERY_FIELDS:
            if f in p:
                _fail(f"discovery {title} 字段 {f} 已退役 (#64, 出现即 fail)")
        out.append({"title": title, "seeds": list(seeds), "extra": list(extra)})
    return {"pits": out}


def validate_wording(data: dict, pit: dict, sentences: list[dict],
                     ban_names: list[str] | None = None) -> dict:
    expect_title = (pit or {}).get("title") if isinstance(pit, dict) else None
    if not expect_title:
        _fail("wording 缺坑 title (缺件即 fail)")
    if not isinstance(data, dict):
        _fail(f"{expect_title} wording 输出须为 JSON 对象, got {type(data)}")
    for f in RETIRED_WORDING_FIELDS:
        if f in data:
            _fail(f"{expect_title} 字段 {f} 已退役 (#64, 出现即 fail)")
    for k in ("title", "severity", "why", "how_to_avoid", "reason", "seeds", "extra"):
        if k not in data:
            _fail(f"{expect_title} wording 缺 {k} (缺件即 fail, 不补空)")
    title = data.get("title")
    if not isinstance(title, str) or not title.strip():
        _fail(f"{expect_title} wording title 须为非空短标题")
    title = title.strip()
    # title 允许精修 (建议→终稿), 不强制一字不差; 自洽靠 N+顺序, 标题精修归 judgment
    if data.get("severity") not in VALID_SEVERITIES:
        _fail(f"{title} wording severity 须为 fatal/risky/trap 之一, got {data.get('severity')!r}")
    for k in ("why", "how_to_avoid", "reason"):
        v = data.get(k)
        if not isinstance(v, str) or len(v.strip()) < 8:
            _fail(f"{title} wording {k} 须人话一句≥8字")
        v = v.strip()
        if v in {s.get("text") for s in sentences if isinstance(s, dict)}:
            _fail(f"{title} wording {k} 整句复制 quote 即 fail (小结须≠原文)")
    seeds = data.get("seeds")
    extra = data.get("extra")
    if not isinstance(seeds, list) or not seeds or any(not isinstance(q, str) for q in seeds):
        _fail(f"{title} wording seeds 须为非空字符串数组 (空证据即 fail)")
    if not isinstance(extra, list) or any(not isinstance(q, str) for q in extra):
        _fail(f"{title} wording extra 须字符串数组 (无则[])")
    if len(seeds) != len(set(seeds)):
        _fail(f"{title} wording seeds 须去重")
    if len(extra) != len(set(extra)):
        _fail(f"{title} wording extra 须去重")
    if set(seeds) & set(extra):
        _fail(f"{title} wording seeds/extra 须不交 (交叠即 fail)")
    sent_texts: set[str] = {s["text"] for s in sentences if isinstance(s, dict) and isinstance(s.get("text"), str)}
    _check_verbatim(f"{title} wording", [q for q in seeds + extra if isinstance(q, str)], sent_texts)
    _check_ban(f"{title} wording", [q for q in seeds + extra if isinstance(q, str)], ban_names or [])
    # why 短引? 08 why 人话+短引? 沿 05/06: why 须带短引? Issue 未明说 why 须短引, 但分级例 why 均带短引.
    # 为与 05/06 一致且可机检, 要求 why 须含短引标记? 不, Issue 说 "N/粒度/trap论证质量机检不管",
    # 且回归只列 自洽/空证据/ban名/extra交叠, 未列短引. 故 why 短引不做码检 (意图进 fewshot, 质量靠人抽).
    # 此处只保非空人话, 不卡短引.
    for f in RETIRED_WORDING_FIELDS:
        if f in data:
            _fail(f"{title} 字段 {f} 已退役 (#64, 出现即 fail)")
    return {"title": title,
            "severity": str(data.get("severity")),
            "why": str(data.get("why")).strip(),
            "how_to_avoid": str(data.get("how_to_avoid")).strip(),
            "reason": str(data.get("reason")).strip(),
            "seeds": list(seeds), "extra": list(extra)}


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
        req = {"id": "step08-1", "type": "prompt", "message": prompt_text}
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


def run_step08_loop(workdir, sentences, grouping=None, agent_fn=None,
                    timeout: float = 1800.0, force: bool = False,
                    max_workers: int = 4, stagger: float = 5.0,
                    model=None, thinking: str = "medium"):
    """08 两段调度: discovery(串行) → wording×N(并行) → 合并落盘.

    agent_fn: 测试注入. 为 None 时走真 RPC spawn.
      - discovery: agent_fn("discovery", None, prompt) -> dict {"pits": [...]}
      - wording: agent_fn("wording", title_or_idx, prompt) -> dict
      测试请传三参 (kind, name, prompt).
    grouping: 03 grouping 列表 (ban scope 约束, 只读 ban 名); None 则不验 ban.
    """
    fewshot = load_fewshot()
    ban_names = _ban_names_from_grouping(grouping)
    outdir = workdir / "steps" / "08-pitfalls"
    per_dir = outdir / "per_pitfall"
    outdir.mkdir(parents=True, exist_ok=True)
    per_dir.mkdir(parents=True, exist_ok=True)
    # fewshot 运行快照进工作区 (审计只读工作区约定路径; 快照与 repo FROZEN 文件逐字节一致, check 验相等)
    (outdir / "fewshot.md").write_text(fewshot, encoding="utf-8", newline="\n")

    # ---- discovery (串行, N 不定, 可空数组诚实交) ----
    disc_prompt = build_discovery_prompt(sentences, fewshot, ban_names)
    cand_path = outdir / "candidates.json"
    disc_raw_path = outdir / "discovery.json"
    disc_log = outdir / "agent-discovery.log"
    disc_rel = "steps/08-pitfalls/discovery.json"

    def _parse_disc(d):
        return validate_discovery(d, sentences, ban_names)

    disc = None
    if cand_path.exists() and disc_raw_path.exists() and not force:
        try:
            disc = _parse_disc(json.loads(disc_raw_path.read_text(encoding="utf-8")))
        except SystemExit:
            raise
        except Exception:
            disc = None  # type: ignore
    if disc is None:
        full_disc = disc_prompt + f"\n\n只写相对路径 `{disc_rel}`，禁 `..` 与绝对盘符。\n"
        if agent_fn is not None:
            try:
                raw_d = agent_fn("discovery", None, disc_prompt)
            except TypeError:
                _fail("agent_fn 须为三参 (kind, name_en, prompt)")
            except SystemExit:
                raise
            except Exception as e:
                _fail(f"discovery agent_fn fail: {e!r}")
            disc = _parse_disc(raw_d)
            disc_raw_path.write_text(json.dumps(disc, ensure_ascii=False, indent=2) + "\n",
                                     encoding="utf-8")
        else:
            if disc_raw_path.exists() and force:
                try:
                    disc_raw_path.unlink()
                except Exception:
                    pass
            disc = _run_single_with_retry(workdir, full_disc, disc_rel, disc_log,
                                          _parse_disc, timeout, model, thinking,
                                          disc_raw_path)
    pits_raw: list[dict] = list(disc.get("pits", []))

    # discovery 回填 candidates.json (code: 去重保序已验, 直接落盘; quote_details 只活 pitfalls)
    candidates: list[dict] = [{"title": p["title"], "seeds": list(p["seeds"]),
                               "extra": list(p["extra"])} for p in pits_raw]
    cand_path.write_text(json.dumps(candidates, ensure_ascii=False, indent=2) + "\n",
                         encoding="utf-8")

    # ---- wording×N (并行, 每条独立单 agent) ----
    def _do_one(pit: dict, idx: int):
        tag = f"{idx:02d}"
        per_path = per_dir / f"{tag}.json"
        w_prompt = build_wording_prompt(pit, sentences, fewshot_text=fewshot,
                                        ban_names=ban_names)

        def _parse_w(d):
            return validate_wording(d, pit, sentences, ban_names)

        if per_path.exists() and not force:
            try:
                return _parse_w(json.loads(per_path.read_text(encoding="utf-8")))
            except SystemExit:
                raise
            except Exception:
                pass
        full_prompt = (w_prompt
                       + f"\n\n只写相对路径 `steps/08-pitfalls/per_pitfall/{tag}.json`，"
                         f"禁 `..` 与绝对盘符。\n")
        if agent_fn is not None:
            try:
                raw_w = agent_fn("wording", pit.get("title"), w_prompt)
            except SystemExit:
                raise
            except Exception as e:
                _fail(f"wording {pit.get('title')} agent_fn fail: {e!r}")
            parsed = _parse_w(raw_w)
            per_path.write_text(json.dumps(parsed, ensure_ascii=False, indent=2) + "\n",
                                encoding="utf-8")
            return parsed
        log_path = outdir / f"agent-wording-{tag}.log"
        out_rel = f"steps/08-pitfalls/per_pitfall/{tag}.json"
        if per_path.exists() and force:
            try:
                per_path.unlink()
            except Exception:
                pass
        return _run_single_with_retry(workdir, full_prompt, out_rel, log_path,
                                      _parse_w, timeout, model, thinking, per_path)

    wordings: list[dict] = []
    if agent_fn is not None:
        for _i, _p in enumerate(pits_raw):
            wordings.append(_do_one(_p, _i))
    else:
        with concurrent.futures.ThreadPoolExecutor(max_workers=max_workers) as ex:
            futs = {}
            for _i, _p in enumerate(pits_raw):
                futs[ex.submit(_do_one, _p, _i)] = _i
                time.sleep(stagger)
            by_i: dict[int, dict] = {}
            for fut in concurrent.futures.as_completed(futs):
                _i = futs[fut]
                by_i[_i] = fut.result()
            wordings = [by_i[_i] for _i in range(len(pits_raw))]

    # 自洽: wordings N == candidates N (标题允许精修, 顺序对齐, 数量必须一致)
    if len(wordings) != len(candidates):
        _fail(f"wordings N 须==candidates N 自洽: 期望 {len(candidates)}, 实得 {len(wordings)}")
    # 桶间不重叠 (跨坑全局, wording 最终口径再保一次)
    _all_q: list[str] = []
    for w in wordings:
        for q in list(w.get("seeds", [])) + list(w.get("extra", [])):
            if q in _all_q:
                _fail(f"wording 桶间不重叠即 fail: {q[:60]!r} 已进他坑")
            _all_q.append(q)
    wordings_sorted = list(wordings)
    (outdir / "wordings.json").write_text(
        json.dumps(wordings_sorted, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")

    # ---- 合并落盘 (code only) ----
    ql = _quote_lookup(sentences)
    pitfalls: list[dict] = []
    for w in wordings_sorted:
        seeds: list[str] = list(w.get("seeds", []))
        extra: list[str] = list(w.get("extra", []))
        qs: list[str] = []
        for q in seeds + extra:
            if q not in qs:
                qs.append(q)
        if qs[:len(seeds)] != seeds:
            _fail(f"合并 seeds 原序即 fail: {w.get('title')}")
        details = []
        for q in qs:
            hits = ql.get(q, [])
            h = hits[0] if hits else {"start": None, "end": None, "t": None,
                                      "context": q[:300]}
            if h.get("start") is not None and not isinstance(h.get("t"), int):
                _fail(f"{w.get('title')} quote_details t 非法: {q[:40]!r}")
            details.append({"quote": q, "start": h["start"], "end": h["end"],
                            "t": h["t"], "context": h["context"]})
        pitfalls.append({"title": w.get("title"), "severity": w.get("severity"),
                         "why": str(w.get("why", "")).strip(),
                         "how_to_avoid": str(w.get("how_to_avoid", "")).strip(),
                         "reason": str(w.get("reason", "")).strip(),
                         "seeds": seeds, "extra": extra,
                         "quotes": qs, "quote_details": details})
    (outdir / "pitfalls.json").write_text(
        json.dumps(pitfalls, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    (workdir / "outputs").mkdir(parents=True, exist_ok=True)
    (workdir / "outputs" / "pitfalls.json").write_text(
        json.dumps(pitfalls, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    return pitfalls
