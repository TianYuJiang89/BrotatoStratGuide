#!/usr/bin/env python3
"""Step07 agent loop (#65): frozen fewshot + selection/wording.

Deterministic-first:
- 固定代码只做: prompt 组装 (任务手册 + 全量整句 + 上游结果摘要, 不喂 count/quotes 全量,
  不读 verbs, 不做 verified/断层/动词表) / 输出形状校验 / 逐字 (sentences lookup, 不信 agent) /
  名在表 (升级名在 ratings term_en, 商店名在 grouping candidates) / 去重 /
  quote_details 重建 (t/start/end/context 由 sentences lookup) /
  自洽 (shop∩T1=∅、shop∩ban=∅、upgrades/shop 非空) / 落盘
  (selection.json + priorities.json + per_item/* + fewshot 快照 + 日志).
- agent judgment 只做: selection 通览定双 TopN (grouping+ratings+weapons+phases+全量整句→
  {upgrades[{name,quotes}],shop[{name,quotes}]}, N 动态, 保底意图, S/A 优先 B 可例外须论证,
  T1/ban 不进 shop 意图进 fewshot) → wording×N (每项独立单 agent→{why,how_to_get},
  数字不丢, 未提空出).
- 缺件/编 quote/编数字/幻觉名/ban 入 TopN/T1 入 shop 即 fail loud, 不回落不补空.

输入:
- fewshot: prompts/step07-priorities-fewshot.md (FROZEN 20-shot: 选择8+文案8+负例4)
- sentences: steps/01-sentences/sentences.json ([{id,text[,start,end],start_s,end_s,t}])
- grouping: steps/03-grouping/grouping.json (四组, 只读 name_en/group/note, 不读 count/quotes)
- ratings: steps/04-attributes/ratings.json (39 全量, 只读 term_en/rating)
- weapons: steps/05-weapons/weapons.json ({t1[],t2[]}, 只读 T1 名单做 shop∩T1)
- phases: steps/06-phases/phases.json (运营波次, 只读 phase/waves/goal 备查)

输出:
- steps/07-priorities/selection.json: {upgrades[{name,quotes}],shop[{name,quotes}]} (selection 原始, N 动态非空)
- steps/07-priorities/per_item/<NN>.json: wording 原始 {name,why,how_to_get} (N==selection, 00..N-1, upgrades 先 shop 后)
- steps/07-priorities/priorities.json (+ outputs/priorities.json):
  {upgrades[],shop[]} 每项 {name,kind,why,how_to_get,quotes,quote_details} (code 合并)
  - count/verified/verb/analysis/断层/动词表全退役 (出现即 fail).
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

FEWSHOT_REL = "prompts/step07-priorities-fewshot.md"
# selection 只活 name/quotes; 其它全退役 (why/how_to_get 归 wording, count/details 只活代码)
RETIRED_SELECTION_FIELDS = ("count", "why", "how_to_get", "analysis", "quote_details",
                            "kind", "group", "note", "reason", "tier", "confidence",
                            "inferred", "verb", "verb_type", "has_verb", "mapped_to",
                            "surface_verb", "surface_word", "verified", "signals",
                            "anchors", "severity", "title", "seeds", "extra")
# wording 只活 name/why/how_to_get; 其它全退役 (quotes 归 selection, count/details 只活代码)
RETIRED_WORDING_FIELDS = ("quotes", "analysis", "count", "quote_details", "tier",
                          "confidence", "inferred", "kind", "group", "note", "reason",
                          "signals", "anchors", "severity", "title", "seeds", "extra",
                          "verb", "verified")
NOTE_SHORT_RE = re.compile(r'原话["“]([^"”]+)["”]')


def _fail(msg: str) -> NoReturn:
    raise SystemExit(f"step07-loop FAIL: {msg}")


def load_fewshot() -> str:
    p = REPO / FEWSHOT_REL
    if not p.exists():
        _fail(f"missing {FEWSHOT_REL} (frozen fewshot 缺件即 fail, 不回落)")
    txt = p.read_text(encoding="utf-8")
    if "FROZEN" not in txt:
        _fail(f"{FEWSHOT_REL} 缺 FROZEN 头 (freeze 完整性 fail)")
    return txt


def _t1_names_from_weapons(weapons) -> list[str]:
    if not isinstance(weapons, dict):
        return []
    out: list[str] = []
    for w in (weapons.get("t1") or []):
        if isinstance(w, dict) and isinstance(w.get("name_en"), str) and w.get("name_en").strip():
            out.append(w.get("name_en").strip())
    return sorted(set(out))


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


def _cand_names_from_grouping(grouping) -> list[str]:
    if not isinstance(grouping, list):
        return []
    return sorted({g.get("name_en") for g in grouping
                   if isinstance(g, dict) and isinstance(g.get("name_en"), str)})


def _rating_names_from_ratings(ratings) -> list[str]:
    if not isinstance(ratings, list):
        return []
    return sorted({r.get("term_en") for r in ratings
                   if isinstance(r, dict) and isinstance(r.get("term_en"), str)})


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


def build_selection_prompt(sentences: list[dict], grouping: list[dict],
                           ratings: list[dict], weapons: dict,
                           phases: list[dict], fewshot_text: str) -> str:
    if not isinstance(sentences, list) or not sentences:
        _fail("sentences 为空 (缺件即 fail)")
    if not isinstance(grouping, list) or not grouping:
        _fail("grouping 为空 (缺件即 fail)")
    if not isinstance(ratings, list) or not ratings:
        _fail("ratings 为空 (缺件即 fail)")
    blob = _sentences_blob(sentences)
    # 上游摘要: 只喂名单+定性, 不喂 count/quotes (禁断层码切, 拿 quote 说话由 agent 从整句自捞)
    grp_sum = [{"name_en": g.get("name_en"), "group": g.get("group"),
                "note": str(g.get("note", ""))[:120]}
               for g in grouping if isinstance(g, dict)]
    rat_sum = [{"term_en": r.get("term_en"), "rating": r.get("rating")}
               for r in ratings if isinstance(r, dict)]
    t1_names = _t1_names_from_weapons(weapons)
    ban_names = _ban_names_from_grouping(grouping)
    ph_sum = [{"phase": p.get("phase"), "waves": p.get("waves", ""),
               "goal": str(p.get("goal", ""))[:120]}
              for p in (phases or []) if isinstance(p, dict)][:20]
    grp_blob = json.dumps(grp_sum, ensure_ascii=False, indent=2)
    rat_blob = json.dumps(rat_sum, ensure_ascii=False, indent=2)
    w_blob = json.dumps({"t1": t1_names,
                         "t2": [w.get("name_en") for w in ((weapons or {}).get("t2") or [])
                                if isinstance(w, dict)]}, ensure_ascii=False)
    ph_blob = json.dumps(ph_sum, ensure_ascii=False, indent=2)
    ban_line = ""
    if ban_names:
        ban_line += "\n## ban 组（永不进 shop，只读）\n\n" + ", ".join(ban_names) + "\n"
    if t1_names:
        ban_line += "\n## T1 武器（永不进 shop，只读）\n\n" + ", ".join(t1_names) + "\n"
    prompt = (
        fewshot_text
        + "\n\n## 该角色全量整句（含 start/end/t，原样全量，不截断）\n\n"
        + "```json\n" + blob + "\n```\n\n"
        + "## 03 grouping 四组（建议，可推翻，拿 quote 说话）\n\n```json\n" + grp_blob + "\n```\n\n"
        + "## 04 ratings（升级只认 term_en，S/A 优先 B 可例外）\n\n```json\n" + rat_blob + "\n```\n\n"
        + "## 05 weapons（T1 名单，只读，shop∩T1=∅）\n\n```json\n" + w_blob + "\n```\n\n"
        + "## 06 phases（节奏备查）\n\n```json\n" + ph_blob + "\n```\n"
        + ban_line
        + "\n---\n\n# TASK_SELECTION（只定双 TopN 名单+证据，不写文案；N 由你定，ban/T1 永不出局）\n\n"
        + "## 输出契约（只输出一件 JSON 对象，不输出其它文字）\n\n"
        + '{"upgrades": [{"name": "<04 term_en 一字不差>", "quotes": ["逐字，去重，非空"]}], '
        + '"shop": [{"name": "<grouping candidates 一字不差>", "quotes": ["逐字，去重，非空"]}]}\n\n'
        + "- upgrades ≥1 且 shop ≥1（Top1 意图由你保，码只验非空，不验断层）。\n"
        + "- S/A 优先但 B 级可例外（例外须在文案 why 论证，此处只管给足 quotes 证据）。\n"
        + "- 可推翻 grouping 建议，拿 quote 说话；ban 件/T1 武器名永不进 shop（交集码验）。\n"
        + "- quotes 须逐字等于全量整句某条 text，去重，每条非空；编 quote / 幻觉名 / 空 TopN 即 fail。\n"
        + "- 你不输出 why/how_to_get/count（只定名单+证据）。缺件即 fail，不回落不补空。\n"
    )
    return prompt


def build_wording_prompt(item: dict, sentences: list[dict], fewshot_text: str) -> str:
    if not isinstance(item, dict) or not item.get("name"):
        _fail("TASK_WORDING 缺项 (缺件即 fail)")
    if not isinstance(sentences, list) or not sentences:
        _fail("sentences 为空 (缺件即 fail)")
    blob = _sentences_blob(sentences)
    b_blob = json.dumps(item, ensure_ascii=False, indent=2)
    prompt = (
        fewshot_text
        + "\n\n## 该角色全量整句（含 start/end/t，原样全量，不截断）\n\n"
        + "```json\n" + blob + "\n```\n\n"
        + "## 本项（只写这一项的文案，其它项一律不写）\n\n"
        + "```json\n" + b_blob + "\n```\n\n"
        + "\n---\n\n# TASK_WORDING（只写本项文案，不改名单；数字不丢，未提空出）\n\n"
        + f"TASK_ITEM: {item.get('name')}\n\n"
        + "## 输出契约（只输出一件 JSON 对象，不输出其它文字）\n\n"
        + '{"name": "<与 TASK_ITEM 一字不差>", "why": "≤120字人话+短引", '
        + '"how_to_get": "≤120字人话，原话数字不丢"}\n\n'
        + "- why 人话一句+短引（短引须逐字出自本项 quotes）；how_to_get 人话一句（原话数字不丢，未提空出不脑补）。\n"
        + "- 数字不丢：why/how_to_get 里每个 ≥2 位数字须逐字出自本项 quotes（编数字即 fail，码验子串）。\n"
        + "- 整句复制某条 quote 当 why/how_to_get 即 fail（小结须≠原文）。\n"
        + "- B 级例外须在 why 写清为什么例外。缺件即 fail，不回落不补空。\n"
    )
    return prompt


def _check_verbatim(who: str, quotes: list[str], sent_texts: set[str]) -> None:
    for q in quotes:
        if q not in sent_texts:
            _fail(f"{who} 编 quote 即 fail: {q[:60]!r} 不在整句内 (逐字)")


def _note_shorts(text: str) -> list[str]:
    return [s.strip() for s in NOTE_SHORT_RE.findall(text or "") if s.strip()]


def _check_numbers(who: str, text: str, quotes: list[str]) -> None:
    """编数字即 fail: why/how_to_get 里每个 ≥2 位数字须出自本项 quotes (子串码验)."""
    if not isinstance(text, str) or not text:
        return
    joined = " ".join(q for q in quotes if isinstance(q, str))
    for m in re.finditer(r"\d+", text):
        tok = m.group(0)
        if len(tok) < 2:
            continue
        if tok not in joined:
            _fail(f"{who} 编数字即 fail: {tok!r} 不在 quotes 内 (逐字，原话数字不丢，未提空出)")


def validate_selection(data: dict, sentences: list[dict],
                       grouping: list[dict], ratings: list[dict],
                       weapons: dict) -> dict:
    if not isinstance(data, dict):
        _fail(f"selection 输出须为 JSON 对象, got {type(data)}")
    for f in RETIRED_SELECTION_FIELDS:
        if f in data:
            _fail(f"selection 字段 {f} 已退役 (#65, 出现即 fail)")
    for k in ("upgrades", "shop"):
        if k not in data:
            _fail(f"selection 缺 {k} (缺件即 fail, 不补空)")
    ups = data["upgrades"]
    shs = data["shop"]
    if not isinstance(ups, list) or not ups:
        _fail("selection upgrades 须为非空数组 (N 动态由 agent 定, 码只验非空)")
    if not isinstance(shs, list) or not shs:
        _fail("selection shop 须为非空数组 (N 动态由 agent 定, 码只验非空)")
    sent_texts: set[str] = {s.get("text") for s in sentences
                             if isinstance(s, dict) and isinstance(s.get("text"), str)}
    cand_names = set(_cand_names_from_grouping(grouping))
    ban_names = set(_ban_names_from_grouping(grouping))
    t1_names = set(_t1_names_from_weapons(weapons))
    rating_names = set(_rating_names_from_ratings(ratings))
    seen: set[str] = set()
    out_ups: list[dict] = []
    out_shop: list[dict] = []
    for key, arr, allowed in (("upgrades", ups, rating_names),
                              ("shop", shs, cand_names)):
        if not isinstance(arr, list):
            _fail(f"selection {key} 须为数组")
        for e in arr:
            if not isinstance(e, dict):
                _fail(f"selection {key} 条目须为对象")
            for k in ("name", "quotes"):
                if k not in e:
                    _fail(f"selection {key} 缺 {k} (缺件即 fail, 不补空)")
            for f in RETIRED_SELECTION_FIELDS:
                if f in e:
                    _fail(f"selection {e.get('name')} 字段 {f} 已退役 (#65, 出现即 fail)")
            nm = e.get("name")
            if not isinstance(nm, str) or not nm.strip():
                _fail(f"selection {key} name 须为非空字符串")
            nm = nm.strip()
            if nm in seen:
                _fail(f"selection {nm!r} 重复 (upgrades+shop 去重)")
            seen.add(nm)
            if nm not in allowed:
                _fail(f"selection 幻觉名即 fail: {nm!r} 不在"
                      f"{'ratings' if key == 'upgrades' else 'grouping candidates'}内")
            if key == "shop":
                if nm in ban_names:
                    _fail(f"selection ban 件禁入 TopN: {nm!r} (拿 quote 说话也不许进)")
                if nm in t1_names:
                    _fail(f"selection T1 武器禁入 shop: {nm!r} (shop∩T1=∅, 码验交集)")
            qs = e.get("quotes")
            if not isinstance(qs, list) or not qs or any(not isinstance(q, str) for q in qs):
                _fail(f"selection {nm} 空证据即 fail (quotes 须非空)")
            if len(qs) != len(set(qs)):
                _fail(f"selection {nm} quotes 须去重")
            _check_verbatim(f"selection {nm}", [q for q in qs if isinstance(q, str)], sent_texts)
            if key == "upgrades":
                out_ups.append({"name": nm, "quotes": list(qs)})
            else:
                out_shop.append({"name": nm, "quotes": list(qs)})
    return {"upgrades": out_ups, "shop": out_shop}


def validate_wording(data: dict, item: dict, sentences: list[dict]) -> dict:
    expect_name = (item or {}).get("name") if isinstance(item, dict) else None
    if not expect_name:
        _fail("wording 缺项 name (缺件即 fail)")
    if not isinstance(data, dict):
        _fail(f"{expect_name} wording 输出须为 JSON 对象, got {type(data)}")
    for f in RETIRED_WORDING_FIELDS:
        if f in data:
            _fail(f"{expect_name} 字段 {f} 已退役 (#65, 出现即 fail)")
    for k in ("name", "why", "how_to_get"):
        if k not in data:
            _fail(f"{expect_name} wording 缺 {k} (缺件即 fail, 不补空)")
    if data.get("name") != expect_name:
        _fail(f"wording name 须一字不差: 期望 {expect_name!r}, 实得 {data.get('name')!r}")
    item_quotes = list((item or {}).get("quotes") or [])
    sent_texts: set[str] = {s.get("text") for s in sentences
                 if isinstance(s, dict) and isinstance(s.get("text"), str)}
    why = data.get("why")
    how = data.get("how_to_get")
    if not isinstance(why, str) or len(why.strip()) < 8:
        _fail(f"{expect_name} wording why 须人话一句≥8字")
    why = why.strip()
    if not isinstance(how, str) or len(how.strip()) < 2:
        _fail(f"{expect_name} wording how_to_get 缺件即 fail")
    how = how.strip()
    if len(why) > 300:
        _fail(f"{expect_name} wording why 过长 (须≤300), got {len(why)}")
    if len(how) > 300:
        _fail(f"{expect_name} wording how_to_get 过长 (须≤300), got {len(how)}")
    if why in sent_texts or why in item_quotes:
        _fail(f"{expect_name} wording why 整句复制 quote 即 fail (小结须≠原文)")
    if how in sent_texts or how in item_quotes:
        _fail(f"{expect_name} wording how_to_get 整句复制 quote 即 fail (小结须≠原文)")
    shorts = _note_shorts(why)
    if not shorts:
        _fail(f"{expect_name} wording why 缺短引标记 原话\"...\" (人话须带逐字短引, 缺件即 fail)")
    for s in shorts:
        if not any(s in q for q in item_quotes if isinstance(q, str)):
            _fail(f"{expect_name} wording why 短引须逐字出自 quotes: {s[:60]!r} 改写/编造即 fail")
    _check_numbers(f"{expect_name} wording", why + " " + how, item_quotes)
    for f in RETIRED_WORDING_FIELDS:
        if f in data:
            _fail(f"{expect_name} 字段 {f} 已退役 (#65, 出现即 fail)")
    return {"name": expect_name, "why": why, "how_to_get": how}


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
        req = {"id": "step07-1", "type": "prompt", "message": prompt_text}
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


def run_step07_loop(workdir, sentences, grouping, ratings, weapons, phases,
                    agent_fn=None, timeout: float = 1800.0, force: bool = False,
                    max_workers: int = 4, stagger: float = 5.0,
                    model=None, thinking: str = "medium"):
    """07 两段调度: selection(串行) → wording×N(并行) → 合并落盘.

    agent_fn: 测试注入. 为 None 时走真 RPC spawn.
      - selection: agent_fn("selection", None, prompt) -> dict
      - wording: agent_fn("wording", name, prompt) -> dict
    """
    fewshot = load_fewshot()
    outdir = workdir / "steps" / "07-priorities"
    per_dir = outdir / "per_item"
    outdir.mkdir(parents=True, exist_ok=True)
    per_dir.mkdir(parents=True, exist_ok=True)
    (outdir / "fewshot.md").write_text(fewshot, encoding="utf-8", newline="\n")

    # ---- selection (串行, 通览定双 TopN) ----
    sel_prompt = build_selection_prompt(sentences, grouping, ratings, weapons or {},
                                        phases or [], fewshot)
    sel_path = outdir / "selection.json"
    sel_log = outdir / "agent-selection.log"
    sel_rel = "steps/07-priorities/selection.json"

    def _parse_sel(d):
        return validate_selection(d, sentences, grouping, ratings, weapons or {})

    sel = None
    if sel_path.exists() and not force:
        try:
            sel = _parse_sel(json.loads(sel_path.read_text(encoding="utf-8")))
        except SystemExit:
            raise
        except Exception:
            sel = None  # type: ignore
    if sel is None:
        full_sel = sel_prompt + f"\n\n只写相对路径 `{sel_rel}`，禁 `..` 与绝对盘符。\n"
        if agent_fn is not None:
            try:
                raw_s = agent_fn("selection", None, sel_prompt)
            except TypeError:
                _fail("agent_fn 须为三参 (kind, name, prompt)")
            except SystemExit:
                raise
            except Exception as e:
                _fail(f"selection agent_fn fail: {e!r}")
            sel = _parse_sel(raw_s)
            sel_path.write_text(json.dumps(sel, ensure_ascii=False, indent=2) + "\n",
                                encoding="utf-8")
        else:
            if sel_path.exists() and force:
                try:
                    sel_path.unlink()
                except Exception:
                    pass
            sel = _run_single_with_retry(workdir, full_sel, sel_rel, sel_log,
                                         _parse_sel, timeout, model, thinking, sel_path)
    sel_ups: list[dict] = list(sel.get("upgrades", []))
    sel_shop: list[dict] = list(sel.get("shop", []))
    ordered: list[dict] = ([{**u, "kind": "upgrade"} for u in sel_ups]
                           + [{**s, "kind": "shop"} for s in sel_shop])

    # 陈坑清扫: N 变小后超编 per_item/agent-wording 残留即 check fail 源, 直接清掉
    _keep = len(ordered)
    for _stale in sorted(per_dir.glob("*.json")):
        try:
            _idx = int(_stale.stem)
        except ValueError:
            # Safe 名旧残留 (上一代 Safe 文件): N 变后无法对齐, 直接清掉重跑
            try:
                _stale.unlink()
            except Exception:
                pass
            continue
        if _idx >= _keep:
            try:
                _stale.unlink()
            except Exception:
                pass
    for _stale in sorted(outdir.glob("agent-wording-*.log*")):
        _m = re.search(r"agent-wording-(\d+)\.log", _stale.name)
        if _m and int(_m.group(1)) >= _keep:
            try:
                _stale.unlink()
            except Exception:
                pass

    # ---- wording×N (并行, 每项独立单 agent) ----
    def _do_one(it: dict, idx: int):
        tag = f"{idx:02d}"
        per_path = per_dir / f"{tag}.json"
        w_prompt = build_wording_prompt({"name": it.get("name"),
                                         "quotes": it.get("quotes", [])},
                                        sentences, fewshot_text=fewshot)

        def _parse_w(d):
            return validate_wording(d, it, sentences)

        if per_path.exists() and not force:
            try:
                return _parse_w(json.loads(per_path.read_text(encoding="utf-8")))
            except SystemExit:
                raise
            except Exception:
                pass
        full_prompt = (w_prompt
                       + f"\n\n只写相对路径 `steps/07-priorities/per_item/{tag}.json`，"
                         f"禁 `..` 与绝对盘符。\n")
        if agent_fn is not None:
            try:
                raw_w = agent_fn("wording", it.get("name"), w_prompt)
            except SystemExit:
                raise
            except Exception as e:
                _fail(f"wording {it.get('name')} agent_fn fail: {e!r}")
            parsed = _parse_w(raw_w)
            per_path.write_text(json.dumps(parsed, ensure_ascii=False, indent=2) + "\n",
                                encoding="utf-8")
            return parsed
        log_path = outdir / f"agent-wording-{tag}.log"
        out_rel = f"steps/07-priorities/per_item/{tag}.json"
        if per_path.exists() and force:
            try:
                per_path.unlink()
            except Exception:
                pass
        return _run_single_with_retry(workdir, full_prompt, out_rel, log_path,
                                      _parse_w, timeout, model, thinking, per_path)

    wordings: list[dict] = []
    if agent_fn is not None:
        for _i, _it in enumerate(ordered):
            wordings.append(_do_one(_it, _i))
    else:
        with concurrent.futures.ThreadPoolExecutor(max_workers=max_workers) as ex:
            futs = {}
            for _i, _it in enumerate(ordered):
                futs[ex.submit(_do_one, _it, _i)] = _i
                time.sleep(stagger)
            by_i: dict[int, dict] = {}
            for fut in concurrent.futures.as_completed(futs):
                _i = futs[fut]
                by_i[_i] = fut.result()
            wordings = [by_i[_i] for _i in range(len(ordered))]

    # 自洽: wordings N == selection N (name 对齐, 顺序对齐)
    if len(wordings) != len(ordered):
        _fail(f"wordings N 须==selection N 自洽: 期望 {len(ordered)}, 实得 {len(wordings)}")
    for _it, _w in zip(ordered, wordings):
        if _w.get("name") != _it.get("name"):
            _fail(f"wordings name 须==selection 自洽: 期望 {_it.get('name')!r}, 实得 {_w.get('name')!r}")

    # ---- 合并落盘 (code only: quote_details 重建) ----
    ql = _quote_lookup(sentences)
    w_by = {w.get("name"): w for w in wordings}
    priorities: dict[str, list[dict]] = {"upgrades": [], "shop": []}
    for key, arr in (("upgrades", sel_ups), ("shop", sel_shop)):
        for ent in arr:
            nm = ent.get("name")
            w = w_by.get(nm)
            if w is None:
                _fail(f"合并缺 wording: {nm!r} (缺件即 fail)")
            qs: list[str] = []
            for q in (ent.get("quotes") or []):
                if q not in qs:
                    qs.append(q)
            details = []
            for q in qs:
                hits = ql.get(q, [])
                h = hits[0] if hits else {"start": None, "end": None, "t": None,
                                          "context": q[:300]}
                if h.get("start") is not None and not isinstance(h.get("t"), int):
                    _fail(f"priority {nm} quote_details t 非法: {q[:40]!r}")
                details.append({"quote": q, "start": h["start"], "end": h["end"],
                                "t": h["t"], "context": h["context"]})
            priorities[key].append({"name": nm,
                                    "kind": "upgrade" if key == "upgrades" else "shop",
                                    "why": str(w.get("why", "")).strip(),
                                    "how_to_get": str(w.get("how_to_get", "")).strip(),
                                    "quotes": qs,
                                    "quote_details": details})
    (outdir / "priorities.json").write_text(
        json.dumps(priorities, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    (workdir / "outputs").mkdir(parents=True, exist_ok=True)
    (workdir / "outputs" / "priorities.json").write_text(
        json.dumps(priorities, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    # 旧 ranking.json 若残留即删 (新链只认 selection.json, 旧终判已退役)
    _old_rank = outdir / "ranking.json"
    if _old_rank.exists():
        try:
            _old_rank.unlink()
        except Exception:
            pass
    return priorities
