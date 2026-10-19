#!/usr/bin/env python3
"""B-段2实施 (#41): 06-phases + 07-priorities + 08-pitfalls + 09-assemble, cyborg/ultimate 单变体.

沿 #39 决议 (B 全链展开 Q6/Q8):
- DAG: 01 -> {02->03,04,05,06,08} 并行 -> 07 -> 09. 06/08 可与段1并行先跑, 07 须段1绿后才开.
- 载体延续三件套 (prompts/step0X + steps/0X-*/ + check + audit 动态读).
- 旧 SOP 只作参考, 不作输入; 旧链冻结 (禁读 data/mentions + data/builds).
- 确定性执行 (沿 run_segment1.py 模式, 子 agent RPC 为 --rpc 模式):
  python scripts/run_segment2.py --slug cyborg --variant ultimate
  python scripts/run_segment2.py --slug cyborg --variant ultimate --rpc

输入 (cwd 锁定 G:/brotato-work/<slug>/<variant>/):
  steps/01-sentences/sentences.json + inputs/meta.json (chapters 备查)
  steps/03-grouping/grouping.json + steps/04-attributes/ratings.json + steps/05-weapons/weapons.json (07 聚合)
  inputs/manifest.json (09 sha 锚点)
全局 (repo 侧只读, 非 runtime): 无新增 (不读 terms/wiki-cache, 只读 inputs + steps 现场数据).
输出:
  steps/06-phases/phases.json (+ outputs/phases.json)
  steps/07-priorities/priorities.json (+ outputs/priorities.json)
  steps/08-pitfalls/pitfalls.json (+ outputs/pitfalls.json)
  steps/09-assemble/guide.json (= outputs/guide.json, 六节聚合 + sha 对上)
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

REPO = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(REPO / "scripts"))

from run_segment1 import build_context as _build_context  # noqa: E402


def _load(workdir: Path, rel: str):
    p = workdir / rel
    if not p.exists():
        raise SystemExit(f"missing {rel} for segment2: 先跑 run_segment1 (段1绿后才开 07/09)")
    return json.loads(p.read_text(encoding="utf-8"))


def _quote_lookup(sentences: list[dict]):
    mp: dict[str, list[dict]] = {}
    for i, s in enumerate(sentences):
        mp.setdefault(s["text"], []).append({
            "start": s.get("start"), "end": s.get("end"),
            "t": int(s["start_s"]) if s.get("start_s") is not None else None,
            "context": _build_context(sentences, i),
        })
    return mp


def _collect(sentences: list[dict], keywords: list[str],
              id_min: int | None = None, id_max: int | None = None) -> tuple[list[str], list[dict]]:
    """现场扫: 任一关键词 substring (case-insensitive) 命中即收, 保序去重, 全量 (去cap #42跟进).

    id 窗 (可选): 视频按波次顺序讲解, W1-5 偏前段 / W6-12 偏中段 / W13-20 偏后段.
    窗只做去重前的预筛, 不改关键词口径, 不编数字.
    """
    seen: list[str] = []
    for s in sentences:
        if id_min is not None and s["id"] < id_min:
            continue
        if id_max is not None and s["id"] > id_max:
            continue
        low = s["text"].lower()
        if "glass cannon" in low:
            continue
        if any(k.lower() in low for k in keywords):
            if s["text"] not in seen:
                seen.append(s["text"])
    qlookup = _quote_lookup(sentences)
    details = []
    for q in seen:
        hits = qlookup.get(q, [])
        h = hits[0] if hits else {"start": None, "end": None, "t": None, "context": q[:300]}
        details.append({"quote": q, "start": h["start"], "end": h["end"], "t": h["t"], "context": h["context"]})
    return seen, details


def _short(q: str, n: int = 60) -> str:
    return q[:n]


def _load_chapters(workdir: Path) -> list[dict]:
    """#45: 作者 8 chapters timed ([{title,start,end}], 秒, yt-dlp 原值).

    老格式纯字符串数组视为缺取证 fail loud, 指引重跑 Step00 回填."""
    meta = _load(workdir, "inputs/meta.json")
    chs = meta.get("chapters")
    if (not isinstance(chs, list) or not chs
            or any(not isinstance(c, dict) for c in chs)
            or any(not isinstance((c or {}).get("title"), str)
                    or not isinstance((c or {}).get("start"), (int, float))
                    or not isinstance((c or {}).get("end"), (int, float))
                    for c in chs)):
        raise SystemExit(
            "step06 chapters 非 timed 格式 ([{title,start,end}]): 老格式纯字符串数组视为缺取证, "
            "先跑 scripts/fetch_inputs.py --url <youtube-url> --slug <slug> --variant <variant> 回填 "
            "(source.vtt 不动, sha 不变)")
    return chs


def _bucket_by_chapter(sentences: list[dict], chapters: list[dict],
                       cap: int | None = None) -> list[tuple[list[str], list[dict]]]:
    """#45+C: 按 chapter 时间窗确定性分桶 (sentence.start_s 落窗即收, 保序去重, 不cap全量).

    窗口左闭右开 [start, end), 末章含 end (ss>=start). 空窗诚实空出 (quotes==[])."""
    for s in sentences:
        if s.get("start_s") is None:
            raise SystemExit("step06 sentences 缺 start_s (需重跑 01 取整句时间戳): 现场时间窗分桶无依据")
    qlookup = _quote_lookup(sentences)
    out: list[tuple[list[str], list[dict]]] = []
    for i, ch in enumerate(chapters):
        s = float(ch["start"])
        e = float(ch["end"])
        is_last = (i == len(chapters) - 1)
        seen: list[str] = []
        for sent in sentences:
            ss = float(sent["start_s"])
            hit = (ss >= s and ss <= e) if is_last else (ss >= s and ss < e)
            if hit and sent["text"] not in seen:
                seen.append(sent["text"])
                if cap is not None and len(seen) >= cap:
                    break
        details = []
        for q in seen:
            hits = qlookup.get(q, [])
            h = hits[0] if hits else {"start": None, "end": None, "t": None, "context": q[:300]}
            details.append({"quote": q, "start": h["start"], "end": h["end"],
                            "t": h["t"], "context": h["context"]})
        out.append((seen, details))
    return out


def step06_buckets(workdir: Path, sentences: list[dict]) -> tuple[list[dict], list[tuple[list[str], list[dict]]]]:
    """#45跟进: 确定性分桶 (代码, 无 judgment). 写 buckets.json 供 agent 输入. N=章节数 (cyborg=8, 他例按实际)."""
    chapters = _load_chapters(workdir)
    buckets = _bucket_by_chapter(sentences, chapters, cap=None)
    outdir = workdir / "steps" / "06-phases"
    outdir.mkdir(parents=True, exist_ok=True)
    dump = [{"phase": str(ch["title"]), "waves": f"{ch['start']}-{ch['end']}s",
             "quotes": qs, "quote_details": qd}
            for ch, (qs, qd) in zip(chapters, buckets)]
    (outdir / "buckets.json").write_text(json.dumps(dump, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    return chapters, buckets


def _load_wordings(workdir: Path, chapters: list[dict]) -> list[dict]:
    """#45跟进: agent judgment (人话三问). 缺件即 fail, 指引跑 prompts/step06-phases.md."""
    p = workdir / "steps" / "06-phases" / "wordings.json"
    if not p.exists():
        raise SystemExit(
            "step06 缺 wordings.json (agent 三问未写): 按 prompts/step06-phases.md "
            "读 steps/06-phases/buckets.json 写 wordings.json (只写 goal/focus/pivot, 不改 quotes)")
    try:
        w = json.loads(p.read_text(encoding="utf-8"))
    except Exception as e:
        raise SystemExit(f"step06 wordings.json 解析失败: {e}")
    if not isinstance(w, list) or len(w) != len(chapters):
        raise SystemExit(f"step06 wordings 须 N={len(chapters)} (一章一段), got {len(w) if isinstance(w, list) else type(w)}")
    for i, (ch, entry) in enumerate(zip(chapters, w)):
        if not isinstance(entry, dict) or entry.get("phase") != str(ch["title"]):
            raise SystemExit(f"step06 wordings[{i}] phase 须=章标题原文 {str(ch['title'])!r}")
        for k in ("goal", "focus", "pivot"):
            v = entry.get(k)
            if not isinstance(v, str) or len(v.strip()) < 8:
                raise SystemExit(f"step06 wordings {entry.get('phase')} 缺 {k} (人话一句≥8字)")
        ex = entry.get("extra_quotes", [])
        if ex is None:
            ex = []
        if not isinstance(ex, list) or any(not isinstance(q, str) for q in ex):
            raise SystemExit(f"step06 wordings {entry.get('phase')} extra_quotes须字符串数组 (窗外补引用, 无则[])")
    return w


def step06_merge(workdir: Path, chapters: list[dict],
                 buckets: list[tuple[list[str], list[dict]]],
                 wordings: list[dict], sentences: list[dict]) -> list[dict]:
    """#45跟进+C: 确定性合并 (代码, 无 judgment). buckets(窗内) + wordings(三问+extra≤2) → phases.json. N=章节数."""
    phases: list[dict] = []
    for i, ch in enumerate(chapters):
        title = str(ch["title"])
        waves = f"{ch['start']}-{ch['end']}s"
        qs, qd = buckets[i]
        if not qs:
            phases.append({
                "phase": title, "waves": waves,
                "goal": f"本章（{title}）为非打法章，作者未给可执行打法，仅作背景/回顾，不硬凑（类比 ratings `-`）。",
                "focus": "本章无配装/走位要点，不脑补。",
                "pivot": "无转向点，不编数字。",
                "quotes": [], "quote_details": [],
            })
            continue
        entry = wordings[i]
        extra: list[str] = list(entry.get("extra_quotes") or [])
        by_text = {s["text"]: s for s in sentences if isinstance(s, dict)}
        qlookup = _quote_lookup(sentences)
        ex_details: list[dict] = []
        for q in extra:
            if q in qs:
                raise SystemExit(f"step06 {title} extra_quotes 与窗内重复: {q[:40]}")
            hit = by_text.get(q)
            if hit is None:
                raise SystemExit(f"step06 {title} extra_quotes 须逐字等于 sentences: {q[:40]}")
            ss = float(hit.get("start_s", -1))
            s0, e0 = float(ch["start"]), float(ch["end"])
            is_last = (i == len(chapters) - 1)
            inside = (ss >= s0 and ss <= e0) if is_last else (ss >= s0 and ss < e0)
            if inside:
                raise SystemExit(f"step06 {title} extra_quotes 须在窗外 (窗内已收): {q[:40]}")
            h = (qlookup.get(q) or [None])[0] or {"start": None, "end": None, "t": None, "context": q[:300]}
            ex_details.append({"quote": q, "start": h["start"], "end": h["end"],
                               "t": h["t"], "context": h["context"], "out_of_window": True})
        phases.append({
            "phase": title, "waves": waves,
            "goal": str(entry["goal"]).strip(),
            "focus": str(entry["focus"]).strip(),
            "pivot": str(entry["pivot"]).strip(),
            "quotes": list(qs) + list(extra), "quote_details": list(qd) + ex_details,
        })
    outdir = workdir / "steps" / "06-phases"
    outdir.mkdir(parents=True, exist_ok=True)
    (outdir / "phases.json").write_text(json.dumps(phases, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    (workdir / "outputs").mkdir(parents=True, exist_ok=True)
    (workdir / "outputs" / "phases.json").write_text(json.dumps(phases, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    return phases


def step06(workdir: Path, sentences: list[dict]) -> list[dict]:
    # #45跟进+C: 分桶(代码) + 三问+extra≤2(agent) + 合并(代码). 窗内quotes不可改, N=章节数.
    chapters, buckets = step06_buckets(workdir, sentences)
    wordings = _load_wordings(workdir, chapters)
    return step06_merge(workdir, chapters, buckets, wordings, sentences)


def step07(workdir: Path, sentences: list[dict], ratings: list[dict],
           grouping: list[dict], phases: list[dict]) -> dict:
    # #45: 跳过空段 (overview/review 诚实空出不进节奏引用, how_to_get 可引章节奏)
    if not isinstance(phases, list) or not phases:
        raise SystemExit("step07 缺 phases (06 未跑): 先跑 step06 作者章节分桶")
    live_phases = [p for p in phases if isinstance(p, dict) and p.get("quotes")]
    # live_phases 仅用于节奏引用 (空段跳过); Top3 口径仍只认 04/03, 不自创不重评
    _ = live_phases
    # 升级 Top3: 只认 04 输出 S/A + count 降序 (不自创, 不重评)
    sa = [r for r in ratings if r.get("rating") in ("S", "A")]
    sa = sorted(sa, key=lambda x: -int(x.get("count", 0)))
    if len(sa) < 3:
        raise SystemExit(f"step07 升级候选不足 S/A={len(sa)}: 段1 ratings 疑异常")
    top_up = sa[:3]
    # 商店 Top3: 只认 03 输出 must_take + verified + count 降序; Peacock 有拒绝原话诚实顺延
    cands = [g for g in grouping if g.get("group") == "must_take" and g.get("confidence") == "verified"]
    cands = sorted(cands, key=lambda x: -int(x.get("count", 0)))
    shop: list[dict] = []
    for g in cands:
        qall = " ".join(g.get("quotes", [])).lower() + " " + str(g.get("reason", "")).lower()
        # 诚实跳过: 本波明确不拿 (not taking) 属波次 modifier, 非商店优先级
        if g.get("name_en") == "Peacock" and ("not taking" in qall or "not take" in qall):
            continue
        shop.append(g)
        if len(shop) >= 3:
            break
    if len(shop) < 3:
        raise SystemExit(f"step07 商店候选不足 must_take verified={len(shop)}: 段1 grouping 疑异常")
    qlookup = _quote_lookup(sentences)

    def _how(name: str, fallback_q: str) -> tuple[str, list[str], list[dict]]:
        # 怎么拿: 找含本名 + buy/lock/roll/upgrade/shop 任一的现场句, 原话数字不丢; 未提空出用 fallback
        lname = name.lower()
        best = None
        for s in sentences:
            low = s["text"].lower()
            if lname in low or lname.rstrip("s") in low:
                if any(k in low for k in ("buy", "lock", "roll", "upgrade", "shop", "take", "pick up", "get")):
                    best = s
                    break
        if best is None:
            for s in sentences:
                if lname in s["text"].lower() or lname.rstrip("s") in s["text"].lower():
                    best = s
                    break
        q = best["text"] if best else fallback_q
        hits = qlookup.get(q, [])
        h = hits[0] if hits else {"start": None, "end": None, "t": None, "context": q[:300]}
        return q, [q], [{"quote": q, "start": h["start"], "end": h["end"], "t": h["t"], "context": h["context"]}]

    upgrades = []
    for r in top_up:
        base_q = (r.get("quotes") or [""])[0] or r.get("term_en", "")
        q, qs, qd = _how(r["term_en"], base_q)
        upgrades.append({
            "name": r["term_en"], "kind": "upgrade",
            "why": f"{r.get('reason', '')}",
            "how_to_get": f"拿法看商店/升级节奏;原话[{_short(q)}]",
            "quotes": qs, "quote_details": qd,
        })
    shops = []
    for g in shop:
        base_q = (g.get("quotes") or [""])[0] or g.get("name_en", "")
        q, qs, qd = _how(g["name_en"], base_q)
        shops.append({
            "name": g["name_en"], "kind": "shop",
            "why": f"{g.get('reason', '')}",
            "how_to_get": f"拿法看商店/升级节奏,roll到即锁;原话[{_short(q)}]",
            "quotes": qs, "quote_details": qd,
        })
    priorities = {"upgrades": upgrades, "shop": shops}
    outdir = workdir / "steps" / "07-priorities"
    outdir.mkdir(parents=True, exist_ok=True)
    (outdir / "priorities.json").write_text(json.dumps(priorities, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    (workdir / "outputs").mkdir(parents=True, exist_ok=True)
    (workdir / "outputs" / "priorities.json").write_text(json.dumps(priorities, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    return priorities


# #46: 08换筐(事件锚定N不定, 沿grilling Q1=A): 筐由作者亲口警告定, 有锚才有条.
# 闭集9锚逐字原话, 机检只认这个; cyborg现货5组全留; glass cannon系take排除.
CLOSED_PIT_ANCHORS = [
    "mistake",
    "dying",
    "do not want",
    "avoid",
    "too dangerous",
    "knock back",
    "materials",
    "transition-swap",
    "peacock-spawn",
]

# 复合锚展开为逐字短语(机检验逐字包含, 大小写不敏感;
# transition-swap = transition OR swap, peacock-spawn = peacock OR spawn)
PIT_ANCHOR_PHRASES: dict[str, list[str]] = {
    "mistake": ["mistake"],
    "dying": ["dying"],
    "do not want": ["do not want"],
    "avoid": ["avoid"],
    "too dangerous": ["too dangerous"],
    "knock back": ["knock back"],
    "materials": ["materials"],
    "transition-swap": ["transition", "swap"],
    "peacock-spawn": ["peacock", "spawn"],
}


def _anchor_phrases(keys: list[str]) -> list[str]:
    out: list[str] = []
    for k in keys:
        out.extend(PIT_ANCHOR_PHRASES.get(k, [k]))
    return out


def _has_closed_anchor(text: str) -> bool:
    low = text.lower()
    for plist in PIT_ANCHOR_PHRASES.values():
        if any(p.lower() in low for p in plist):
            return True
    return False


def _collect_anchors(sentences: list[dict], anchor_keys: list[str]) -> tuple[list[str], list[dict]]:
    """闭集锚收集: 任一锚短语逐字命中即收(glass cannon已在_collect内排除)."""
    return _collect(sentences, _anchor_phrases(anchor_keys))


def _collect_anchor_hits(sentences: list[dict], anchor_keys: list[str]) -> list[dict]:
    """事件锚触发实况: 逐句扫锚短语, 保序去重, 每hit带sentence_id(审计跳原文句)."""
    phrases = _anchor_phrases(anchor_keys)
    hits: list[dict] = []
    seen: list[str] = []
    for s in sentences:
        low = s["text"].lower()
        if any(p.lower() in low for p in phrases):
            if s["text"] not in seen:
                seen.append(s["text"])
                hits.append({
                    "sentence_id": s["id"],
                    "quote": s["text"],
                    "start": s.get("start"), "end": s.get("end"),
                    "t": int(s["start_s"]) if s.get("start_s") is not None else None,
                })
    return hits


def _collect_discretion(sentences: list[dict], keywords: list[str]) -> tuple[list[str], list[dict]]:
    """裁量收集: 关键词命中 + 排除闭集锚(保证黄vs绿可分) + 排除glass cannon, 全量去重."""
    seen: list[str] = []
    for s in sentences:
        low = s["text"].lower()
        if "glass cannon" in low:
            continue
        if _has_closed_anchor(s["text"]):
            continue
        if any(k.lower() in low for k in keywords):
            if s["text"] not in seen:
                seen.append(s["text"])
    qlookup = _quote_lookup(sentences)
    details = []
    for q in seen:
        hits = qlookup.get(q, [])
        h = hits[0] if hits else {"start": None, "end": None, "t": None, "context": q[:300]}
        details.append({"quote": q, "start": h["start"], "end": h["end"], "t": h["t"], "context": h["context"]})
    return seen, details


def step08(workdir: Path, sentences: list[dict]) -> list[dict]:
    # 5锚定组(覆盖全部9闭集锚, cyborg现货全留) + 2裁量(不限条, 黄永不进绿)
    anchored_specs = [
        ("半波转换踩空", "fatal", ["transition-swap"],
         "前半波没打完elite/boss, 转换后变近战刮痧",
         "看顶栏halfway, 前半波集火elite, engineering half靠螺丝刀+结构补"),
        ("材料落地不捡", "risky", ["materials"],
         "中期材料落地不捡, 经济崩盘",
         "材料顺路捡, 不跨波囤, 中期必清地"),
        ("失误丢击退", "risky", ["mistake", "knock back"],
         "走位撞投射物出生点失误 + 击退丢了难处理",
         "开局记出生点, 不贴左墙; 丢击退后靠走位拉扯"),
        ("刷怪站位失控", "trap", ["peacock-spawn", "do not want"],
         "Peacock波+30%伤 + 刷怪失控 + 站位撞刷怪点",
         "horde波提前合核弹清场, peacock波控刷怪数, 开局远离刷怪点"),
        ("高难警告别硬顶", "risky", ["dying", "avoid", "too dangerous"],
         "经济没成型硬顶会死 + 非武器伤别碰 + 危险波次别硬拿",
         "经济先保命再贪收入; 非武器伤直接避开; horde波不拿scarf锁企鹅过波"),
    ]
    discretion_specs = [
        ("尸潮核弹清场", "risky", ["horde", "nuke"],
         "horde波没核弹清不动, 拖到尸潮堆起来会崩",
         "horde波前合核弹(nuke launcher), 留咖啡/穿透打清场",
         "裁量: horde波靠核弹清场是判断(无闭集锚, 标黄待人点)"),
        ("精英集火补伤", "risky", ["elite", "boss"],
         "精英/boss不集火压不住, 后半变刮痧",
         "前半远程补第二把枪, 精英优先点掉, 留伤进boss波",
         "裁量: 精英/boss集火是判断(无闭集锚, 标黄待人点)"),
    ]
    pitfalls: list[dict] = []
    for title, sev, akeys, why_tail, avoid in anchored_specs:
        for k in akeys:
            if k not in CLOSED_PIT_ANCHORS:
                raise SystemExit(f"step08 anchor非闭集: {k}")
        qs, qd = _collect_anchors(sentences, akeys)
        if not qs:
            raise SystemExit(f"step08现场扫不足 {title}: anchors={akeys}")
        pitfalls.append({
            "title": title, "severity": sev, "kind": "anchor",
            "anchor": akeys[0], "anchors": akeys,
            "why": f"{why_tail}；原话“{_short(qs[0])}…”",
            "how_to_avoid": f"{avoid}；原话“{_short(qs[1] if len(qs) > 1 else qs[0])}…”",
            "quotes": qs, "quote_details": qd,
        })
    for title, sev, keys, why_tail, avoid, reason in discretion_specs:
        qs, qd = _collect_discretion(sentences, keys)
        if not qs:
            raise SystemExit(f"step08裁量扫不足 {title}: keywords={keys}")
        pitfalls.append({
            "title": title, "severity": sev, "kind": "discretion",
            "anchor": None, "anchors": [],
            "why": f"{why_tail}；原话“{_short(qs[0])}…”",
            "how_to_avoid": f"{avoid}；原话“{_short(qs[1] if len(qs) > 1 else qs[0])}…”",
            "quotes": qs, "quote_details": qd,
            "quote": qs[0], "reason": reason, "inferred": True,
        })
    outdir = workdir / "steps" / "08-pitfalls"
    outdir.mkdir(parents=True, exist_ok=True)
    (outdir / "pitfalls.json").write_text(json.dumps(pitfalls, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    (workdir / "outputs").mkdir(parents=True, exist_ok=True)
    (workdir / "outputs" / "pitfalls.json").write_text(json.dumps(pitfalls, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    # 事件锚触发实况落盘 (#42跟进): 闭集9锚全列(0触发也列, 覆盖率可见), 审计面板直读
    anchors = []
    for ak in CLOSED_PIT_ANCHORS:
        hits = _collect_anchor_hits(sentences, [ak])
        anchors.append({"anchor": ak, "phrases": PIT_ANCHOR_PHRASES[ak], "hits": hits, "count": len(hits)})
    (outdir / "anchors.json").write_text(json.dumps(anchors, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    (workdir / "outputs" / "anchors.json").write_text(json.dumps(anchors, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    return pitfalls


def step09(workdir: Path, grouping, ratings, weapons, phases, priorities, pitfalls) -> dict:
    manifest = _load(workdir, "inputs/manifest.json")
    meta = _load(workdir, "inputs/meta.json")
    sha = (manifest.get("sources") or [{}])[0].get("sha1", "")
    if not sha:
        raise SystemExit("step09 manifest 缺 sha1: 取证未完成")
    url = (manifest.get("sources") or [{}])[0].get("url", "")
    guide = {
        "slug": manifest.get("slug", ""),
        "variant": manifest.get("variant", ""),
        "covers": manifest.get("covers", []),
        "sha": sha,
        "url": url,
        "title": meta.get("title", ""),
        "groups": grouping,
        "ratings": ratings,
        "weapons": weapons,
        "phases": phases,
        "priorities": priorities,
        "pitfalls": pitfalls,
    }
    outdir = workdir / "steps" / "09-assemble"
    outdir.mkdir(parents=True, exist_ok=True)
    (outdir / "guide.json").write_text(json.dumps(guide, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    (workdir / "outputs").mkdir(parents=True, exist_ok=True)
    (workdir / "outputs" / "guide.json").write_text(json.dumps(guide, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    return guide


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description="B-段2实施 (#41)")
    ap.add_argument("--slug", default="cyborg")
    ap.add_argument("--variant", default="ultimate")
    ap.add_argument("--work-root", default="G:/brotato-work")
    ap.add_argument("--rpc", action="store_true", help="只打印 RPC 子进程命令, 不执行")
    args = ap.parse_args(argv)
    slug, vid = args.slug, args.variant
    workdir = Path(args.work_root) / slug / vid

    if args.rpc:
        print(f'cd "{workdir}" && "F:/Pi/CLI/pi.cmd" --mode rpc --no-session '
              f"--no-skills --no-extensions --no-context-files --tools read,bash,write --thinking off")
        print("子 prompt 见 prompts/step06-phases.md / step07-priorities.md / step08-pitfalls.md "
              "/ step09-assemble.md")
        return 0

    print(f"[segment2] workdir={workdir} (cwd 锁定, 只读写相对路径)")
    sentences = _load(workdir, "steps/01-sentences/sentences.json")
    grouping = _load(workdir, "steps/03-grouping/grouping.json")
    ratings = _load(workdir, "steps/04-attributes/ratings.json")
    weapons = _load(workdir, "steps/05-weapons/weapons.json")
    print(f"[segment2] 段1输入就绪 (sentences={len(sentences)} grouping={len(grouping)} "
          f"ratings={len(ratings)} weapons=T1:{len(weapons.get('t1', []))} T2:{len(weapons.get('t2', []))})")
    phases = step06(workdir, sentences)
    print(f"[segment2] 06-phases: {len(phases)} 段 (作者 chapters 一章一段) -> steps/06-phases/phases.json")
    pitfalls = step08(workdir, sentences)
    print(f"[segment2] 08-pitfalls: {len(pitfalls)} 条 -> steps/08-pitfalls/pitfalls.json")
    priorities = step07(workdir, sentences, ratings, grouping, phases)
    print(f"[segment2] 07-priorities: upgrades={len(priorities['upgrades'])} shop={len(priorities['shop'])} "
          f"-> steps/07-priorities/priorities.json")
    guide = step09(workdir, grouping, ratings, weapons, phases, priorities, pitfalls)
    print(f"[segment2] 09-assemble: guide sha={guide['sha'][:8]} -> steps/09-assemble/guide.json (= outputs/guide.json)")
    print("[segment2] done. 跑 check: python scripts/check_segment2.py --slug cyborg --variant ultimate")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
