#!/usr/bin/env python3
"""Machine check for B-段2 (#45 + #49): 06-phases + 07-priorities + 08-pitfalls + 09-assemble.

沿 check_segment1.py (schema + 去重 + quote 对句 + sha + audit 一一对应), 加:
- 06: N=8 作者 chapters 一章一段 (phase 名=章标题原文), 非空段 goal/focus/pivot + quotes 去重 + 对句,
  空段 quotes==[] + quote_details==[] + goal 写明非打法章 (类比 ratings `-`)
- 07 (#49 去 Top3 写死 + Peacock 按名顺延): upgrades 3 沿用 (全在 ratings S/A 内) + shop N 动态 (全在新 grouping must_take verified 内,
  无拒绝动词 + 最大断层 TopN + 保底 Top1), 每项 why/how_to_get/quotes[0]
- 08: >=3 条, severity 全在 fatal/risky/trap 内, 每条 why/how_to_avoid/quotes[0]
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

    # --- 06-phases (#45+C: 作者 chapters 一章一段, N=章节数(cyborg=8), phase 名=章标题原文) ---
    try:
        _meta = json.loads((work / "inputs" / "meta.json").read_text(encoding="utf-8"))
    except Exception:
        fail("missing inputs/meta.json for chapters timed 校验", errors)
        _meta = {}
    _chs = (_meta or {}).get("chapters") if isinstance(_meta, dict) else None
    if (not isinstance(_chs, list) or not _chs
            or any(not isinstance(c, dict) for c in _chs)):
        fail("meta.json chapters 非 timed 格式 ([{title,start,end}]): 先回填 Step00", errors)
        _chs = []
    expect_titles = [str(c.get("title")) for c in _chs] if _chs else []
    if not isinstance(phases, list) or (expect_titles and len(phases) != len(expect_titles)):
        fail(f"phases must be N={len(expect_titles)} (作者 chapters 一章一段), got {len(phases) if isinstance(phases, list) else type(phases)}", errors)
    elif expect_titles:
        got_ph = [p.get("phase") for p in phases]
        if got_ph != expect_titles:
            fail(f"phases phase 名须=章标题原文, got {got_ph}", errors)
        for p in phases:
            for k in ("phase", "waves", "goal", "focus", "pivot", "quotes"):
                if k not in p or (isinstance(p[k], str) and not p[k].strip()):
                    fail(f"phases missing {k}: {p.get('phase')}", errors)
            if len(str(p.get("goal", ""))) < 8 or len(str(p.get("focus", ""))) < 8 or len(str(p.get("pivot", ""))) < 8:
                fail(f"phases goal/focus/pivot too short: {p.get('phase')}", errors)
            rs = str(p.get("goal", "")) + str(p.get("focus", ""))
            if "字幕" in rs and "次" in rs and "原话" not in rs:
                warns.append(f"WARN: phases 疑计数泄漏: {p.get('phase')}")
            qs = p.get("quotes", [])
            qd = p.get("quote_details", [])
            if not qs:
                # 空段诚实空出: quotes==[] + details==[] + goal 写明非打法章
                if qs != [] or qd != []:
                    fail(f"phases 空段须 quotes==[] + quote_details==[]: {p.get('phase')}", errors)
                if "非打法章" not in str(p.get("goal", "")):
                    fail(f"phases 空段 goal 须写明非打法章: {p.get('phase')}", errors)
            else:
                # C: 窗内全量前缀须等于buckets, 窗外补不限条须标out_of_window
                try:
                    _bk = json.loads((work / "steps" / "06-phases" / "buckets.json").read_text(encoding="utf-8"))
                except Exception:
                    _bk = []
                _bq = []
                for b in (_bk if isinstance(_bk, list) else []):
                    if isinstance(b, dict) and b.get("phase") == p.get("phase"):
                        _bq = b.get("quotes", []) if isinstance(b.get("quotes", []), list) else []
                        break
                if _bq and list(qs[:len(_bq)]) != list(_bq):
                    fail(f"phases 窗内前缀须等于buckets (不可改写): {p.get('phase')}", errors)
                _in_n = len(_bq) if _bq else len(qs)

                _check_quotes(f"phases {p.get('phase')}", qs, qd)
                # 窗外补须标out_of_window:true
                for d in (qd[_in_n:] if isinstance(qd, list) else []):
                    if not isinstance(d, dict) or d.get("out_of_window") is not True:
                        fail(f"phases 窗外补须标 out_of_window:true: {p.get('phase')}", errors)
                        break
                # #45跟进: 三问人话质检 (FAIL=整句复制; WARN=模板黑话/无实体)
                for k in ("goal", "focus", "pivot"):
                    v = str(p.get(k, "")).strip()
                    if v in qs:
                        fail(f"phases {k} 整句复制 quote (须综合非复读): {p.get('phase')}", errors)
                blob = str(p.get("goal", "")) + str(p.get("focus", "")) + str(p.get("pivot", ""))
                if ("按本章节奏来" in blob or "转向下一章衔接点" in blob) and "原话" in blob:
                    warns.append(f"WARN: phases 疑模板黑话 (须具体动作+条件): {p.get('phase')}")
                low = blob.lower()
                entities = ("screwdriver", "minigun", "smg", "submachine", "nuke", "turret",
                            "pocket factory", "peacock", "whale", "elite", "boss", "horde",
                            "engineering", "ranged", "life steal", "coffee", "scar", "beanie",
                            "whistle", "tentacle", "scope", "wave 16", "wave 20", "halfway")
                if not any(e in low for e in entities):
                    warns.append(f"WARN: phases 无具体实体词 (武器/怪/波次至少一个): {p.get('phase')}")
    if phases != phases_out:
        fail("outputs/phases.json must equal steps/06-phases/phases.json", errors)

    # --- 07-priorities (#50: upgrades/shop 双断层动态, 去 Top3 写死 + 按名特判) ---
    if not isinstance(priorities, dict) or "upgrades" not in priorities or "shop" not in priorities:
        fail("priorities must be {upgrades[N], shop[N]} (升级断层动态N>=1 + 商店断层动态N>=1)", errors)
        ups, shs = [], []
    else:
        ups, shs = priorities["upgrades"], priorities["shop"]
    if not (isinstance(ups, list) and len(ups) >= 1):
        fail(f"priorities upgrades must be N>=1 动态 (保底 Top1), got {len(ups) if isinstance(ups, list) else type(ups)}", errors)
    if not (isinstance(shs, list) and len(shs) >= 1):
        fail(f"priorities shop must be N>=1 动态 (保底 Top1), got {len(shs) if isinstance(shs, list) else type(shs)}", errors)
    sa_names = {r.get("term_en") for r in ratings if r.get("rating") in ("S", "A")}
    mt_names = {g.get("name_en") for g in grouping if g.get("group") == "must_take"}
    mt_verified = {g.get("name_en"): g for g in grouping
                   if g.get("group") == "must_take" and g.get("confidence") == "verified"}
    # 通用顺延信号 (与 run_segment2.step07 同口径, 不点名, 不含泛 don't want)
    _REJECT = ("not taking", "not take", "don't take", "do not take",
               "don't buy", "do not buy", "not buying",
               "don't pick", "do not pick", "not picking",
               "don't lock", "do not lock",
               "skip", "avoid", "ban", "recycle", "sell",
               "passed on", "ignoring", "ignored", "not interested",
               "don't want to take", "do not want to take",
               "don't want to buy", "do not want to buy")

    def _has_refusal(g):
        qall = " ".join(g.get("quotes", [])).lower() + " " + str(g.get("reason", "")).lower()
        return any(sig in qall for sig in _REJECT)

    # 期望升级 TopN (#50: 与 run 同刀法, 独立重算): S/A 按 (-count, term_en) 排, 最大断层切分, 不断层多收, 保底 Top1
    _sa_exp = sorted([r for r in ratings if r.get("rating") in ("S", "A")],
                     key=lambda x: (-int(x.get("count", 0)), str(x.get("term_en", ""))))
    _ucounts_exp = [int(r.get("count", 0)) for r in _sa_exp]
    if len(_sa_exp) <= 1:
        _expect_up = [r.get("term_en") for r in _sa_exp]
    elif not _sa_exp:
        _expect_up = []
    else:
        _ugaps = [_ucounts_exp[i] - _ucounts_exp[i + 1] for i in range(len(_ucounts_exp) - 1)]
        _umx = max(_ugaps)
        if _umx == 0:
            _expect_up = [r.get("term_en") for r in _sa_exp]
        else:
            _ucut = next(i for i, gp in enumerate(_ugaps) if gp == _umx)
            _expect_up = [r.get("term_en") for r in _sa_exp[:_ucut + 1]]
    if isinstance(ups, list) and ups and _expect_up:
        _got_up = [u.get("name") for u in ups if isinstance(u, dict)]
        if _got_up != _expect_up:
            fail(f"priorities upgrades 须为断层 TopN (期望 {_expect_up}, 实得 {_got_up})", errors)
    # 期望商店 TopN (与 run 同刀法, 独立重算): must_take verified 按 (-count, name) 排, 去拒绝, 最大断层切分
    _cands_exp = sorted(list(mt_verified.values()), key=lambda x: (-int(x.get("count", 0)), str(x.get("name_en", ""))))
    _filt_exp = [g for g in _cands_exp if not _has_refusal(g)]
    _counts_exp = [int(g.get("count", 0)) for g in _filt_exp]
    if len(_filt_exp) == 1:
        _expect_names = [_filt_exp[0].get("name_en")]
    elif not _filt_exp:
        _expect_names = []
    else:
        _gaps = [_counts_exp[i] - _counts_exp[i + 1] for i in range(len(_counts_exp) - 1)]
        _mx = max(_gaps)
        if _mx == 0:
            _expect_names = [g.get("name_en") for g in _filt_exp]
        else:
            _cut = next(i for i, gp in enumerate(_gaps) if gp == _mx)
            _expect_names = [g.get("name_en") for g in _filt_exp[:_cut + 1]]
    if isinstance(shs, list) and shs and _expect_names:
        _got_names = [s.get("name") for s in shs if isinstance(s, dict)]
        if _got_names != _expect_names:
            fail(f"priorities shop 须为断层 TopN (期望 {_expect_names}, 实得 {_got_names})", errors)
    for u in (ups if isinstance(ups, list) else []):
        for k in ("name", "kind", "why", "how_to_get", "quotes"):
            if k not in u or (isinstance(u[k], str) and not u[k].strip()):
                fail(f"priorities upgrades missing {k}: {u.get('name')}", errors)
        if u.get("kind") != "upgrade":
            fail(f"priorities upgrades kind must be upgrade: {u.get('name')}", errors)
        if u.get("name") not in sa_names:
            fail(f"priorities upgrades must be in ratings S/A: {u.get('name')}", errors)
        if len(str(u.get("why", ""))) < 8 or len(str(u.get("how_to_get", ""))) < 8:
            fail(f"priorities upgrades why/how_to_get too short: {u.get('name')}", errors)
        _check_quotes(f"priorities upgrade {u.get('name')}", u.get("quotes", []), u.get("quote_details", []))
    for s in (shs if isinstance(shs, list) else []):
        for k in ("name", "kind", "why", "how_to_get", "quotes"):
            if k not in s or (isinstance(s[k], str) and not s[k].strip()):
                fail(f"priorities shop missing {k}: {s.get('name')}", errors)
        if s.get("kind") != "shop":
            fail(f"priorities shop kind must be shop: {s.get('name')}", errors)
        if s.get("name") not in mt_names:
            fail(f"priorities shop must be in grouping must_take: {s.get('name')}", errors)
        if s.get("name") not in mt_verified:
            fail(f"priorities shop must be verified (拿取锚绿): {s.get('name')}", errors)
        else:
            _ge = mt_verified.get(s.get("name"))
            if _ge is not None and _has_refusal(_ge):
                fail(f"priorities shop 有拒绝动词应顺延 (通用顺延未执行): {s.get('name')}", errors)
        if len(str(s.get("why", ""))) < 8 or len(str(s.get("how_to_get", ""))) < 8:
            fail(f"priorities shop why/how_to_get too short: {s.get('name')}", errors)
        _check_quotes(f"priorities shop {s.get('name')}", s.get("quotes", []), s.get("quote_details", []))
    if priorities != priorities_out:
        fail("outputs/priorities.json must equal steps/07-priorities/priorities.json", errors)

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
