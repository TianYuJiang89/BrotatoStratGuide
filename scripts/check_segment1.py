#!/usr/bin/env python3
"""Machine check for B-段1 (#40, #61): 01-03 新 schema + 04-attributes + 05-weapons.

沿试点 check_pilot.py (schema + 全收录 + 低频一句话 + sha), 加:
- 01 新 schema: {id,text[,start,end]} (B-04 起统一加, ?t= 跳链用)
- 02/03 新字段: start/end/context 只读 (不进机检锚点, 但须存在)
- 03 quotes 去重 (count 口径不动)
- 04: 39 全量 (主 17 + 次级 22), 提过即算口径 (count>0 必 S-D, count==0 必 -)
- 05 (#61): T1+T2 == candidates (discovery 自洽), T1>=1, note 短引逐字验 (码保)

Usage:
  python scripts/check_segment1.py --slug cyborg --variant ultimate
  python scripts/check_segment1.py --slug cyborg --variant ultimate --work-root G:/brotato-work
"""

from __future__ import annotations

import argparse
import hashlib
import json
import re
import re
from pathlib import Path

REPO = Path(__file__).resolve().parent.parent
TS_RE = re.compile(r"^\d{2}:\d{2}:\d{2}[.,]\d{3}$")


def fail(msg: str, errors: list[str]) -> None:
    errors.append(msg)
    print(f"FAIL: {msg}")


def _valid_ts(v) -> bool:
    return v is None or (isinstance(v, str) and bool(TS_RE.match(v)))


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description="check segment1 (#40)")
    ap.add_argument("--slug", default="cyborg")
    ap.add_argument("--variant", default="ultimate")
    ap.add_argument("--work-root", default="G:/brotato-work")
    args = ap.parse_args(argv)
    slug, vid = args.slug, args.variant
    work = Path(args.work_root) / slug / vid
    errors: list[str] = []
    warns: list[str] = []

    need = [
        work / "inputs" / "source.vtt",
        work / "inputs" / "meta.json",
        work / "inputs" / "manifest.json",
        work / "steps" / "01-sentences" / "sentences.json",
        work / "steps" / "02-verbs" / "verbs.json",
        work / "steps" / "03-grouping" / "candidates.json",
        work / "steps" / "03-grouping" / "discovery.json",
        work / "steps" / "03-grouping" / "fewshot.md",
        work / "steps" / "03-grouping" / "ranking.json",
        work / "steps" / "03-grouping" / "grouping.json",
        work / "outputs" / "groups.json",
        work / "steps" / "04-attributes" / "ratings.json",
        work / "outputs" / "ratings.json",
        work / "steps" / "05-weapons" / "candidates.json",
        work / "steps" / "05-weapons" / "discovery.json",
        work / "steps" / "05-weapons" / "fewshot-discovery.md",
        work / "steps" / "05-weapons" / "fewshot-evidence.md",
        work / "steps" / "05-weapons" / "fewshot-ranking.md",
        work / "steps" / "05-weapons" / "ranking.json",
        work / "steps" / "05-weapons" / "weapons.json",
        work / "outputs" / "weapons.json",
    ]
    for p in need:
        if not p.exists():
            fail(f"missing file: {p}", errors)
    if errors:
        return 1

    manifest = json.loads((work / "inputs" / "manifest.json").read_text(encoding="utf-8"))
    sentences = json.loads((work / "steps" / "01-sentences" / "sentences.json").read_text(encoding="utf-8"))
    verbs = json.loads((work / "steps" / "02-verbs" / "verbs.json").read_text(encoding="utf-8"))
    grouping = json.loads((work / "steps" / "03-grouping" / "grouping.json").read_text(encoding="utf-8"))
    outputs = json.loads((work / "outputs" / "groups.json").read_text(encoding="utf-8"))
    ratings = json.loads((work / "steps" / "04-attributes" / "ratings.json").read_text(encoding="utf-8"))
    ratings_out = json.loads((work / "outputs" / "ratings.json").read_text(encoding="utf-8"))
    weapons = json.loads((work / "steps" / "05-weapons" / "weapons.json").read_text(encoding="utf-8"))
    weapons_out = json.loads((work / "outputs" / "weapons.json").read_text(encoding="utf-8"))
    weapon_candidates = json.loads((work / "steps" / "05-weapons" / "candidates.json").read_text(encoding="utf-8"))
    discovery05_info = json.loads((work / "steps" / "05-weapons" / "discovery.json").read_text(encoding="utf-8"))
    item_candidates = json.loads((work / "steps" / "03-grouping" / "candidates.json").read_text(encoding="utf-8"))
    discovery_info = json.loads((work / "steps" / "03-grouping" / "discovery.json").read_text(encoding="utf-8"))
    # 打勾覆盖机检 (#62 v2: 收+丢==全表, 缺件即 fail; 分片动态, 不写死片数)
    try:
        _wiki_items = sorted((json.loads((REPO / "data" / "wiki-cache.json").read_text(encoding="utf-8")).get("items", {}) or {}).keys())
    except Exception:
        _wiki_items = []
        fail("data/wiki-cache.json items 读失败 (打勾覆盖无全表可比)", errors)
    # fewshot 运行快照 provenance: 03 单本 + 05 三本须与 repo FROZEN 文件逐字节一致
    try:
        _few_run = (work / "steps" / "03-grouping" / "fewshot.md").read_bytes()
        _few_repo = (REPO / "prompts" / "step03-grouping-fewshot.md").read_bytes()
        if _few_run != _few_repo:
            fail("steps/03-grouping/fewshot.md must equal repo FROZEN fewshot (逐字节, 重跑 03 即回填)", errors)
    except Exception:
        fail("steps/03-grouping/fewshot.md 读失败 (缺运行快照, 重跑 03 即回填)", errors)
    # fewshot 运行快照 provenance: 三本任务手册须与 repo FROZEN 文件逐字节一致 (审计离线可读即认此件)
    for _task in ("discovery", "evidence", "ranking"):
        try:
            _few_run = (work / "steps" / "05-weapons" / f"fewshot-{_task}.md").read_bytes()
            _few_repo = (REPO / "prompts" / f"step05-{_task}-fewshot.md").read_bytes()
            if _few_run != _few_repo:
                fail(f"steps/05-weapons/fewshot-{_task}.md must equal repo FROZEN fewshot (逐字节, 重跑 05 即回填)", errors)
        except Exception:
            fail(f"steps/05-weapons/fewshot-{_task}.md 读失败 (缺运行快照, 重跑 05 即回填)", errors)

    # --- 01-sentences 新 schema ---
    if not isinstance(sentences, list) or not sentences:
        fail("sentences must be non-empty array", errors)
    else:
        ids = [s.get("id") for s in sentences]
        if ids != list(range(1, len(sentences) + 1)):
            fail(f"sentences id must be 1..N continuous, got head {ids[:5]}", errors)
        # #43滚动折叠后: 411±100 (ultimate 411/danger-5 459/nightmare 442, 1496旧数作废)
        if not (300 <= len(sentences) <= 600):
            fail(f"sentences count must be 411±150折叠后 (300-600), got {len(sentences)}", errors)
        # #43无半句复读: 相邻句不得完全相同 (自然复读如Incredible.允许隔句, 滚动半句复读为相邻重复)
        texts = [s.get("text","") for s in sentences if isinstance(s, dict)]
        adj = sum(1 for i in range(1,len(texts)) if texts[i]==texts[i-1])
        if adj>0:
            fail(f"sentences must have no adjacent dups折叠后无半句复读, got {adj}", errors)
        for s in sentences[:5]:
            if not isinstance(s.get("text"), str) or not s["text"].strip():
                fail(f"sentence text empty: {s.get('id')}", errors)
            if "-->" in s["text"] or "<c>" in s["text"]:
                fail(f"sentence not cleaned: {s.get('id')}", errors)
        # start/end 可选但须合法
        n_ts = sum(1 for s in sentences if s.get("start") is not None)
        for s in sentences:
            if not _valid_ts(s.get("start")) or not _valid_ts(s.get("end")):
                fail(f"bad start/end format: id={s.get('id')} {s.get('start')}->{s.get('end')}", errors)
                break
        if n_ts < len(sentences) * 0.9:
            fail(f"start/end coverage too low: {n_ts}/{len(sentences)} (B-04 起应统一加)", errors)
        # t 与 start 同生同死: 有 start 必有 int t (审计 step1 按 t 渲染, 缺 t 即 no-ts 误导)
        bad_t = [s.get("id") for s in sentences if s.get("start") is not None and not isinstance(s.get("t"), int)]
        if bad_t:
            fail(f"sentences with start must carry int t (?t= 跳链用): ids={bad_t[:5]}", errors)

    sent_by_id = {s["id"]: s["text"] for s in sentences if isinstance(s, dict)}

    # --- 02-verbs (#48 种子 + agent 补, 只查格式) ---
    if not isinstance(verbs, dict) or "verified" not in verbs or "candidates" not in verbs:
        fail("verbs must be {verified[], candidates[]}", errors)
        verified, candidates = [], []
    else:
        verified, candidates = verbs["verified"], verbs["candidates"]
    for r in verified:
        for k in ("verb", "object_norm", "sentence_id", "quote"):
            if k not in r:
                fail(f"verified missing {k}: {r}", errors)
        if r.get("quote") != sent_by_id.get(r.get("sentence_id")):
            fail(f"verified quote must equal sentences text: {r.get('object_norm')}@{r.get('sentence_id')}", errors)
        for k in ("start", "end", "context"):
            if k not in r:
                fail(f"verified missing read-only {k}: {r.get('object_norm')}@{r.get('sentence_id')}", errors)
    for c in candidates:
        for k in ("surface", "quote", "reason"):
            if not c.get(k):
                fail(f"candidates must have {k}: {c.get('normalized_to')}", errors)
        if c.get("quote") != sent_by_id.get(c.get("sentence_id")):
            fail(f"candidates quote must equal sentences text: {c.get('normalized_to')}@{c.get('sentence_id')}", errors)
        if not isinstance(c.get("inferred"), bool):
            fail(f"candidates inferred must be bool: {c.get('normalized_to')}", errors)
        for k in ("start", "end", "context"):
            if k not in c:
                fail(f"candidates missing read-only {k}: {c.get('normalized_to')}@{c.get('sentence_id')}", errors)

    # --- 03-grouping (#62: frozen fewshot + discovery/evidence/grouping-ranking, shape only) ---
    # 新 schema: candidates.json [{name_en,count,quotes,quote_details}] (discovery 补全, scope 脱离 slice)
    # + ranking.json {must_take[],mentioned_not_taken[],ban[],casual_mention[]} (终判, 可推翻) 
    # + per_item/<Safe>.json (evidence 原始) + grouping.json [{name_en,count,group,quotes,analysis,note,quote_details}]
    # 链: ranking 四组==candidates; grouping==candidates 自洽; 旧件 tier/confidence/inferred/has_verb/
    # verb/verb_type/mapped_to/reason 全退役 (出现即 fail); count==len(quotes); note 短引逐字验.
    import re as _re3
    _short_re3 = _re3.compile(r'原话["“]([^"”]+)["”]')
    if not isinstance(item_candidates, list) or not item_candidates:
        fail("item candidates must be non-empty array (discovery completeness)", errors)
        _cand_names3: list = []
    else:
        _cand_names3 = []
        for c in item_candidates:
            if not isinstance(c, dict):
                fail("item candidates must be objects", errors)
                continue
            for k in ("name_en", "count", "quotes", "quote_details"):
                if k not in c:
                    fail(f"item candidates missing {k}: {c.get('name_en')}", errors)
            for _old in ("tier", "confidence", "inferred", "has_verb", "verb",
                          "verb_type", "mapped_to", "reason"):
                if _old in c:
                    fail(f"item candidates retired field must be absent: {_old}", errors)
            _cand_names3.append(c.get("name_en"))
            qs = c.get("quotes", [])
            if not isinstance(qs, list) or not qs:
                fail(f"item candidates must have quotes: {c.get('name_en')}", errors)
                qs = []
            if isinstance(qs, list) and len(qs) != len(set(qs)):
                fail(f"item candidates quotes must be deduped: {c.get('name_en')}", errors)
            if c.get("count") != len(qs):
                fail(f"item candidates count must == len(quotes): {c.get('name_en')}", errors)
            for q in qs:
                if q not in {s.get("text") for s in sentences if isinstance(s, dict)}:
                    fail(f"item candidates quotes must be verbatim: {c.get('name_en')}", errors)
                    break
            qd = c.get("quote_details", [])
            if not isinstance(qd, list) or len(qd) != len(qs):
                fail(f"item candidates quote_details must parallel quotes: {c.get('name_en')}", errors)
        if len(_cand_names3) != len(set(_cand_names3)):
            fail("item candidates must be deduped by name_en", errors)
    # 打勾覆盖机检 (#62 v2: 收+丢==全表, 缺件即 fail; 分片动态, 不写死片数)
    _d_chunks = discovery_info.get("chunks") if isinstance(discovery_info, dict) else None
    if not isinstance(_d_chunks, list) or not _d_chunks:
        fail("steps/03-grouping/discovery.json chunks 非法 (须为非空分片表)", errors)
        _d_chunks = []
    else:
        if sorted(sum([list(c) for c in _d_chunks], [])) != sorted(_wiki_items):
            fail("discovery.json 分片须覆盖全表 (动态分片, 缺件即 fail)", errors)
        _d_got: list = []
        _d_drop: list = []
        for _i, _ch in enumerate(_d_chunks):
            _cp = work / "steps" / "03-grouping" / f"discovery-chunk-{_i}.json"
            if not _cp.exists():
                fail(f"steps/03-grouping/discovery-chunk-{_i}.json 缺失 (分片 verdict, 缺节即 fail)", errors)
                continue
            try:
                _cd = json.loads(_cp.read_text(encoding="utf-8"))
            except Exception:
                fail(f"discovery-chunk-{_i}.json 非法 JSON", errors)
                continue
            if not isinstance(_cd, dict) or not isinstance(_cd.get("收"), list) or not isinstance(_cd.get("丢"), list):
                fail(f"discovery-chunk-{_i}.json 须为 {{收[], 丢[]}}", errors)
                continue
            _names = [x.get("name_en") for x in _cd["收"] if isinstance(x, dict)] + [x for x in _cd["丢"] if isinstance(x, str)]
            if sorted(_names) != sorted(_ch):
                fail(f"discovery-chunk-{_i}.json 收+丢须==本片 (缺件/串片即 fail)", errors)
            _d_got += [x.get("name_en") for x in _cd["收"] if isinstance(x, dict)]
            _d_drop += [x for x in _cd["丢"] if isinstance(x, str)]
        if sorted(_d_got + _d_drop) != sorted(_wiki_items):
            fail("discovery 全片收+丢须==全表 (沉默遗漏即 fail)", errors)
        if sorted(_d_got) != sorted(_cand_names3):
            fail("discovery 收须==candidates (合并一致)", errors)
    if isinstance(grouping, list):
        grouped_names = {g.get("name_en") for g in grouping if isinstance(g, dict)}
        if set(_cand_names3) and grouped_names != set(_cand_names3):
            fail(f"grouping must equal candidates {sorted(_cand_names3)}, got {sorted(grouped_names)}", errors)
        for g in grouping:
            for k in ("name_en", "count", "group", "quotes", "analysis", "note", "quote_details"):
                if k not in g:
                    fail(f"grouping missing {k}: {g.get('name_en')}", errors)
            if g.get("group") not in ("must_take", "mentioned_not_taken", "ban", "casual_mention"):
                fail(f"bad group: {g.get('name_en')}={g.get('group')}", errors)
            for _old in ("tier", "confidence", "inferred", "has_verb", "verb",
                          "verb_type", "mapped_to", "surface_verb", "surface_word",
                          "discretion_reason", "reason"):
                if _old in g:
                    fail(f"grouping retired field must be absent: {_old} ({g.get('name_en')})", errors)
            qs = g.get("quotes", [])
            if not isinstance(qs, list) or not qs:
                fail(f"grouping must have quotes (空证据即 fail): {g.get('name_en')}", errors)
                qs = []
            if isinstance(qs, list) and len(qs) != len(set(qs)):
                fail(f"quotes must be deduped (展示去重): {g.get('name_en')}", errors)
            if isinstance(g.get("count"), int) and g.get("count") != len(qs):
                fail(f"grouping count must == len(quotes): {g.get('name_en')}", errors)
            for q in qs:
                if q not in {s.get("text") for s in sentences if isinstance(s, dict)}:
                    fail(f"grouping quotes must be verbatim: {g.get('name_en')}", errors)
                    break
            _ana = str(g.get("analysis", ""))
            if len(_ana.strip()) < 4:
                fail(f"grouping analysis must be nonempty: {g.get('name_en')}", errors)
            if not g.get("note") or len(str(g.get("note")).strip()) < 2:
                fail(f"grouping note too short: {g.get('name_en')}", errors)
            if len(str(g.get("note", ""))) > 120:
                fail(f"grouping note must be <=120: {g.get('name_en')}", errors)
            _shorts = [s.strip() for s in _short_re3.findall(str(g.get("note", ""))) if s.strip()]
            if not _shorts:
                fail(f"grouping note 缺短引标记 原话\"...\": {g.get('name_en')}", errors)
            for _s in _shorts:
                if not any(_s in _q for _q in qs if isinstance(_q, str)):
                    fail(f"grouping note 短引须逐字出自 quotes: {g.get('name_en')}", errors)
                    break
            qd = g.get("quote_details", [])
            if not isinstance(qd, list) or len(qd) != len(qs):
                fail(f"quote_details must parallel quotes: {g.get('name_en')}", errors)
            else:
                for d in qd[:2]:
                    if "quote" not in d or "context" not in d:
                        fail(f"quote_details missing quote/context: {g.get('name_en')}", errors)
                        break
    else:
        fail("grouping must be array", errors)
    if grouping != outputs:
        fail("outputs/groups.json must equal steps/03-grouping/grouping.json (重跑 01-03 新 schema 后须一致)", errors)
    # 链: ranking 四组终判名==candidates (cut 自洽, 可推翻 tier 但名必须对上)
    try:
        ranking03 = json.loads((work / "steps" / "03-grouping" / "ranking.json").read_text(encoding="utf-8"))
    except Exception:
        ranking03 = None  # type: ignore
        fail("steps/03-grouping/ranking.json 缺失或非法 (终判, 缺节即 fail)", errors)
    if isinstance(ranking03, dict):
        got_r3: set = set()
        for _t in ("must_take", "mentioned_not_taken", "ban", "casual_mention"):
            for _x in (ranking03.get(_t) or []):
                if isinstance(_x, dict):
                    got_r3.add(_x.get("name_en"))
                    _rn, _rnote = _x.get("name_en"), str(_x.get("note", ""))
                    _rs = [s.strip() for s in _short_re3.findall(_rnote) if s.strip()]
                    if not _rs:
                        fail(f"ranking note 缺短引标记 原话\"...\": {_rn}", errors)
                    else:
                        _safe = re.sub(r"[^A-Za-z0-9]+", "_", str(_rn)).strip("_")
                        _pp = work / "steps" / "03-grouping" / "per_item" / f"{_safe}.json"
                        try:
                            _pev = json.loads(_pp.read_text(encoding="utf-8"))
                            _pqs = _pev.get("quotes", [])
                        except Exception:
                            _pqs = []
                        for _s in _rs:
                            if not any(_s in _q for _q in _pqs if isinstance(_q, str)):
                                fail(f"ranking note 短引须逐字出自 evidence quotes: {_rn}", errors)
                                break
        if set(_cand_names3) and got_r3 != set(_cand_names3):
            fail(f"ranking 四组须==candidates {sorted(_cand_names3)}, got {sorted(got_r3)}", errors)
    # 链: per_item 每件存在 + group 合法 + 名对上 + quotes 非空
    for _n in _cand_names3:
        _safe = re.sub(r"[^A-Za-z0-9]+", "_", str(_n)).strip("_")
        _pp = work / "steps" / "03-grouping" / "per_item" / f"{_safe}.json"
        if not _pp.exists():
            fail(f"per_item missing (evidence 原始): {_n}", errors)
            continue
        try:
            _ev = json.loads(_pp.read_text(encoding="utf-8"))
        except Exception:
            fail(f"per_item 非法 JSON: {_n}", errors)
            continue
        if not isinstance(_ev, dict) or _ev.get("name_en") != _n:
            fail(f"per_item name_en 须对上: {_n}", errors)
        if _ev.get("group") not in ("must_take", "mentioned_not_taken", "ban", "casual_mention"):
            fail(f"per_item group 须四组之一: {_n}", errors)
        _eq = _ev.get("quotes", [])
        if not isinstance(_eq, list) or not _eq:
            fail(f"per_item quotes 须非空: {_n}", errors)
        for _q in _eq:
            if _q not in {s.get("text") for s in sentences if isinstance(s, dict)}:
                fail(f"per_item quotes 须逐字: {_n}", errors)
                break
    # 审计节点三元组: 每次 LLM 调用须留 log
    _logs3 = [work / "steps" / "03-grouping" / "agent-ranking.log.jsonl"]
    _d_chunks_for_logs = discovery_info.get("chunks") if isinstance(discovery_info, dict) else []
    for _i in range(len(_d_chunks_for_logs) if isinstance(_d_chunks_for_logs, list) else 0):
        _logs3.append(work / "steps" / "03-grouping" / f"agent-discovery-chunk-{_i}.log.jsonl")
    for _n in _cand_names3:
        _safe = re.sub(r"[^A-Za-z0-9]+", "_", str(_n)).strip("_")
        _logs3.append(work / "steps" / "03-grouping" / f"agent-evidence-{_safe}.log.jsonl")
    for _lp in _logs3:
        if not _lp.exists() or _lp.stat().st_size == 0:
            fail(f"03审计节点缺log (入参不可查, 重跑03回填): {_lp.name}", errors)

    # --- 04-attributes (#60: frozen fewshot + for-loop x39, shape only) ---
    if not isinstance(ratings, list) or len(ratings) != 39:
        fail("ratings must be 39", errors)
    else:
        import csv as _csv
        terms = list(_csv.DictReader((REPO / "data" / "terms.csv").open(encoding="utf-8")))
        expect = [(t["en"].strip(), t.get("type", "")) for t in terms]
        got = [(r.get("term_en"), r.get("type")) for r in ratings]
        if set(x[0] for x in got) != set(x[0] for x in expect):
            fail("ratings must cover all 39 terms", errors)
        _meta_by = {t["en"].strip(): t for t in terms}
        sent_texts = {s.get("text") for s in sentences if isinstance(s, dict)}
        for r in ratings:
            for k in ("term_en", "term_zh", "type", "count", "rating", "quotes", "analysis", "summary", "quote_details"):
                if k not in r:
                    fail("ratings missing", errors)
            for _old in ("anchors", "confidence", "kind", "inferred", "reason"):
                if _old in r:
                    fail("ratings retired field must be absent", errors)
            cnt = r.get("count")
            rt = r.get("rating")
            if not isinstance(cnt, int) or cnt < 0:
                fail("ratings count must be nonneg int", errors)
            if rt not in ("S", "A", "B", "C", "D", "-"):
                fail("ratings rating must be valid", errors)
            _exp = _meta_by.get(r.get("term_en"), {})
            if _exp and r.get("term_zh") != _exp.get("zh"):
                fail("ratings term_zh must match terms.csv", errors)
            if _exp and r.get("type") != _exp.get("type"):
                fail("ratings type must match terms.csv", errors)
            qs = r.get("quotes", [])
            if not isinstance(qs, list):
                fail("ratings quotes must be array", errors)
                qs = []
            if len(qs) != len(set(qs)):
                fail("ratings quotes must be deduped", errors)
            for q in qs:
                if q not in sent_texts:
                    fail("ratings quotes must be verbatim from sentences", errors)
                    break
            _ana = str(r.get("analysis", ""))
            if len(_ana.strip()) < 4:
                fail("ratings analysis must be nonempty", errors)
            pass  # 漏数不卡 (#60删禁数字，agent全权)
            _sum = str(r.get("summary", ""))
            if not _sum.strip():
                fail("ratings summary missing", errors)
            if len(_sum) > 120:
                fail("ratings summary must be le 120", errors)
            pass  # 漏数不卡 (#60删禁数字，agent全权)
            qd = r.get("quote_details", [])
            if not isinstance(qd, list) or len(qd) != len(qs):
                fail("ratings quote_details must parallel quotes", errors)
            else:
                for d in qd:
                    if not isinstance(d, dict) or "quote" not in d or "t" not in d:
                        fail("ratings quote_details must have quote and t", errors)
                        break
                    if d.get("quote") not in qs:
                        fail("ratings quote_details quote must be in quotes", errors)
                        break
                    if not _valid_ts(d.get("start")) or not _valid_ts(d.get("end")):
                        fail("ratings quote_details start end bad", errors)
                        break
                    if d.get("start") is not None and not isinstance(d.get("t"), int):
                        fail("ratings quote_details start must have int t", errors)
                        break
                for d in qd[:2]:
                    if "context" not in d:
                        fail("ratings quote_details missing context", errors)
                        break
            if isinstance(cnt, int):
                if cnt == 0:
                    if rt != "-":
                        fail("count0 must be dash", errors)
                    if qs:
                        fail("count0 must have empty quotes", errors)
                    if qd:
                        fail("count0 must have empty quote_details", errors)
                    if "作者未提及" not in _sum:
                        fail("count0 summary must say not mentioned", errors)
                else:
                    if rt == "-":
                        fail("count positive must not be dash", errors)
                    if not qs:
                        fail("count positive must have quotes", errors)
    if ratings != ratings_out:
        fail("outputs ratings must equal steps ratings", errors)

    # --- 05-weapons (#61: frozen fewshot + discovery/evidence/ranking, shape only; #62 v2 打勾) ---
    # 新 schema: candidates.json [{name_en,count,quotes,quote_details}] + weapons.json {t1[],t2[]}
    # + ranking.json {t1[{name_en,note}],t2[]} (终判, 可推翻) + per_weapon/<Safe>.json (evidence 原始)
    # 链: ranking 名==candidates; per_weapon 每把存在+tier合法+名对上; 旧六件退役 (出现即 fail);
    # 每条 {name_en,count,tier,quotes,analysis,note,quote_details}; 旧六件退役 (出现即 fail);
    # count==len(quotes); note 短引逐字验 (原话"..."/原话“...”须出自 quotes, 缺标记/改写即 fail); T1>=1; T1+T2==candidates.
    import re as _re
    _short_re = _re.compile(r'原话["“]([^"”]+)["”]')
    if not isinstance(weapon_candidates, list) or not weapon_candidates:
        fail("candidates must be non-empty array (discovery completeness)", errors)
        cand_names = []
    else:
        cand_names = []
        for c in weapon_candidates:
            if not isinstance(c, dict):
                fail("candidates must be objects", errors)
                continue
            for k in ("name_en", "count", "quotes", "quote_details"):
                if k not in c:
                    fail(f"candidates missing {k}: {c.get('name_en')}", errors)
            for _old in ("anchors", "confidence", "kind", "inferred", "score", "reason"):
                if _old in c:
                    fail(f"candidates retired field must be absent: {_old}", errors)
            cand_names.append(c.get("name_en"))
            qs = c.get("quotes", [])
            if not isinstance(qs, list) or not qs:
                fail(f"candidates must have quotes: {c.get('name_en')}", errors)
                qs = []
            if isinstance(qs, list) and len(qs) != len(set(qs)):
                fail(f"candidates quotes must be deduped: {c.get('name_en')}", errors)
            if c.get("count") != len(qs):
                fail(f"candidates count must == len(quotes): {c.get('name_en')}", errors)
            for q in qs:
                if q not in {s.get("text") for s in sentences if isinstance(s, dict)}:
                    fail(f"candidates quotes must be verbatim: {c.get('name_en')}", errors)
                    break
            qd = c.get("quote_details", [])
            if not isinstance(qd, list) or len(qd) != len(qs):
                fail(f"candidates quote_details must parallel quotes: {c.get('name_en')}", errors)
        if len(cand_names) != len(set(cand_names)):
            fail("candidates must be deduped by name_en", errors)
    # 打勾覆盖机检 (#62 v2: 收+丢==武器全表, 缺件即 fail; 分片动态, 不写死武器数)
    _d5_chunks = discovery05_info.get("chunks") if isinstance(discovery05_info, dict) else None
    if not isinstance(_d5_chunks, list) or not _d5_chunks:
        fail("steps/05-weapons/discovery.json chunks 非法 (须为非空分片表)", errors)
    else:
        try:
            _wiki_weapons = sorted((json.loads((REPO / "data" / "wiki-cache.json").read_text(encoding="utf-8")).get("weapons", {}) or {}).keys())
        except Exception:
            _wiki_weapons = []
            fail("data/wiki-cache.json weapons 读失败 (打勾覆盖无全表可比)", errors)
        if sorted(sum([list(c) for c in _d5_chunks], [])) != sorted(_wiki_weapons):
            fail("discovery.json 分片须覆盖武器全表 (动态分片, 缺件即 fail)", errors)
        _d5_got: list = []
        _d5_drop: list = []
        for _i, _ch in enumerate(_d5_chunks):
            _cp = work / "steps" / "05-weapons" / f"discovery-chunk-{_i}.json"
            if not _cp.exists():
                fail(f"steps/05-weapons/discovery-chunk-{_i}.json 缺失 (分片 verdict, 缺节即 fail)", errors)
                continue
            try:
                _cd = json.loads(_cp.read_text(encoding="utf-8"))
            except Exception:
                fail(f"discovery-chunk-{_i}.json 非法 JSON", errors)
                continue
            if not isinstance(_cd, dict) or not isinstance(_cd.get("收"), list) or not isinstance(_cd.get("丢"), list):
                fail(f"discovery-chunk-{_i}.json 须为 {{收[], 丢[]}}", errors)
                continue
            _names = [x.get("name_en") for x in _cd["收"] if isinstance(x, dict)] + [x for x in _cd["丢"] if isinstance(x, str)]
            if sorted(_names) != sorted(_ch):
                fail(f"discovery-chunk-{_i}.json 收+丢须==本片 (缺件/串片即 fail)", errors)
            _d5_got += [x.get("name_en") for x in _cd["收"] if isinstance(x, dict)]
            _d5_drop += [x for x in _cd["丢"] if isinstance(x, str)]
        if sorted(_d5_got + _d5_drop) != sorted(_wiki_weapons):
            fail("discovery 全片收+丢须==武器全表 (沉默遗漏即 fail)", errors)
        if sorted(_d5_got) != sorted(cand_names):
            fail("discovery 收须==candidates (合并一致)", errors)
    if not isinstance(weapons, dict) or "t1" not in weapons or "t2" not in weapons:
        fail("weapons must be {t1[], t2[]}", errors)
        t1, t2 = [], []
    else:
        t1, t2 = weapons["t1"], weapons["t2"]
    got_w = {w.get("name_en") for w in (t1 + t2) if isinstance(w, dict)}
    if set(cand_names) and got_w != set(cand_names):
        fail(f"weapons t1+t2 must equal candidates {sorted(cand_names)}, got {sorted(got_w)}", errors)
    if len(t1) < 1:
        fail("weapons T1>=1 (验收线, 由 ranking 保)", errors)
    sent_texts = {s.get("text") for s in sentences if isinstance(s, dict)}
    for w in (t1 + t2):
        for k in ("name_en", "count", "tier", "note", "quotes", "analysis", "copies", "copies_quote", "quote_details"):
            if k not in w:
                fail(f"weapons missing {k}: {w.get('name_en')}", errors)
        for _old in ("anchors", "confidence", "kind", "inferred", "score", "reason"):
            if _old in w:
                fail(f"weapons retired field must be absent: {_old} ({w.get('name_en')})", errors)
        if w.get("tier") not in ("T1", "T2"):
            fail(f"weapons tier must be T1/T2: {w.get('name_en')}", errors)
        qs = w.get("quotes", [])
        if not isinstance(qs, list) or not qs:
            fail(f"weapons must have quotes (空证据即 fail): {w.get('name_en')}", errors)
            qs = []
        if isinstance(qs, list) and len(qs) != len(set(qs)):
            fail(f"weapons quotes must be deduped: {w.get('name_en')}", errors)
        if isinstance(w.get("count"), int) and w.get("count") != len(qs):
            fail(f"weapons count must == len(quotes): {w.get('name_en')}", errors)
        for q in qs:
            if q not in sent_texts:
                fail(f"weapons quotes must be verbatim: {w.get('name_en')}", errors)
                break
        _ana = str(w.get("analysis", ""))
        if len(_ana.strip()) < 4:
            fail(f"weapons analysis must be nonempty: {w.get('name_en')}", errors)
        if not w.get("note") or len(str(w.get("note")).strip()) < 2:
            fail(f"weapons note too short: {w.get('name_en')}", errors)
        if len(str(w.get("note", ""))) > 120:
            fail(f"weapons note must be <=120: {w.get('name_en')}", errors)
        _shorts = [s.strip() for s in _short_re.findall(str(w.get("note", ""))) if s.strip()]
        if not _shorts:
            fail(f"weapons note 缺短引标记 原话\"...\": {w.get('name_en')}", errors)
        for _s in _shorts:
            if not any(_s in _q for _q in qs if isinstance(_q, str)):
                fail(f"weapons note 短引须逐字出自 quotes: {w.get('name_en')}", errors)
                break
        _cop, _cq = str(w.get("copies", "")), str(w.get("copies_quote", ""))
        if not _cop.strip():
            fail(f"weapons 缺 copies (配比须明示): {w.get('name_en')}", errors)
        elif _cop.strip() == "未提及":
            if _cq.strip():
                fail(f"weapons copies 未提及则 quote 须空: {w.get('name_en')}", errors)
        else:
            if not _cq.strip():
                fail(f"weapons 缺 copies_quote: {w.get('name_en')}", errors)
            elif not any(_cq.strip() in _q for _q in qs if isinstance(_q, str)):
                fail(f"weapons copies_quote 须逐字出自 quotes: {w.get('name_en')}", errors)
        qd = w.get("quote_details", [])
        if not isinstance(qd, list) or len(qd) != len(qs):
            fail(f"weapons quote_details must parallel quotes: {w.get('name_en')}", errors)
        else:
            for d in qd:
                if not isinstance(d, dict) or "quote" not in d or "t" not in d:
                    fail(f"weapons quote_details must have quote and t: {w.get('name_en')}", errors)
                    break
                if d.get("quote") not in qs:
                    fail(f"weapons quote_details quote must be in quotes: {w.get('name_en')}", errors)
                    break
                if d.get("start") is not None and not isinstance(d.get("t"), int):
                    fail(f"weapons quote_details start must have int t: {w.get('name_en')}", errors)
                    break
        rs = str(w.get("note", ""))
        if "字幕" in rs and "次" in rs and "原话" not in rs:
            warns.append(f"WARN: weapons 疑计数泄漏: {w.get('name_en')}")
    if weapons != weapons_out:
        fail("outputs/weapons.json must equal steps/05-weapons/weapons.json", errors)
    # 链: ranking 终判名==candidates (cut 自洽, 可推翻 tier 但名必须对上)
    try:
        ranking = json.loads((work / "steps" / "05-weapons" / "ranking.json").read_text(encoding="utf-8"))
    except Exception:
        ranking = None  # type: ignore
        fail("ranking.json 缺失或非法 (ranking 终判, 缺节即 fail)", errors)
    if isinstance(ranking, dict):
        got_r = set()
        for _t in ("t1", "t2"):
            for _x in (ranking.get(_t) or []):
                if isinstance(_x, dict):
                    got_r.add(_x.get("name_en"))
                    _rn, _rnote = _x.get("name_en"), str(_x.get("note", ""))
                    _rs = [s.strip() for s in _short_re.findall(_rnote) if s.strip()]
                    if not _rs:
                        fail(f"ranking note 缺短引标记 原话\"...\": {_rn}", errors)
                    else:
                        _safe = re.sub(r"[^A-Za-z0-9]+", "_", str(_rn)).strip("_")
                        _pp = work / "steps" / "05-weapons" / "per_weapon" / f"{_safe}.json"
                        try:
                            _pev = json.loads(_pp.read_text(encoding="utf-8"))
                            _pqs = _pev.get("quotes", [])
                        except Exception:
                            _pqs = []
                        for _s in _rs:
                            if not any(_s in _q for _q in _pqs if isinstance(_q, str)):
                                fail(f"ranking note 短引须逐字出自 evidence quotes: {_rn}", errors)
                                break
                        _rcop, _rcq = str(_x.get("copies", "")), str(_x.get("copies_quote", ""))
                        if not _rcop.strip():
                            fail(f"ranking 缺 copies: {_rn}", errors)
                        elif _rcop.strip() == "未提及":
                            if _rcq.strip():
                                fail(f"ranking copies 未提及则 quote 须空: {_rn}", errors)
                        else:
                            if not _rcq.strip():
                                fail(f"ranking 缺 copies_quote: {_rn}", errors)
                            elif not any(_rcq.strip() in _q for _q in _pqs if isinstance(_q, str)):
                                fail(f"ranking copies_quote 须逐字出自 evidence quotes: {_rn}", errors)
        if set(cand_names) and got_r != set(cand_names):
            fail(f"ranking t1+t2 must equal candidates {sorted(cand_names)}, got {sorted(got_r)}", errors)
    # 链: per_weapon 每把存在 (Safe 名) + tier 合法 + 名对上 + quotes 非空
    for _n in cand_names:
        _safe = re.sub(r"[^A-Za-z0-9]+", "_", str(_n)).strip("_")
        _pp = work / "steps" / "05-weapons" / "per_weapon" / f"{_safe}.json"
        if not _pp.exists():
            fail(f"per_weapon missing (evidence 原始): {_n}", errors)
            continue
        try:
            _ev = json.loads(_pp.read_text(encoding="utf-8"))
        except Exception:
            fail(f"per_weapon 非法 JSON: {_n}", errors)
            continue
        if not isinstance(_ev, dict) or _ev.get("name_en") != _n:
            fail(f"per_weapon name_en 须对上: {_n}", errors)
        if _ev.get("tier") not in ("T1", "T2"):
            fail(f"per_weapon tier 须 T1/T2: {_n}", errors)
        _eq = _ev.get("quotes", [])
        if not isinstance(_eq, list) or not _eq:
            fail(f"per_weapon quotes 须非空: {_n}", errors)
        for _q in _eq:
            if _q not in sent_texts:
                fail(f"per_weapon quotes 须逐字 (扩引也逐字): {_n}", errors)
                break
        _eshorts = [s.strip() for s in _short_re.findall(str(_ev.get("note", ""))) if s.strip()]
        if not _eshorts:
            fail(f"per_weapon note 缺短引标记 原话\"...\": {_n}", errors)
        for _s in _eshorts:
            if not any(_s in _q for _q in _eq if isinstance(_q, str)):
                fail(f"per_weapon note 短引须逐字出自 quotes: {_n}", errors)
                break
        _ecop, _ecq = str(_ev.get("copies", "")), str(_ev.get("copies_quote", ""))
        if not _ecop.strip():
            fail(f"per_weapon 缺 copies: {_n}", errors)
        elif _ecop.strip() == "未提及":
            if _ecq.strip():
                fail(f"per_weapon copies 未提及则 quote 须空: {_n}", errors)
        else:
            if not _ecq.strip():
                fail(f"per_weapon 缺 copies_quote: {_n}", errors)
            elif not any(_ecq.strip() in _q for _q in _eq if isinstance(_q, str)):
                fail(f"per_weapon copies_quote 须逐字出自 quotes: {_n}", errors)
    # 审计节点三元组: 每次 LLM 调用须留 log (入参 prompt 可查), 缺 log 即 fail
    _logs = [work / "steps" / "05-weapons" / "agent-ranking.log.jsonl"]
    for _i in range(len(_d5_chunks) if isinstance(_d5_chunks, list) else 0):
        _logs.append(work / "steps" / "05-weapons" / f"agent-discovery-chunk-{_i}.log.jsonl")
    for _n in cand_names:
        _safe = re.sub(r"[^A-Za-z0-9]+", "_", str(_n)).strip("_")
        _logs.append(work / "steps" / "05-weapons" / f"agent-evidence-{_safe}.log.jsonl")
    for _lp in _logs:
        if not _lp.exists() or _lp.stat().st_size == 0:
            fail(f"05审计节点缺log (入参不可查, 重跑05回填): {_lp.name}", errors)

    # --- audit 常设对应节 (check 与审计节一一对应, 缺节即 fail) ---
    audit_html = (REPO / "templates" / "audit.html").read_text(encoding="utf-8")
    for marker in ("audit-04-attributes", "audit-05-weapons", "steps/04-attributes", "steps/05-weapons"):
        if marker not in audit_html:
            fail(f"audit.html 缺对应节 (一一对应): {marker}", errors)
    # B-段2 空节占位 (#42: 开工前审计先有 06-09 空节, 缺节即 fail, 与实现同 PR 进)
    for marker in ("audit-06-phases", "audit-07-priorities", "audit-08-pitfalls", "audit-09-assemble",
                   "steps/06-phases", "steps/07-priorities", "steps/08-pitfalls", "steps/09-assemble"):
        if marker not in audit_html:
            fail(f"audit.html 缺 06-09 空节占位 (#42): {marker}", errors)
    # 06-09 输入标注 (每步卡标清真实输入, 沿 01-05 已标口径)
    for marker in ("steps/06-phases/phases.json", "steps/07-priorities/priorities.json",
                   "steps/08-pitfalls/pitfalls.json", "steps/09-assemble/guide.json"):
        if marker not in audit_html:
            fail(f"audit.html 缺 06-09 输入标注 (#42): {marker}", errors)
    # DAG 分组 (#42: 01→{02→03,04,05,06,08}→07→09 分层, 不再直线串行; 04/05 已按层)
    if "01→{02→03,04,05,06,08}→07→09" not in audit_html:
        fail("audit.html 缺 DAG 分层总览 (#42): 01→{02→03,04,05,06,08}→07→09", errors)
    for marker in ('data-dag-layer="L0"', 'data-dag-layer="L1"',
                   'data-dag-layer="L2"', 'data-dag-layer="L3"'):
        if marker not in audit_html:
            fail(f"audit.html 缺 DAG 分层标记 (#42): {marker}", errors)
    if "DAG L1" not in audit_html:
        fail("audit.html 缺 DAG L1 并行层标注 (#42: 04/05 已按层)", errors)
    # 左侧 DAG 导航 (长页跳转: 按 DAG 分层列全 10 节, 缺节即 fail)
    if 'id="sideNav"' not in audit_html:
        fail("audit.html 缺左侧导航 (#42跟进): 缺 id=sideNav", errors)
    for marker in ("audit-inputs", "audit-01-sentences", "audit-02-verbs", "audit-03-grouping",
                   "audit-04-attributes", "audit-05-weapons", "audit-06-phases", "audit-08-pitfalls",
                   "audit-07-priorities", "audit-09-assemble"):
        if marker not in audit_html:
            fail(f"audit.html 左侧导航缺锚点 (#42跟进): {marker}", errors)
        if f'href="#{marker}"' not in audit_html:
            fail(f"audit.html 左侧导航缺链接 (#42跟进): #{marker}", errors)
    # step1/2 行级明细 (句子/动词行点开进抽屉, 与 step3 卡片对齐, 缺钩子即 fail)
    for marker in ("data-sent", "data-verb-v", "data-verb-c",
                   "openSentenceDrawer", "openVerbDrawer", "fullContextHtml",
                   "data-jump-sent", "sentJumpLink"):
        if marker not in audit_html:
            fail(f"audit.html 缺 step1/2 行明细 (#42跟进): {marker}", errors)
    # 06-09 审计 (卡片钩子 + 抽屉明细 + 07依赖穿透, 缺即 fail；08按节点公约无卡片/抽屉，只列D/W节点)
    for marker in ("data-phase", "data-priority",
                   "openPhaseDrawer", "openPriorityDrawer",
                   "依赖来源", "继承自"):
        if marker not in audit_html:
            fail(f"audit.html 缺06-09审计 (#42): {marker}", errors)
    # 默认工作区 (picker 从 G:\brotato-work/上次目录开始: 固定 id + IndexedDB 存句柄)
    for marker in ("startIn", "brotato-work-root"):
        if marker not in audit_html:
            fail(f"audit.html 缺默认工作区 (#42跟进): {marker}", errors)
    # ratings/weapons mock 已删 (#60 只读真实，不回落 mock): 禁残留 MOCK 常量与自动载入
    for marker in ("MOCK_RATINGS", "MOCK_WEAPONS", "MOCK_DATA", "loadMockData"):
        if marker in audit_html:
            fail(f"audit.html 须无 mock 残留 (#60 只读真实): {marker}", errors)
    # 禁静默回 mock: 启动不许自动载 mock (麦当劳不给广告纸); live 失败必须亮红灯不回落
    import re as _re2
    _m = _re2.search(r"window\.addEventListener\('DOMContentLoaded'.*?", audit_html, _re2.DOTALL)
    # 粗查: DOMContentLoaded 块内不许出现 loadMockData()
    _dom = audit_html[audit_html.find("window.addEventListener('DOMContentLoaded'"):audit_html.find("window.addEventListener('DOMContentLoaded'")+2000]
    if "loadMockData()" in _dom:
        fail("audit.html 禁静默回 mock: DOMContentLoaded 不许自动 loadMockData()", errors)
    for marker in ("不回落 mock",):
        if marker not in audit_html:
            fail(f"audit.html 缺 live 硬保证文案: {marker}", errors)
    # live 硬保证: 顶栏来源可验 (live 蓝点才算验收) + 失败红灯不回落 + 备用上传不伪造 live
    for marker in ("source-dot live", "source-dot error", "live 加载失败", "live 加载异常"):
        if marker not in audit_html:
            fail(f"audit.html 缺 live 硬保证 (#42): {marker}", errors)
    if "webkitRelativePath" not in audit_html:
        fail("audit.html 备用上传须实读文件 (禁伪造 live, #42): 缺 webkitRelativePath", errors)

    # --- sha 对上 ---
    src_bytes = (work / "inputs" / "source.vtt").read_bytes()
    actual_sha = hashlib.sha1(src_bytes).hexdigest()
    expect_sha = (manifest.get("sources") or [{}])[0].get("sha1", "")
    if actual_sha != expect_sha:
        fail(f"sha mismatch: manifest {expect_sha[:8]} vs actual {actual_sha[:8]}", errors)

    if errors:
        print(f"FAIL: check_segment1 {len(errors)} errors")
        return 1
    for w in warns:
        print(w)
    print(f"OK: segment1 cleared, sentences={len(sentences)} verified={len(verified)} "
          f"candidates={len(candidates)} grouping={len(grouping)} "
          f"ratings={len(ratings)} weapons=T1:{len(t1)} T2:{len(t2)} sha={actual_sha[:8]}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
