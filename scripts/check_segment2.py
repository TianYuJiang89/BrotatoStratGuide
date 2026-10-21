#!/usr/bin/env python3
"""Machine check for B-段2 (#63 + #49): 06-phases + 07-priorities + 08-pitfalls + 09-assemble.

沿 check_segment1.py (schema + 去重 + quote 对句 + sha + audit 一一对应), 加:
- 06 (#63: frozen fewshot + segmentation/wording, N 不定, 运营波次自定义): buckets.json + wordings.json + per_phase/* + phases.json, 桶间不重叠, 桶内前缀须等于 buckets, 桶外补标 out_of_window, 小结≠原文
- 07 (#49 去 Top3 写死 + Peacock 按名顺延; #50 升级侧同商店刀法去 sa[:3] 写死): upgrades N 动态 + shop N 动态 (全在 ratings S/A / 新 grouping must_take verified 内,
  通用拒绝顺延 + 最大断层 TopN + 保底 Top1), 每项 why/how_to_get/quotes[0]
- 08: >=3 条, severity 全在 fatal/risky/trap 内, 每条 why/how_to_avoid/quotes[0]
- 09: 双写一致 + 六节聚合一致 + sha 对上 manifest + source.vtt
- audit 常设对应节 (check 与审计节一一对应, 缺节即 fail; 06-09 须为实节非空占位)

Usage:
  python scripts/check_segment2.py --slug cyborg --variant ultimate
  python scripts/check_segment2.py --slug cyborg --variant ultimate --work-root G:/brotato-work
"""

from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path

REPO = Path(__file__).resolve().parent.parent


def fail(msg: str, errors: list[str]) -> None:
    errors.append(msg)
    print(f"FAIL: {msg}")


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description="check segment2 (#41)")
    ap.add_argument("--slug", default="cyborg")
    ap.add_argument("--variant", default="ultimate")
    ap.add_argument("--work-root", default="G:/brotato-work")
    args = ap.parse_args(argv)
    slug, vid = args.slug, args.variant
    work = Path(args.work_root) / slug / vid
    errors: list[str] = []
    warns: list[str] = []

    need = [
        work / "steps" / "06-phases" / "buckets.json",
        work / "steps" / "06-phases" / "wordings.json",
        work / "steps" / "06-phases" / "fewshot.md",
        work / "steps" / "06-phases" / "phases.json",
        work / "outputs" / "phases.json",
        work / "steps" / "07-priorities" / "priorities.json",
        work / "outputs" / "priorities.json",
        work / "steps" / "08-pitfalls" / "pitfalls.json",
        work / "outputs" / "pitfalls.json",
        work / "steps" / "08-pitfalls" / "candidates.json",
        work / "steps" / "09-assemble" / "guide.json",
        work / "outputs" / "guide.json",
        work / "steps" / "01-sentences" / "sentences.json",
        work / "steps" / "03-grouping" / "grouping.json",
        work / "steps" / "04-attributes" / "ratings.json",
        work / "steps" / "05-weapons" / "weapons.json",
        work / "inputs" / "manifest.json",
    ]
    for p in need:
        if not p.exists():
            fail(f"missing file: {p}", errors)
    if errors:
        return 1

    sentences = json.loads((work / "steps" / "01-sentences" / "sentences.json").read_text(encoding="utf-8"))
    grouping = json.loads((work / "steps" / "03-grouping" / "grouping.json").read_text(encoding="utf-8"))
    ratings = json.loads((work / "steps" / "04-attributes" / "ratings.json").read_text(encoding="utf-8"))
    weapons = json.loads((work / "steps" / "05-weapons" / "weapons.json").read_text(encoding="utf-8"))
    phases = json.loads((work / "steps" / "06-phases" / "phases.json").read_text(encoding="utf-8"))
    phases_out = json.loads((work / "outputs" / "phases.json").read_text(encoding="utf-8"))
    priorities = json.loads((work / "steps" / "07-priorities" / "priorities.json").read_text(encoding="utf-8"))
    priorities_out = json.loads((work / "outputs" / "priorities.json").read_text(encoding="utf-8"))
    pitfalls = json.loads((work / "steps" / "08-pitfalls" / "pitfalls.json").read_text(encoding="utf-8"))
    pitfalls_out = json.loads((work / "outputs" / "pitfalls.json").read_text(encoding="utf-8"))
    candidates = json.loads((work / "steps" / "08-pitfalls" / "candidates.json").read_text(encoding="utf-8"))
    guide = json.loads((work / "steps" / "09-assemble" / "guide.json").read_text(encoding="utf-8"))
    guide_out = json.loads((work / "outputs" / "guide.json").read_text(encoding="utf-8"))
    manifest = json.loads((work / "inputs" / "manifest.json").read_text(encoding="utf-8"))

    sent_texts = {s["text"] for s in sentences if isinstance(s, dict)}

    def _check_quotes(tag: str, qs, qd):
        if not isinstance(qs, list) or not qs:
            fail(f"{tag} quotes must be non-empty array", errors)
            return
        if len(qs) != len(set(qs)):
            fail(f"{tag} quotes must be deduped (展示去重)", errors)
        for q in qs:
            if q not in sent_texts:
                fail(f"{tag} quote must equal sentences text (逐字原文): {str(q)[:60]}", errors)
                break
        if not isinstance(qd, list) or len(qd) != len(qs):
            fail(f"{tag} quote_details must parallel quotes", errors)
            return
        for d in qd[:2]:
            if "quote" not in d or "context" not in d:
                fail(f"{tag} quote_details missing quote/context", errors)
                break

    # --- 06-phases (#63: frozen fewshot + segmentation/wording, N不定, 运营波次自定义) ---
    try:
        _buckets = json.loads((work / "steps" / "06-phases" / "buckets.json").read_text(encoding="utf-8"))
    except Exception:
        fail("missing steps/06-phases/buckets.json (segmentation, 缺节即 fail)", errors)
        _buckets = []
    try:
        _wordings = json.loads((work / "steps" / "06-phases" / "wordings.json").read_text(encoding="utf-8"))
    except Exception:
        fail("missing steps/06-phases/wordings.json (wording, 缺节即 fail)", errors)
        _wordings = []
    if not isinstance(_buckets, list) or not _buckets:
        fail("buckets must be non-empty array (N不定但>=1)", errors)
        _buckets = []
    if not isinstance(_wordings, list) or not _wordings:
        fail("wordings must be non-empty array (N==buckets N)", errors)
        _wordings = []
    try:
        _meta06 = json.loads((work / "inputs" / "meta.json").read_text(encoding="utf-8"))
    except Exception:
        _meta06 = {}
    _chapter_titles = {str(c.get("title")) for c in ((_meta06 or {}).get("chapters") or []) if isinstance(c, dict)}
    _b_phases = [b.get("phase") for b in _buckets if isinstance(b, dict)]
    if len(_b_phases) != len(set(_b_phases)):
        fail("buckets phase 须互异", errors)
    for b in _buckets:
        if not isinstance(b, dict):
            fail("buckets entry must be object", errors)
            continue
        for k in ("phase", "waves", "quotes", "quote_details"):
            if k not in b:
                fail(f"buckets missing {k}: {b.get('phase')}", errors)
        if b.get("phase") in _chapter_titles:
            fail(f"buckets phase 不许抄作者章题: {b.get('phase')}", errors)
        if not isinstance(b.get("waves"), str):
            fail(f"buckets waves 须为字符串: {b.get('phase')}", errors)
        elif str(b.get("waves", "")).strip():
            _wl = str(b.get("waves", "")).lower()
            _joined = " ".join(b.get("quotes", []) if isinstance(b.get("quotes"), list) else []).lower()
            if _wl not in _joined:
                _want = []
                for _m in re.finditer(r"wave\s*\d+", _wl):
                    _want.append(_m.group(0))
                for _kw in ("horde", "elite", "boss", "final", "peacock", "mini", "whale", "wave"):
                    if _kw in _wl and _kw not in _want:
                        _want.append(_kw)
                if not _want or not all(_tk in _joined for _tk in _want):
                    fail(f"buckets waves 须原话作证: {b.get('phase')}={b.get('waves')}", errors)
        _bq = b.get("quotes", [])
        if not isinstance(_bq, list) or not _bq:
            fail(f"buckets quotes 须非空: {b.get('phase')}", errors)
            _bq = []
        if isinstance(_bq, list) and len(_bq) != len(set(_bq)):
            fail(f"buckets quotes 须去重: {b.get('phase')}", errors)
        for q in _bq:
            if q not in sent_texts:
                fail(f"buckets quotes 须逐字: {b.get('phase')}", errors)
                break
        _bqd = b.get("quote_details", [])
        if not isinstance(_bqd, list) or len(_bqd) != len(_bq):
            fail(f"buckets quote_details 须平行: {b.get('phase')}", errors)
    _all_bq = [q for b in _buckets if isinstance(b, dict) for q in (b.get("quotes", []) if isinstance(b.get("quotes"), list) else [])]
    if len(_all_bq) != len(set(_all_bq)):
        fail("buckets 桶间不重叠", errors)
    if len(_wordings) != len(_buckets):
        fail(f"wordings N 须==buckets N: 期望 {len(_buckets)}, 实得 {len(_wordings)}", errors)
    _w_by = {w.get("phase"): w for w in _wordings if isinstance(w, dict)}
    if set(_w_by.keys()) != set(_b_phases):
        fail(f"wordings phase 须==buckets 自洽: 期望 {sorted(_b_phases)}, 实得 {sorted(_w_by.keys())}", errors)
    import re as _re6
    _short_re6 = _re6.compile(r'原话["“]([^"”]+)["”]')
    for w in _wordings:
        if not isinstance(w, dict):
            continue
        for k in ("phase", "goal", "focus", "pivot", "extra_quotes"):
            if k not in w:
                fail(f"wordings missing {k}: {w.get('phase')}", errors)
        for k in ("goal", "focus", "pivot"):
            _v = str(w.get(k, ""))
            if len(_v.strip()) < 8:
                fail(f"wordings {k} 须>=8字: {w.get('phase')}", errors)
            if _v.strip() in sent_texts:
                fail(f"wordings {k} 整句复制 quote: {w.get('phase')}", errors)
            _shorts = [s.strip() for s in _short_re6.findall(_v) if s.strip()]
            if not _shorts:
                fail(f"wordings {k} 缺短引标记: {w.get('phase')}", errors)
            _bq0 = []
            for _b in _buckets:
                if isinstance(_b, dict) and _b.get("phase") == w.get("phase"):
                    _bq0 = _b.get("quotes", [])
                    break
            _allowed = set(_bq0) | set(w.get("extra_quotes", []) if isinstance(w.get("extra_quotes"), list) else [])
            for _s in _shorts:
                if not any(_s in _q for _q in _allowed if isinstance(_q, str)):
                    fail(f"wordings {k} 短引须出自本桶或 extra: {w.get('phase')}", errors)
                    break
        _ex = w.get("extra_quotes", [])
        if not isinstance(_ex, list):
            fail(f"wordings extra_quotes 须数组: {w.get('phase')}", errors)
            _ex = []
        if len(_ex) != len(set(_ex)):
            fail(f"wordings extra_quotes 须去重: {w.get('phase')}", errors)
        _bq0 = []
        for _b in _buckets:
            if isinstance(_b, dict) and _b.get("phase") == w.get("phase"):
                _bq0 = _b.get("quotes", []) if isinstance(_b.get("quotes"), list) else []
                break
        for q in _ex:
            if q not in sent_texts:
                fail(f"wordings extra 须逐字: {w.get('phase')}", errors)
                break
            if q in _bq0:
                fail(f"wordings extra 须真桶外: {w.get('phase')}", errors)
                break
    if not isinstance(phases, list) or len(phases) != len(_buckets):
        fail(f"phases must be N==buckets N, got {len(phases) if isinstance(phases, list) else type(phases)}", errors)
    else:
        for p in phases:
            for k in ("phase", "waves", "goal", "focus", "pivot", "quotes"):
                if k not in p or (isinstance(p[k], str) and not p[k].strip() and k not in ("waves",)):
                    fail(f"phases missing {k}: {p.get('phase')}", errors)
            _bq = []
            _bw = ""
            for b in (_buckets if isinstance(_buckets, list) else []):
                if isinstance(b, dict) and b.get("phase") == p.get("phase"):
                    _bq = b.get("quotes", []) if isinstance(b.get("quotes", []), list) else []
                    _bw = b.get("waves", "")
                    break
            if p.get("phase") not in _b_phases:
                fail(f"phases phase 须在 buckets 内: {p.get('phase')}", errors)
                continue
            if str(p.get("waves", "")) != str(_bw):
                fail(f"phases waves 须==buckets: {p.get('phase')}", errors)
            if len(str(p.get("goal", ""))) < 8 or len(str(p.get("focus", ""))) < 8 or len(str(p.get("pivot", ""))) < 8:
                fail(f"phases goal/focus/pivot too short: {p.get('phase')}", errors)
            qs = p.get("quotes", [])
            qd = p.get("quote_details", [])
            if not isinstance(qs, list) or not qs:
                fail(f"phases quotes 须非空: {p.get('phase')}", errors)
                qs = []
            if isinstance(qs, list) and _bq and list(qs[:len(_bq)]) != list(_bq):
                fail(f"phases 桶内前缀须等于buckets: {p.get('phase')}", errors)
            _in_n = len(_bq) if _bq else 0
            _check_quotes(f"phases {p.get('phase')}", qs, qd)
            for d in (qd[_in_n:] if isinstance(qd, list) else []):
                if not isinstance(d, dict) or d.get("out_of_window") is not True:
                    fail(f"phases 桶外补须标 out_of_window:true: {p.get('phase')}", errors)
                    break
            for k in ("goal", "focus", "pivot"):
                v = str(p.get(k, "")).strip()
                if v in qs:
                    fail(f"phases {k} 整句复制 quote: {p.get('phase')}", errors)
            blob = str(p.get("goal", "")) + str(p.get("focus", "")) + str(p.get("pivot", ""))
            if ("按本章节奏来" in blob or "转向下一章衔接点" in blob):
                warns.append(f"WARN: phases 疑模板黑话: {p.get('phase')}")
    if phases != phases_out:
        fail("outputs/phases.json must equal steps/06-phases/phases.json", errors)
    try:
        _few06_run = (work / "steps" / "06-phases" / "fewshot.md").read_bytes()
        _few06_repo = (REPO / "prompts" / "step06-phases-fewshot.md").read_bytes()
        if _few06_run != _few06_repo:
            fail("steps/06-phases/fewshot.md must equal repo FROZEN fewshot", errors)
    except Exception:
        fail("steps/06-phases/fewshot.md 读失败", errors)
    if not (work / "steps" / "06-phases" / "wordings.json").exists():
        fail("steps/06-phases/wordings.json 缺失", errors)
    if not (work / "steps" / "06-phases" / "segmentation.json").exists():
        fail("steps/06-phases/segmentation.json 缺失", errors)
    for _i, _b in enumerate(_buckets):
        _tag = f"{_i:02d}"
        _pp = work / "steps" / "06-phases" / "per_phase" / f"{_tag}.json"
        if not _pp.exists():
            _glob = list((work / "steps" / "06-phases" / "per_phase").glob("*.json")) if (work / "steps" / "06-phases" / "per_phase").exists() else []
            if len(_glob) != len(_buckets):
                fail(f"steps/06-phases/per_phase 缺 {_tag} ({_b.get('phase')})", errors)
                break
    _log06 = work / "steps" / "06-phases" / "agent-segmentation.log.jsonl"
    if not _log06.exists() or _log06.stat().st_size == 0:
        fail("06审计节点缺log: agent-segmentation.log.jsonl", errors)
    _wlogs = list((work / "steps" / "06-phases").glob("agent-wording-*.log.jsonl"))
    if len(_wlogs) != len(_buckets):
        fail(f"06审计节点缺wording log: 期望 {len(_buckets)} 个 agent-wording-*.log.jsonl, 实得 {len(_wlogs)}", errors)


    # --- 07-priorities (#62: frozen fewshot + priority-ranking 单 agent, shape only) ---
    # 新口径: {upgrades[N], shop[N]} 每项 {name,kind,why,how_to_get,quotes,analysis,quote_details}.
    # N 动态由 agent 定 (码只验非空, 不验断层); shop ⊆ grouping candidates 且禁 ban 组;
    # upgrades ⊆ ratings term_en; quotes 逐字; why 短引逐字; 退役断层/拒绝动词表码逻辑.
    if not isinstance(priorities, dict) or "upgrades" not in priorities or "shop" not in priorities:
        fail("priorities must be {upgrades[N], shop[N]} (N动态由agent定, 码只验非空)", errors)
        ups, shs = [], []
    else:
        ups, shs = priorities["upgrades"], priorities["shop"]
    if not (isinstance(ups, list) and len(ups) >= 1):
        fail(f"priorities upgrades must be N>=1 (Top1意图由agent保), got {len(ups) if isinstance(ups, list) else type(ups)}", errors)
    if not (isinstance(shs, list) and len(shs) >= 1):
        fail(f"priorities shop must be N>=1 (Top1意图由agent保), got {len(shs) if isinstance(shs, list) else type(shs)}", errors)
    rating_names = {r.get("term_en") for r in ratings if isinstance(r, dict)}
    cand_names07 = {g.get("name_en") for g in grouping if isinstance(g, dict)}
    ban_names07 = {g.get("name_en") for g in grouping
                   if isinstance(g, dict) and g.get("group") == "ban"}
    import re as _re7
    _short_re7 = _re7.compile(r'原话["“]([^"”]+)["”]')
    for u in (ups if isinstance(ups, list) else []):
        for k in ("name", "kind", "why", "how_to_get", "quotes", "analysis"):
            if k not in u or (isinstance(u[k], str) and not u[k].strip()):
                fail(f"priorities upgrades missing {k}: {u.get('name')}", errors)
        if u.get("kind") != "upgrade":
            fail(f"priorities upgrades kind must be upgrade: {u.get('name')}", errors)
        if u.get("name") not in rating_names:
            fail(f"priorities upgrades must be in ratings term_en (幻觉即 fail): {u.get('name')}", errors)
        if len(str(u.get("why", ""))) < 8 or len(str(u.get("how_to_get", ""))) < 8:
            fail(f"priorities upgrades why/how_to_get too short: {u.get('name')}", errors)
        if len(str(u.get("analysis", "")).strip()) < 4:
            fail(f"priorities upgrades analysis must be nonempty: {u.get('name')}", errors)
        _qs = u.get("quotes", [])
        _shorts = [s.strip() for s in _short_re7.findall(str(u.get("why", ""))) if s.strip()]
        if not _shorts:
            fail(f"priorities upgrades why 缺短引标记 原话\"...\": {u.get('name')}", errors)
        for _s in _shorts:
            if not any(_s in _q for _q in _qs if isinstance(_q, str)):
                fail(f"priorities upgrades why 短引须逐字出自 quotes: {u.get('name')}", errors)
                break
        _check_quotes(f"priorities upgrade {u.get('name')}", _qs, u.get("quote_details", []))
    for s in (shs if isinstance(shs, list) else []):
        for k in ("name", "kind", "why", "how_to_get", "quotes", "analysis"):
            if k not in s or (isinstance(s[k], str) and not s[k].strip()):
                fail(f"priorities shop missing {k}: {s.get('name')}", errors)
        if s.get("kind") != "shop":
            fail(f"priorities shop kind must be shop: {s.get('name')}", errors)
        if s.get("name") not in cand_names07:
            fail(f"priorities shop must be in grouping candidates (幻觉即 fail): {s.get('name')}", errors)
        if s.get("name") in ban_names07:
            fail(f"priorities shop ban 件禁入 TopN: {s.get('name')}", errors)
        if len(str(s.get("why", ""))) < 8 or len(str(s.get("how_to_get", ""))) < 8:
            fail(f"priorities shop why/how_to_get too short: {s.get('name')}", errors)
        if len(str(s.get("analysis", "")).strip()) < 4:
            fail(f"priorities shop analysis must be nonempty: {s.get('name')}", errors)
        _qs = s.get("quotes", [])
        _shorts = [x.strip() for x in _re7.compile(r'原话["“]([^"”]+)["”]').findall(str(s.get("why", ""))) if x.strip()]
        if not _shorts:
            fail(f"priorities shop why 缺短引标记 原话\"...\": {s.get('name')}", errors)
        for _x in _shorts:
            if not any(_x in _q for _q in _qs if isinstance(_q, str)):
                fail(f"priorities shop why 短引须逐字出自 quotes: {s.get('name')}", errors)
                break
        _check_quotes(f"priorities shop {s.get('name')}", _qs, s.get("quote_details", []))
    if priorities != priorities_out:
        fail("outputs/priorities.json must equal steps/07-priorities/priorities.json", errors)
    # 07 运行快照 + 审计节点: fewshot 单本须与 repo FROZEN 逐字节一致, ranking 落盘, log 可查
    try:
        _few07_run = (work / "steps" / "07-priorities" / "fewshot.md").read_bytes()
        _few07_repo = (REPO / "prompts" / "step07-priorities-fewshot.md").read_bytes()
        if _few07_run != _few07_repo:
            fail("steps/07-priorities/fewshot.md must equal repo FROZEN fewshot (逐字节, 重跑 07 即回填)", errors)
    except Exception:
        fail("steps/07-priorities/fewshot.md 读失败 (缺运行快照, 重跑 07 即回填)", errors)
    if not (work / "steps" / "07-priorities" / "ranking.json").exists():
        fail("steps/07-priorities/ranking.json 缺失 (终判, 缺节即 fail)", errors)
    _log07 = work / "steps" / "07-priorities" / "agent-ranking.log.jsonl"
    if not _log07.exists() or _log07.stat().st_size == 0:
        fail("07审计节点缺log (入参不可查, 重跑07回填): agent-ranking.log.jsonl", errors)

    # --- 08-pitfalls (两跳: 种子池 + 种子链约束, 闭集词表已废) ---
    try:
        _cands = json.loads((work / "steps" / "08-pitfalls" / "candidates.json").read_text(encoding="utf-8"))
    except Exception:
        fail("missing steps/08-pitfalls/candidates.json (先跑 step08 第一跳召回)", errors)
        _cands = []
    _pool = {c.get("quote") for c in (_cands if isinstance(_cands, list) else []) if isinstance(c, dict)}
    if not isinstance(pitfalls, list) or len(pitfalls) < 3:
        fail(f"pitfalls must be >=3, got {len(pitfalls) if isinstance(pitfalls, list) else type(pitfalls)}", errors)
    else:
        for p in pitfalls:
            for k in ("title", "severity", "why", "how_to_avoid", "quotes", "kind", "quote", "reason", "inferred", "seeds", "extra"):
                if k not in p:
                    fail(f"pitfalls missing {k}: {p.get('title')}", errors)
            if p.get("severity") not in ("fatal", "risky", "trap"):
                fail(f"pitfalls severity must be fatal/risky/trap: {p.get('title')}", errors)
            if p.get("kind") not in ("anchor", "discretion"):
                fail(f"pitfalls kind must be anchor/discretion: {p.get('title')}", errors)
            akeys = p.get("anchors", [])
            if not isinstance(akeys, list):
                fail(f"pitfalls anchors must be array: {p.get('title')}", errors)
                akeys = []
            seeds = p.get("seeds", [])
            extra = p.get("extra", [])
            if not isinstance(seeds, list) or not isinstance(extra, list):
                fail(f"pitfalls seeds/extra must be arrays: {p.get('title')}", errors)
                seeds, extra = [], []
            want_kind = "anchor" if akeys else "discretion"
            if p.get("kind") != want_kind:
                fail(f"pitfalls kind须与anchors一致 (有锚anchor/无锚discretion): {p.get('title')}", errors)
            if (p.get("anchor") or None) != (akeys[0] if akeys else None):
                fail(f"pitfalls anchor须=anchors[0]: {p.get('title')}", errors)
            if list(p.get("quotes", []) if isinstance(p.get("quotes"), list) else []) != list(seeds) + list(extra):
                fail(f"pitfalls quotes须=seeds+extra原序: {p.get('title')}", errors)
            if len(str(p.get("why", ""))) < 8 or len(str(p.get("how_to_avoid", ""))) < 8:
                fail(f"pitfalls why/how_to_avoid too short: {p.get('title')}", errors)
            if not isinstance(p.get("reason"), str) or len(p["reason"].strip()) < 4:
                fail(f"pitfalls missing reason (分组/扩展依据, 锚定条也要): {p.get('title')}", errors)
            if not isinstance(p.get("inferred"), bool):
                fail(f"pitfalls inferred must be bool: {p.get('title')}", errors)
            if want_kind == "anchor" and p.get("inferred") is not False:
                fail(f"pitfalls 锚定条inferred须false: {p.get('title')}", errors)
            if want_kind == "discretion" and p.get("inferred") is not True:
                fail(f"pitfalls 裁量条inferred须true: {p.get('title')}", errors)
            _check_quotes(f"pitfalls {p.get('title')}", p.get("quotes", []), p.get("quote_details", []))
            if p.get("quote") not in (p.get("quotes", []) if isinstance(p.get("quotes"), list) else []):
                fail(f"pitfalls quote须等于quotes成员: {p.get('title')}", errors)
            if want_kind == "anchor" and (p.get("quotes", []) or [None])[0] not in seeds:
                fail(f"pitfalls 锚定条quotes[0]须是种子直引: {p.get('title')}", errors)
            # (#50: take 系出局走 prompt 锚规则 + 召回约束, 代码侧不点名; merge 只校验种子链, 不做按名过滤)
            if want_kind == "anchor" and not seeds:
                fail(f"pitfalls 锚定条至少一句链回seed: {p.get('title')}", errors)
            for q in seeds:
                if q not in _pool:
                    fail(f"pitfalls seed须出自种子池逐字: {p.get('title')} :: {str(q)[:40]}", errors)
                    break
            for q in extra:
                if q not in sent_texts:
                    fail(f"pitfalls extra须出自sentences逐字: {p.get('title')} :: {str(q)[:40]}", errors)
                    break
            for a in akeys:
                if not any(str(a).lower() in str(q).lower() for q in seeds):
                    fail(f"pitfalls anchor须出自本条种子句逐字: {p.get('title')}={a}", errors)
                    break
    if pitfalls != pitfalls_out:
        fail("outputs/pitfalls.json must equal steps/08-pitfalls/pitfalls.json", errors)

    # --- 08-candidates.json (召回池实况: 全捞不取舍, 审计漏斗面板直读) ---
    if not isinstance(candidates, list) or not candidates:
        fail("candidates must be non-empty array (代码召回全捞)", errors)
    else:
        _cquotes = [c.get("quote") for c in candidates if isinstance(c, dict)]
        if len(_cquotes) != len(set(_cquotes)):
            fail("candidates quotes must be deduped", errors)
        for c in candidates:
            if not isinstance(c, dict) or not isinstance(c.get("quote"), str) or not c["quote"].strip():
                fail("candidates entry must have quote", errors)
                break
            if c["quote"] not in sent_texts:
                fail(f"candidates quote must equal sentences text: {str(c['quote'])[:60]}", errors)
                break
            if not isinstance(c.get("signals"), list) or not c["signals"]:
                fail("candidates entry must have non-empty signals", errors)
                break
            # (#50: 召回纯标记 + 情态约束, 不点名; take 系出局走 prompt, candidates 允许警告标记句含 taken 件名, 由 agent 提名时剔除)

    # --- 09-assemble ---
    if guide != guide_out:
        fail("outputs/guide.json must equal steps/09-assemble/guide.json (双写一致)", errors)
    for k in ("slug", "variant", "sha", "groups", "ratings", "weapons", "phases", "priorities", "pitfalls"):
        if k not in guide:
            fail(f"guide missing {k}", errors)
    if guide.get("groups") != grouping:
        fail("guide.groups must equal steps/03-grouping/grouping.json (聚合一致)", errors)
    if guide.get("ratings") != ratings:
        fail("guide.ratings must equal steps/04-attributes/ratings.json", errors)
    if guide.get("weapons") != weapons:
        fail("guide.weapons must equal steps/05-weapons/weapons.json", errors)
    if guide.get("phases") != phases:
        fail("guide.phases must equal steps/06-phases/phases.json", errors)
    if guide.get("priorities") != priorities:
        fail("guide.priorities must equal steps/07-priorities/priorities.json", errors)
    if guide.get("pitfalls") != pitfalls:
        fail("guide.pitfalls must equal steps/08-pitfalls/pitfalls.json", errors)
    expect_sha = (manifest.get("sources") or [{}])[0].get("sha1", "")
    if guide.get("sha") != expect_sha or not expect_sha:
        fail(f"guide.sha must equal manifest sha1 ({str(expect_sha)[:8]})", errors)
    actual_sha = hashlib.sha1((work / "inputs" / "source.vtt").read_bytes()).hexdigest()
    if actual_sha != expect_sha:
        fail(f"sha mismatch: manifest {str(expect_sha)[:8]} vs actual {actual_sha[:8]}", errors)

    # --- audit 常设对应节 (check 与审计节一一对应, 缺节即 fail; 06-09 须为实节) ---
    audit_html = (REPO / "templates" / "audit.html").read_text(encoding="utf-8")
    for marker in ("audit-06-phases", "audit-07-priorities", "audit-08-pitfalls", "audit-09-assemble",
                   "steps/06-phases", "steps/07-priorities", "steps/08-pitfalls", "steps/09-assemble",
                   "steps/06-phases/phases.json", "steps/07-priorities/priorities.json",
                   "steps/08-pitfalls/pitfalls.json", "steps/08-pitfalls/candidates.json", "steps/09-assemble/guide.json"):
        if marker not in audit_html:
            fail(f"audit.html 缺对应节 (一一对应): {marker}", errors)
    # 实节渲染 (非空占位): 须有卡片渲染逻辑, 不只待加载文案
    for marker in ("appData.phases", "appData.priorities", "appData.pitfalls", "appData.assemble", "appData.candidates08"):
        if marker not in audit_html:
            fail(f"audit.html 缺 06-09 实节渲染 (须读 live 数据): {marker}", errors)

    if errors:
        print(f"FAIL: check_segment2 {len(errors)} errors")
        return 1
    for w in warns:
        print(w)
    print(f"OK: segment2 cleared, phases={len(phases)} upgrades={len(ups)} shop={len(shs)} "
          f"pitfalls={len(pitfalls)} sha={actual_sha[:8]}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
