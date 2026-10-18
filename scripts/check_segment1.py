#!/usr/bin/env python3
"""Machine check for B-段1 (#40): 01-03 新 schema + 04-attributes + 05-weapons.

沿试点 check_pilot.py (schema + 全收录 + 低频一句话 + sha), 加:
- 01 新 schema: {id,text[,start,end]} (B-04 起统一加, ?t= 跳链用)
- 02/03 新字段: start/end/context 只读 (不进机检锚点, 但须存在)
- 03 quotes 去重 (count 口径不动)
- 04: 39 全量 (主 17 + 次级 22), 提过即算口径 (count>0 必 S-D, count==0 必 -)
- 05: T1+T2 == registry-slice 子集, T1>=1, 把数/波次数字在 note (不机检数字, 只查非空)

Usage:
  python scripts/check_segment1.py --slug cyborg --variant ultimate
  python scripts/check_segment1.py --slug cyborg --variant ultimate --work-root G:/brotato-work
"""

from __future__ import annotations

import argparse
import hashlib
import json
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
        work / "inputs" / "registry-slice.json",
        work / "inputs" / "manifest.json",
        work / "steps" / "01-sentences" / "sentences.json",
        work / "steps" / "02-verbs" / "verbs.json",
        work / "steps" / "03-grouping" / "grouping.json",
        work / "outputs" / "groups.json",
        work / "steps" / "04-attributes" / "ratings.json",
        work / "outputs" / "ratings.json",
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

    # --- 02-verbs (+start/end/context 只读) ---
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

    # --- 03-grouping (沿 pilot + quote_details + 去重) ---
    if isinstance(grouping, list):
        grouped_names = {g.get("name_en") for g in grouping if isinstance(g, dict)}
        try:
            reg_slice = json.loads((work / "inputs" / "registry-slice.json").read_text(encoding="utf-8"))
            item_set = set(reg_slice.get("items", []))
        except Exception:
            item_set = grouped_names
        for r in verified:
            if r.get("object_norm") in item_set and r.get("object_norm") not in grouped_names:
                fail(f"verified not grouped: {r.get('object_norm')}", errors)
        if len(grouping) != 68:
            fail(f"grouping must be 68 (count>0 全收录), got {len(grouping)}", errors)
        for g in grouping:
            for k in ("name_en", "count", "group", "confidence", "reason", "quotes"):
                if k not in g:
                    fail(f"grouping missing {k}: {g.get('name_en')}", errors)
            if g.get("group") not in ("must_take", "mentioned_not_taken", "ban", "casual_mention"):
                fail(f"bad group: {g.get('name_en')}={g.get('group')}", errors)
            if g.get("group") == "must_take" and g.get("tier") not in ("core", "convenient", "compromise"):
                fail(f"must_take must have tier: {g.get('name_en')}", errors)
            if isinstance(g.get("count"), int) and g["count"] <= 3:
                if len(str(g.get("reason", "")).strip()) < 8:
                    fail(f"low-freq must have one-liner: {g.get('name_en')}", errors)
            rs = str(g.get("reason", ""))
            if "字幕" in rs and "次" in rs and "原话" not in rs:
                warns.append(f"WARN: reason 疑计数泄漏: {g.get('name_en')}")
            if g.get("group") == "ban":
                qall = " ".join(g.get("quotes", [])).lower()
                if not any(w in qall for w in ("ban", "avoid", "recycl", "sell", "skip", "ignor")):
                    if "ban" not in rs.lower() and "避开" not in rs:
                        fail(f"ban must have rejection verb quote: {g.get('name_en')}", errors)
            # quotes 去重
            qs = g.get("quotes", [])
            if isinstance(qs, list) and len(qs) != len(set(qs)):
                fail(f"quotes must be deduped (展示去重): {g.get('name_en')}", errors)
            # quote_details 只读
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
        # outputs/groups.json 为旧 pilot 格式 (无 quote_details) 时允许? 不, 段1要求一致
        # 兼容: 若 outputs 缺 quote_details, 视为未刷新, fail 提示重跑
        fail("outputs/groups.json must equal steps/03-grouping/grouping.json (重跑 01-03 新 schema 后须一致)", errors)

    # --- 04-attributes ---
    if not isinstance(ratings, list) or len(ratings) != 39:
        fail(f"ratings must be 39 (主17+次级22全量), got {len(ratings) if isinstance(ratings, list) else type(ratings)}", errors)
    else:
        import csv as _csv
        terms = list(_csv.DictReader((REPO / "data" / "terms.csv").open(encoding="utf-8")))
        expect = [(t["en"].strip(), t.get("type", "")) for t in terms]
        got = [(r.get("term_en"), r.get("type")) for r in ratings]
        if set(x[0] for x in got) != set(x[0] for x in expect):
            fail("ratings must cover all 39 terms (主17+次级22)", errors)
        for r in ratings:
            for k in ("term_en", "type", "count", "rating", "reason", "quotes"):
                if k not in r:
                    fail(f"ratings missing {k}: {r.get('term_en')}", errors)
            cnt = r.get("count")
            rt = r.get("rating")
            if isinstance(cnt, int) and cnt > 0:
                if rt not in ("S", "A", "B", "C", "D"):
                    fail(f"count>0 must have S-D rating: {r.get('term_en')}={rt}", errors)
                if not r.get("quotes"):
                    fail(f"count>0 must have quotes: {r.get('term_en')}", errors)
                if len(str(r.get("reason", "")).strip()) < 8:
                    fail(f"ratings reason too short: {r.get('term_en')}", errors)
            elif cnt == 0:
                if rt != "-":
                    fail(f"count==0 must be '-': {r.get('term_en')}={rt}", errors)
                if r.get("quotes"):
                    fail(f"count==0 must have empty quotes: {r.get('term_en')}", errors)
            rs = str(r.get("reason", ""))
            if "字幕" in rs and "次" in rs and "原话" not in rs:
                warns.append(f"WARN: ratings 疑计数泄漏: {r.get('term_en')}")
            qs = r.get("quotes", [])
            if isinstance(qs, list) and len(qs) != len(set(qs)):
                fail(f"ratings quotes must be deduped: {r.get('term_en')}", errors)
            qd = r.get("quote_details", [])
            if not isinstance(qd, list) or len(qd) != len(qs):
                fail(f"ratings quote_details must parallel quotes: {r.get('term_en')}", errors)
    if ratings != ratings_out:
        fail("outputs/ratings.json must equal steps/04-attributes/ratings.json", errors)

    # --- 05-weapons ---
    if not isinstance(weapons, dict) or "t1" not in weapons or "t2" not in weapons:
        fail("weapons must be {t1[], t2[]}", errors)
        t1, t2 = [], []
    else:
        t1, t2 = weapons["t1"], weapons["t2"]
    try:
        reg_slice = json.loads((work / "inputs" / "registry-slice.json").read_text(encoding="utf-8"))
        wset = set(reg_slice.get("weapons", []))
    except Exception:
        wset = set()
    got_w = {w.get("name_en") for w in (t1 + t2) if isinstance(w, dict)}
    if wset and got_w != wset:
        fail(f"weapons t1+t2 must equal registry-slice weapons {sorted(wset)}, got {sorted(got_w)}", errors)
    if len(t1) < 1:
        fail("weapons T1>=1 (验收线)", errors)
    for w in (t1 + t2):
        for k in ("name_en", "count", "tier", "note", "quotes"):
            if k not in w:
                fail(f"weapons missing {k}: {w.get('name_en')}", errors)
        if not w.get("note") or len(str(w.get("note")).strip()) < 8:
            fail(f"weapons note too short (把数/波次不丢): {w.get('name_en')}", errors)
        if not w.get("quotes"):
            fail(f"weapons must have quotes: {w.get('name_en')}", errors)
        qs = w.get("quotes", [])
        if isinstance(qs, list) and len(qs) != len(set(qs)):
            fail(f"weapons quotes must be deduped: {w.get('name_en')}", errors)
        qd = w.get("quote_details", [])
        if not isinstance(qd, list) or len(qd) != len(qs):
            fail(f"weapons quote_details must parallel quotes: {w.get('name_en')}", errors)
        rs = str(w.get("note", ""))
        if "字幕" in rs and "次" in rs and "原话" not in rs:
            warns.append(f"WARN: weapons 疑计数泄漏: {w.get('name_en')}")
    if weapons != weapons_out:
        fail("outputs/weapons.json must equal steps/05-weapons/weapons.json", errors)

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
    # 默认工作区 (picker 从 G:\brotato-work/上次目录开始: 固定 id + IndexedDB 存句柄)
    for marker in ("startIn", "brotato-work-root"):
        if marker not in audit_html:
            fail(f"audit.html 缺默认工作区 (#42跟进): {marker}", errors)
    # ratings/weapons mock 常设 (离线可读, live 经 picker/?base= 全量)
    for marker in ("MOCK_RATINGS", "MOCK_WEAPONS"):
        if marker not in audit_html:
            fail(f"audit.html 缺 mock 常设: {marker}", errors)
    # 禁静默回 mock: 启动不许自动载 mock (麦当劳不给广告纸); live 失败必须亮红灯不回落
    import re as _re2
    _m = _re2.search(r"window\.addEventListener\('DOMContentLoaded'.*?", audit_html, _re2.DOTALL)
    # 粗查: DOMContentLoaded 块内不许出现 loadMockData()
    _dom = audit_html[audit_html.find("window.addEventListener('DOMContentLoaded'"):audit_html.find("window.addEventListener('DOMContentLoaded'")+2000]
    if "loadMockData()" in _dom:
        fail("audit.html 禁静默回 mock: DOMContentLoaded 不许自动 loadMockData()", errors)
    for marker in ("不回落 mock", "不可作为验收依据"):
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
