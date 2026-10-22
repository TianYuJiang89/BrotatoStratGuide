#!/usr/bin/env python3
"""Machine check for B-段2 (#65 + #64 + #63): 06-phases + 07-priorities + 08-pitfalls + 09-assemble.

沿 check_segment1.py (schema + 去重 + quote 对句 + sha + audit 一一对应), 加:
- 06 (#63: frozen fewshot + segmentation/wording, N 不定, 运营波次自定义): buckets.json + wordings.json + per_phase/* + phases.json, 桶间不重叠, 桶内前缀须等于 buckets, 桶外补标 out_of_window, 小结≠原文
- 07 (#65: frozen fewshot + selection/wording 两段 agent, 双侧断层/动词表/verified 已退役): selection.json + per_item/* + priorities.json, shop∩T1=∅, shop∩ban=∅, N 动态非空, 短引+数字码保
- 08 (#64: frozen fewshot + discovery/wording 两段 agent, 警告子串召回已退役): candidates[{title,seeds,extra}] + wordings[{title,severity,why,how_to_avoid,reason,seeds,extra}] + per_pitfall/* + pitfalls.json, 桶间不重叠, ban 反向 allowlist, severity 三档保留
- 09: 双写一致 + 六节聚合一致 + sha 对上 manifest + source.vtt
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
        work / "steps" / "07-priorities" / "selection.json",
        work / "steps" / "07-priorities" / "fewshot.md",
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


    # --- 07-priorities (#65: frozen fewshot + selection/wording 两段 agent, 新口径) ---
    # 新口径: selection.json {upgrades[{name,quotes}],shop[{name,quotes}],synthesis{upgrade_view,shop_view,channel_rule,rhythm,exceptions}} (N 动态非空, 名在表, ban/T1 出局, synthesis 五句非空且点名)
    # + per_item/<NN>.json {name,why,how_to_get} (wording, N==selection, 带标签+synthesis+phases, 短引+数字码保, phases 数字禁进)
    # + priorities.json {upgrades[],shop[]} 每项 {name,kind,why,how_to_get,quotes,quote_details} (code 合并, 无 analysis).
    # N 动态由 agent 定 (码只验非空, 不验切分); shop ⊆ grouping candidates 且禁 ban 组且禁 T1; 
    # upgrades ⊆ ratings term_en (S/A 优先 B 可例外, 码只验名在表); quotes 逐字; why 短引逐字; 数字不丢 (phases/synthesis 数字禁进文案).
    # 退役: count 双侧码切/拒绝动词表/verified 门/T1 码规则/保底 Top1 码规则/why 沿 reason/07 读 verbs.
    try:
        _sel07 = json.loads((work / "steps" / "07-priorities" / "selection.json").read_text(encoding="utf-8"))
    except Exception:
        fail("missing steps/07-priorities/selection.json (先跑 step07 selection, 缺节即 fail)", errors)
        _sel07 = None
    if not isinstance(_sel07, dict) or "upgrades" not in _sel07 or "shop" not in _sel07 or "synthesis" not in _sel07:
        fail("selection must be {upgrades[N], shop[N], synthesis} (N动态由agent定, 码只验非空+synthesis五句)", errors)
        _sel_ups, _sel_shs = [], []
    else:
        _sel_ups, _sel_shs = _sel07["upgrades"], _sel07["shop"]
    if not (isinstance(_sel_ups, list) and len(_sel_ups) >= 1):
        fail(f"selection upgrades must be N>=1 (Top1意图由agent保), got {len(_sel_ups) if isinstance(_sel_ups, list) else type(_sel_ups)}", errors)
    if not (isinstance(_sel_shs, list) and len(_sel_shs) >= 1):
        fail(f"selection shop must be N>=1 (Top1意图由agent保), got {len(_sel_shs) if isinstance(_sel_shs, list) else type(_sel_shs)}", errors)
    rating_names = {r.get("term_en") for r in ratings if isinstance(r, dict)}
    cand_names07 = {g.get("name_en") for g in grouping if isinstance(g, dict)}
    ban_names07 = {g.get("name_en") for g in grouping
                   if isinstance(g, dict) and g.get("group") == "ban"}
    t1_names07 = {w.get("name_en") for w in (weapons.get("t1", []) if isinstance(weapons, dict) else [])
                  if isinstance(w, dict)}
    import re as _re7
    _short_re7 = _re7.compile(r'原话["“]([^"”]+)["”]')
    _sel_names: list = []
    for _arr, _key in ((_sel_ups, "upgrades"), (_sel_shs, "shop")):
        if not isinstance(_arr, list):
            continue
        for _e in _arr:
            if not isinstance(_e, dict):
                fail(f"selection {_key} entry must be object", errors)
                continue
            for _k in ("name", "quotes"):
                if _k not in _e:
                    fail(f"selection {_key} missing {_k}: {_e.get('name')}", errors)
            for _old in ("count", "why", "how_to_get", "analysis", "quote_details",
                          "kind", "verified", "verb", "tier", "confidence", "inferred"):
                if _old in _e:
                    fail(f"selection retired field must be absent: {_old} ({_e.get('name')})", errors)
            _nm = _e.get("name")
            _sel_names.append(_nm)
            if _key == "upgrades" and _nm not in rating_names:
                fail(f"selection upgrades must be in ratings term_en (幻觉即 fail): {_nm}", errors)
            if _key == "shop" and _nm not in cand_names07:
                fail(f"selection shop must be in grouping candidates (幻觉即 fail): {_nm}", errors)
            if _key == "shop" and _nm in ban_names07:
                fail(f"selection shop ban 件禁入 TopN: {_nm}", errors)
            if _key == "shop" and _nm in t1_names07:
                fail(f"selection shop T1 武器禁入 shop (shop∩T1=∅): {_nm}", errors)
            _qs = _e.get("quotes", [])
            _check_quotes(f"selection {_key} {_nm}", _qs, [{"quote": q, "context": "x"} for q in _qs] if isinstance(_qs, list) else [])
            # _check_quotes 需 quote_details 平行; selection 无 details, 此处只验逐字去重非空
            if isinstance(_qs, list):
                if not _qs:
                    fail(f"selection {_key} quotes 须非空: {_nm}", errors)
                if len(_qs) != len(set(_qs)):
                    fail(f"selection {_key} quotes 须去重: {_nm}", errors)
                for _q in _qs:
                    if _q not in sent_texts:
                        fail(f"selection {_key} quote 须逐字: {_nm} :: {str(_q)[:40]}", errors)
                        break
    if len(_sel_names) != len(set(_sel_names)):
        fail("selection upgrades+shop 须去重", errors)
    _syn07 = _sel07.get("synthesis") if isinstance(_sel07, dict) else None
    if not isinstance(_syn07, dict):
        fail("selection synthesis 须为对象 {upgrade_view,shop_view,channel_rule,rhythm,exceptions}", errors)
        _syn07 = {}
    for _k in ("upgrade_view", "shop_view", "channel_rule", "rhythm", "exceptions"):
        _v = _syn07.get(_k) if isinstance(_syn07, dict) else None
        if not isinstance(_v, str) or not _v.strip():
            fail(f"selection synthesis 缺 {_k} 非空", errors)
    _joined_syn = " ".join(str(_syn07.get(_k, "")) for _k in ("upgrade_view", "shop_view", "channel_rule", "rhythm", "exceptions")) if isinstance(_syn07, dict) else ""
    for _nm in _sel_names:
        if isinstance(_nm, str) and _nm and _nm not in _joined_syn:
            fail(f"selection synthesis 须点名 {_nm} (三句须覆盖每个 TopN)", errors)
    # per_item: N==selection, 每项 {name,why,how_to_get}, 短引+数字码保
    _n_sel = (len(_sel_ups) if isinstance(_sel_ups, list) else 0) + (len(_sel_shs) if isinstance(_sel_shs, list) else 0)
    for _i in range(_n_sel):
        _pp = work / "steps" / "07-priorities" / "per_item" / f"{_i:02d}.json"
        if not _pp.exists():
            fail(f"steps/07-priorities/per_item/{_i:02d}.json 缺失 (wording原始, 缺节即 fail)", errors)
            continue
        try:
            _pev07 = json.loads(_pp.read_text(encoding="utf-8"))
        except Exception:
            fail(f"per_item/{_i:02d}.json 非法 JSON", errors)
            continue
        if not isinstance(_pev07, dict):
            fail(f"per_item/{_i:02d}.json 须为对象", errors)
            continue
        for _k in ("name", "why", "how_to_get"):
            if _k not in _pev07:
                fail(f"per_item/{_i:02d}.json 缺 {_k}", errors)
        for _old in ("quotes", "analysis", "count", "quote_details", "verified", "verb"):
            if _old in _pev07:
                fail(f"per_item/{_i:02d}.json retired field must be absent: {_old}", errors)
        _pn, _pw, _ph = _pev07.get("name"), str(_pev07.get("why", "")), str(_pev07.get("how_to_get", ""))
        if _pn not in _sel_names:
            fail(f"per_item/{_i:02d}.json name 须==selection: {_pn}", errors)
        if len(_pw.strip()) < 8:
            fail(f"per_item/{_i:02d}.json why 须>=8字: {_pn}", errors)
        if len(_ph.strip()) < 2:
            fail(f"per_item/{_i:02d}.json how_to_get 缺件: {_pn}", errors)
        if not any(_k in _ph for _k in ("升级", "商店", "捡", "锁", "roll", "Roll")):
            fail(f"per_item/{_i:02d}.json how_to_get 缺通道词: {_pn}", errors)
        _shorts = [s.strip() for s in _short_re7.findall(_pw) if s.strip()]
        if not _shorts:
            fail(f"per_item/{_i:02d}.json why 缺短引标记 原话\"...\": {_pn}", errors)
        # 短引须出自 selection 对应项 quotes; 数字 ≥2 位须出自 quotes (编数字即 fail)
        _sel_qs: list = []
        for _arr in ((_sel_ups if isinstance(_sel_ups, list) else []) + (_sel_shs if isinstance(_sel_shs, list) else [])):
            if isinstance(_arr, dict) and _arr.get("name") == _pn:
                _sel_qs = _arr.get("quotes", []) if isinstance(_arr.get("quotes"), list) else []
                break
        for _s in _shorts:
            if not any(_s in _q for _q in _sel_qs if isinstance(_q, str)):
                fail(f"per_item/{_i:02d}.json why 短引须逐字出自 selection quotes: {_pn}", errors)
                break
        for _m in _re7.finditer(r"\d+", _pw + " " + _ph):
            _tok = _m.group(0)
            if len(_tok) >= 2 and _tok not in " ".join(_sel_qs):
                fail(f"per_item/{_i:02d}.json 编数字即 fail: {_tok} 不在 quotes 内 ({_pn})", errors)
                break
    if not isinstance(priorities, dict) or "upgrades" not in priorities or "shop" not in priorities:
        fail("priorities must be {upgrades[N], shop[N]} (N动态由agent定, 码只验非空)", errors)
        ups, shs = [], []
    else:
        ups, shs = priorities["upgrades"], priorities["shop"]
    if not (isinstance(ups, list) and len(ups) >= 1):
        fail(f"priorities upgrades must be N>=1 (Top1意图由agent保), got {len(ups) if isinstance(ups, list) else type(ups)}", errors)
    if not (isinstance(shs, list) and len(shs) >= 1):
        fail(f"priorities shop must be N>=1 (Top1意图由agent保), got {len(shs) if isinstance(shs, list) else type(shs)}", errors)
    # priorities N==selection N, quotes==selection, why/how==per_item
    if isinstance(_sel_ups, list) and isinstance(ups, list):
        if [u.get("name") for u in ups if isinstance(u, dict)] != [u.get("name") for u in _sel_ups if isinstance(u, dict)]:
            fail(f"priorities upgrades 须==selection 自洽: 期望 {[u.get('name') for u in _sel_ups if isinstance(u, dict)]}, 实得 {[u.get('name') for u in ups if isinstance(u, dict)]}", errors)
    if isinstance(_sel_shs, list) and isinstance(shs, list):
        if [s.get("name") for s in shs if isinstance(s, dict)] != [s.get("name") for s in _sel_shs if isinstance(s, dict)]:
            fail(f"priorities shop 须==selection 自洽: 期望 {[s.get('name') for s in _sel_shs if isinstance(s, dict)]}, 实得 {[s.get('name') for s in shs if isinstance(s, dict)]}", errors)
    for u in (ups if isinstance(ups, list) else []):
        if not isinstance(u, dict):
            continue
        for k in ("name", "kind", "why", "how_to_get", "quotes", "quote_details"):
            if k not in u or (isinstance(u[k], str) and not u[k].strip()):
                fail(f"priorities upgrades missing {k}: {u.get('name')}", errors)
        for _old in ("count", "analysis", "verified", "verb"):
            if _old in u:
                fail(f"priorities upgrades retired field must be absent: {_old} ({u.get('name')})", errors)
        if u.get("kind") != "upgrade":
            fail(f"priorities upgrades kind must be upgrade: {u.get('name')}", errors)
        if u.get("name") not in rating_names:
            fail(f"priorities upgrades must be in ratings term_en (幻觉即 fail): {u.get('name')}", errors)
        if len(str(u.get("why", ""))) < 8 or len(str(u.get("how_to_get", ""))) < 2:
            fail(f"priorities upgrades why/how_to_get too short: {u.get('name')}", errors)
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
        if not isinstance(s, dict):
            continue
        for k in ("name", "kind", "why", "how_to_get", "quotes", "quote_details"):
            if k not in s or (isinstance(s[k], str) and not s[k].strip()):
                fail(f"priorities shop missing {k}: {s.get('name')}", errors)
        for _old in ("count", "analysis", "verified", "verb"):
            if _old in s:
                fail(f"priorities shop retired field must be absent: {_old} ({s.get('name')})", errors)
        if s.get("kind") != "shop":
            fail(f"priorities shop kind must be shop: {s.get('name')}", errors)
        if s.get("name") not in cand_names07:
            fail(f"priorities shop must be in grouping candidates (幻觉即 fail): {s.get('name')}", errors)
        if s.get("name") in ban_names07:
            fail(f"priorities shop ban 件禁入 TopN: {s.get('name')}", errors)
        if s.get("name") in t1_names07:
            fail(f"priorities shop T1 武器禁入 shop (shop∩T1=∅): {s.get('name')}", errors)
        if len(str(s.get("why", ""))) < 8 or len(str(s.get("how_to_get", ""))) < 2:
            fail(f"priorities shop why/how_to_get too short: {s.get('name')}", errors)
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
    # 07 运行快照 + 审计节点: fewshot 单本须与 repo FROZEN 逐字节一致, selection 落盘, log 可查
    try:
        _few07_run = (work / "steps" / "07-priorities" / "fewshot.md").read_bytes()
        _few07_repo = (REPO / "prompts" / "step07-priorities-fewshot.md").read_bytes()
        if _few07_run != _few07_repo:
            fail("steps/07-priorities/fewshot.md must equal repo FROZEN fewshot (逐字节, 重跑 07 即回填)", errors)
    except Exception:
        fail("steps/07-priorities/fewshot.md 读失败 (缺运行快照, 重跑 07 即回填)", errors)
    if _sel07 is None:
        fail("steps/07-priorities/selection.json 缺失 (终判, 缺节即 fail)", errors)
    _log07s = work / "steps" / "07-priorities" / "agent-selection.log.jsonl"
    if not _log07s.exists() or _log07s.stat().st_size == 0:
        fail("07审计节点缺log (入参不可查, 重跑07回填): agent-selection.log.jsonl", errors)
    _wlogs07 = list((work / "steps" / "07-priorities").glob("agent-wording-*.log.jsonl"))
    if len(_wlogs07) != _n_sel:
        fail(f"07审计节点缺wording log: 期望 {_n_sel} 个 agent-wording-*.log.jsonl, 实得 {len(_wlogs07)}", errors)

    # --- 08-pitfalls (#64: frozen fewshot + discovery/wording) ---
    try:
        _cands08 = json.loads((work / "steps" / "08-pitfalls" / "candidates.json").read_text(encoding="utf-8"))
    except Exception:
        fail("missing steps/08-pitfalls/candidates.json (先跑 step08 discovery)", errors)
        _cands08 = None
    try:
        _wordings08 = json.loads((work / "steps" / "08-pitfalls" / "wordings.json").read_text(encoding="utf-8"))
    except Exception:
        fail("missing steps/08-pitfalls/wordings.json (先跑 step08 wording)", errors)
        _wordings08 = None
    _ban08 = {g.get("name_en") for g in (grouping if isinstance(grouping, list) else [])
              if isinstance(g, dict) and g.get("group") == "ban"}
    # candidates: new schema [{title,seeds,extra}], N不定可空数组诚实交
    if not isinstance(_cands08, list):
        fail("candidates must be array (discovery, N不定可空)", errors)
        _cands08 = []
    else:
        _seen08 = set()
        for _c in _cands08:
            if not isinstance(_c, dict):
                fail("candidates entry must be object", errors)
                continue
            for _k in ("title", "seeds", "extra"):
                if _k not in _c:
                    fail(f"candidates missing {_k}: {_c.get('title')}", errors)
            for _old in ("quote", "signals", "anchors", "inferred", "kind", "anchor",
                         "severity", "why", "how_to_avoid", "reason", "count", "quote_details"):
                if _old in _c:
                    fail(f"candidates retired field must be absent: {_old}", errors)
            _t = _c.get("title")
            if not isinstance(_t, str) or not _t.strip():
                fail("candidates title must be nonempty", errors)
            _s = _c.get("seeds", [])
            _e = _c.get("extra", [])
            if not isinstance(_s, list) or not _s:
                fail(f"candidates seeds must be non-empty (空证据即 fail): {_t}", errors)
                _s = []
            if not isinstance(_e, list):
                fail(f"candidates extra must be array: {_t}", errors)
                _e = []
            if isinstance(_s, list) and len(_s) != len(set(_s)):
                fail(f"candidates seeds must be deduped: {_t}", errors)
            if isinstance(_e, list) and len(_e) != len(set(_e)):
                fail(f"candidates extra must be deduped: {_t}", errors)
            if isinstance(_s, list) and isinstance(_e, list) and set(_s) & set(_e):
                fail(f"candidates seeds/extra must be disjoint (交叠即 fail): {_t}", errors)
            for _q in (list(_s) + list(_e) if isinstance(_s, list) and isinstance(_e, list) else []):
                if _q not in sent_texts:
                    fail(f"candidates quotes must be verbatim: {_t} :: {str(_q)[:40]}", errors)
                    break
                if _q in _seen08:
                    fail(f"candidates must be globally deduped (桶间不重叠): {str(_q)[:40]}", errors)
                    break
            for _q in (list(_s) + list(_e) if isinstance(_s, list) and isinstance(_e, list) else []):
                _seen08.add(_q)
            for _q in (list(_s) + list(_e) if isinstance(_s, list) and isinstance(_e, list) else []):
                for _b in _ban08:
                    if _b and _b.lower() in str(_q).lower():
                        fail(f"candidates ban scope (坑不重复进): {_t}含ban名 {_b}", errors)
                        break
    # wordings: new schema, N==candidates 自洽
    if not isinstance(_wordings08, list):
        fail("wordings must be array (wordingxN)", errors)
        _wordings08 = []
    else:
        if len(_wordings08) != len(_cands08):
            fail(f"wordings N must == candidates N 自洽: 期望 {len(_cands08)}, 实得 {len(_wordings08)}", errors)
        _wseen08 = set()
        for _w in _wordings08:
            if not isinstance(_w, dict):
                fail("wordings entry must be object", errors)
                continue
            for _k in ("title", "severity", "why", "how_to_avoid", "reason", "seeds", "extra"):
                if _k not in _w:
                    fail(f"wordings missing {_k}: {_w.get('title')}", errors)
            for _old in ("anchors", "inferred", "kind", "anchor", "quote", "signals", "count", "quote_details"):
                if _old in _w:
                    fail(f"wordings retired field must be absent: {_old} ({_w.get('title')})", errors)
            if _w.get("severity") not in ("fatal", "risky", "trap"):
                fail(f"wordings severity must be fatal/risky/trap: {_w.get('title')}", errors)
            if not isinstance(_w.get("why"), str) or len(str(_w.get("why", "")).strip()) < 8:
                fail(f"wordings why too short: {_w.get('title')}", errors)
            if not isinstance(_w.get("how_to_avoid"), str) or len(str(_w.get("how_to_avoid", "")).strip()) < 8:
                fail(f"wordings how_to_avoid too short: {_w.get('title')}", errors)
            if not isinstance(_w.get("reason"), str) or len(str(_w.get("reason", "")).strip()) < 4:
                fail(f"wordings missing reason: {_w.get('title')}", errors)
            _ws = _w.get("seeds", [])
            _we = _w.get("extra", [])
            if not isinstance(_ws, list) or not _ws:
                fail(f"wordings seeds must be non-empty (空证据即 fail): {_w.get('title')}", errors)
                _ws = []
            if not isinstance(_we, list):
                fail(f"wordings extra must be array: {_w.get('title')}", errors)
                _we = []
            if isinstance(_ws, list) and len(_ws) != len(set(_ws)):
                fail(f"wordings seeds must be deduped: {_w.get('title')}", errors)
            if isinstance(_we, list) and len(_we) != len(set(_we)):
                fail(f"wordings extra must be deduped: {_w.get('title')}", errors)
            if isinstance(_ws, list) and isinstance(_we, list) and set(_ws) & set(_we):
                fail(f"wordings seeds/extra must be disjoint (交叠即 fail): {_w.get('title')}", errors)
            for _q in (list(_ws) + list(_we) if isinstance(_ws, list) and isinstance(_we, list) else []):
                if _q not in sent_texts:
                    fail(f"wordings quotes must be verbatim: {_w.get('title')} :: {str(_q)[:40]}", errors)
                    break
                if _q in _wseen08:
                    fail(f"wordings must be globally deduped (桶间不重叠): {str(_q)[:40]}", errors)
                    break
            for _q in (list(_ws) + list(_we) if isinstance(_ws, list) and isinstance(_we, list) else []):
                _wseen08.add(_q)
            for _q in (list(_ws) + list(_we) if isinstance(_ws, list) and isinstance(_we, list) else []):
                for _b in _ban08:
                    if _b and _b.lower() in str(_q).lower():
                        fail(f"wordings ban scope (坑不重复进): {_w.get('title')}含ban名 {_b}", errors)
                        break
    # pitfalls: merge (quotes=seeds+extra原序, quote_details平行)
    if not isinstance(pitfalls, list):
        fail(f"pitfalls must be array, got {type(pitfalls)}", errors)
    else:
        if len(pitfalls) != len(_wordings08):
            fail(f"pitfalls N must == wordings N 自洽: 期望 {len(_wordings08)}, 实得 {len(pitfalls)}", errors)
        else:
            for _p, _w in zip(pitfalls, _wordings08):
                if not isinstance(_p, dict) or not isinstance(_w, dict):
                    fail("pitfalls/wordings entry must be object", errors)
                    continue
                for _k in ("title", "severity", "why", "how_to_avoid", "reason", "seeds", "extra", "quotes", "quote_details"):
                    if _k not in _p:
                        fail(f"pitfalls missing {_k}: {_p.get('title')}", errors)
                for _old in ("anchors", "inferred", "kind", "anchor", "quote", "signals"):
                    if _old in _p:
                        fail(f"pitfalls retired field must be absent: {_old} ({_p.get('title')})", errors)
                if _p.get("severity") not in ("fatal", "risky", "trap"):
                    fail(f"pitfalls severity must be fatal/risky/trap: {_p.get('title')}", errors)
                _ps = _p.get("seeds", [])
                _pe = _p.get("extra", [])
                if list(_p.get("quotes", []) if isinstance(_p.get("quotes"), list) else []) != list(_ps if isinstance(_ps, list) else []) + list(_pe if isinstance(_pe, list) else []):
                    fail(f"pitfalls quotes must == seeds+extra原序: {_p.get('title')}", errors)
                _check_quotes(f"pitfalls {_p.get('title')}", _p.get("quotes", []), _p.get("quote_details", []))
                for _q in (list(_ps) + list(_pe) if isinstance(_ps, list) and isinstance(_pe, list) else []):
                    for _b in _ban08:
                        if _b and _b.lower() in str(_q).lower():
                            fail(f"pitfalls ban scope (坑不重复进): {_p.get('title')}含ban名 {_b}", errors)
                            break
    if pitfalls != pitfalls_out:
        fail("outputs/pitfalls.json must equal steps/08-pitfalls/pitfalls.json", errors)
    # 08 运行快照 + 审计节点: fewshot单本须与repo FROZEN逐字节一致, per_pitfall落盘, log可查
    try:
        _few08_run = (work / "steps" / "08-pitfalls" / "fewshot.md").read_bytes()
        _few08_repo = (REPO / "prompts" / "step08-pitfalls-fewshot.md").read_bytes()
        if _few08_run != _few08_repo:
            fail("steps/08-pitfalls/fewshot.md must equal repo FROZEN fewshot (逐字节, 重跑08即回填)", errors)
    except Exception:
        fail("steps/08-pitfalls/fewshot.md 读失败 (缺运行快照, 重跑08即回填)", errors)
    if not (work / "steps" / "08-pitfalls" / "wordings.json").exists():
        fail("steps/08-pitfalls/wordings.json 缺失", errors)
    if not (work / "steps" / "08-pitfalls" / "discovery.json").exists():
        fail("steps/08-pitfalls/discovery.json 缺失 (discovery原始, 缺节即 fail)", errors)
    for _i in range(len(_wordings08) if isinstance(_wordings08, list) else 0):
        _pp = work / "steps" / "08-pitfalls" / "per_pitfall" / f"{_i:02d}.json"
        if not _pp.exists():
            fail(f"steps/08-pitfalls/per_pitfall/{_i:02d}.json 缺失 (wording原始, 缺节即 fail)", errors)
            break
        try:
            _pev08 = json.loads(_pp.read_text(encoding="utf-8"))
        except Exception:
            fail(f"per_pitfall/{_i:02d}.json 非法 JSON", errors)
            continue
        if not isinstance(_pev08, dict) or _pev08.get("severity") not in ("fatal", "risky", "trap"):
            fail(f"per_pitfall/{_i:02d}.json severity 须三档之一", errors)
    _log08d = work / "steps" / "08-pitfalls" / "agent-discovery.log.jsonl"
    if not _log08d.exists() or _log08d.stat().st_size == 0:
        fail("08审计节点缺log (入参不可查, 重跑08回填): agent-discovery.log.jsonl", errors)
    _wlogs08 = list((work / "steps" / "08-pitfalls").glob("agent-wording-*.log.jsonl"))
    if len(_wlogs08) != (len(_wordings08) if isinstance(_wordings08, list) else 0):
        fail(f"08审计节点缺wording log: 期望 {(len(_wordings08) if isinstance(_wordings08, list) else 0)} 个 agent-wording-*.log.jsonl, 实得 {len(_wlogs08)}", errors)

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
