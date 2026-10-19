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
    # live_phases 仅用于节奏引用 (空段跳过); 升级沿用 S/A 排名 + 商店读新分组, 不自创不重评
    _ = live_phases
    # 升级 Top3 沿用: 只认 04 输出 S/A + count 降序 (不自创, 不重评; 04 新评级自动跟)
    sa = [r for r in ratings if r.get("rating") in ("S", "A")]
    sa = sorted(sa, key=lambda x: -int(x.get("count", 0)))
    if len(sa) < 3:
        raise SystemExit(f"step07 升级候选不足 S/A={len(sa)}: 段1 ratings 疑异常")
    top_up = sa[:3]
    # 商店 TopN 断层动态 (#49: 去 Top3 写死 + Peacock 按名顺延; 只认新分组 must_take + verified + count 降序)
    # 通用顺延 (不点名): 任一候选 quotes+reason 含拒绝动词原话即顺延 (拿取否定/跳过系逐字, 不含泛 don't want)
    _REJECT = ("not taking", "not take", "don't take", "do not take",
               "don't buy", "do not buy", "not buying",
               "don't pick", "do not pick", "not picking",
               "don't lock", "do not lock",
               "skip", "avoid", "ban", "recycle", "sell",
               "passed on", "ignoring", "ignored", "not interested",
               "don't want to take", "do not want to take",
               "don't want to buy", "do not want to buy")

    def _has_refusal(g: dict) -> bool:
        qall = " ".join(g.get("quotes", [])).lower() + " " + str(g.get("reason", "")).lower()
        return any(sig in qall for sig in _REJECT)

    cands = [g for g in grouping if g.get("group") == "must_take" and g.get("confidence") == "verified"]
    cands = sorted(cands, key=lambda x: (-int(x.get("count", 0)), str(x.get("name_en", ""))))
    filtered: list[dict] = [g for g in cands if not _has_refusal(g)]
    if not filtered:
        raise SystemExit(f"step07 商店候选不足 must_take verified 去拒绝后=0 (cands={len(cands)}): 段1 grouping 疑异常")
    # 断层切分 (与 05 排名制同一刀法): gaps=count[i]-count[i+1], 最大断层即止, 不断层(max==0)多收, 保底 Top1
    counts = [int(g.get("count", 0)) for g in filtered]
    if len(filtered) == 1:
        shop = filtered
    else:
        gaps = [counts[i] - counts[i + 1] for i in range(len(counts) - 1)]
        mx = max(gaps)
        if mx == 0:
            shop = filtered
        else:
            cut = next(i for i, gp in enumerate(gaps) if gp == mx)
            shop = filtered[:cut + 1]
    if not shop:
        raise SystemExit(f"step07 商店断层切分空 (filtered={len(filtered)}): 保底 Top1 失败")
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


# 08两跳召回((a)方案): 第一跳纯警告标记产种子池(零游戏名词) + agent提名主题扩展 + merge种子链约束.
# 标记只认警告言语行为(禁止/义务/翻车/风险/后悔), materials/swap/peacock等地名式名词一律不进;
# 主题由agent从seed出发提名, 每条锚定坑至少一句种子直引(链回seed), 扩展须出自sentences逐字.
MARKER_SIGNALS = [
    "mistake", "wrong", "fail", "failed", "fault",
    "dying", "die", "died", "death", "hurt", "hurts", "painful",
    "lose", "lost", "losing", "took damage", "taking damage", "too late",
    "went wrong", "given up", "gave up",
    "don't", "do not", "never", "can't", "cannot", "shouldn't", "should not", "must not",
    "need to", "needs to", "have to", "has to", "got to", "gotta", "must", "should", "had to",
    "make sure", "make certain", "be sure", "remember",
    "dangerous", "risky", "risk", "trap", "careful", "worry", "worried", "warn", "warning",
    "watch out", "beware", "awkward", "problem", "struggle", "survive", "barely", "hard",
    "wish", "should have", "could have", "would have", "if only", "supposed to",
    "avoid", "'d ",
]


def _recall_08(workdir: Path, sentences: list[dict]) -> list[dict]:
    """第一跳(代码, 无判断): 任一警告标记逐字命中即收为种子, 保序去重全量, 落candidates.json(种子池)."""
    qs, qd = _collect(sentences, MARKER_SIGNALS)
    by_q = {d["quote"]: d for d in qd if isinstance(d, dict)}
    cands: list[dict] = []
    for q in qs:
        low = q.lower()
        sigs = sorted({s for s in MARKER_SIGNALS if s.lower() in low})
        d = by_q.get(q, {})
        cands.append({"quote": q, "signals": sigs, "start": d.get("start"),
                      "end": d.get("end"), "t": d.get("t"),
                      "context": d.get("context", q[:300])})
    outdir = workdir / "steps" / "08-pitfalls"
    outdir.mkdir(parents=True, exist_ok=True)
    (outdir / "candidates.json").write_text(json.dumps(cands, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    return cands


def _load_wordings_08(workdir: Path) -> list[dict]:
    """判断(agent): 缺件或旧schema即fail, 指引跑 prompts/step08-pitfalls.md."""
    p = workdir / "steps" / "08-pitfalls" / "wordings.json"
    if not p.exists():
        raise SystemExit(
            "step08 缺 wordings.json (agent判断未写): 按 prompts/step08-pitfalls.md "
            "读 steps/08-pitfalls/candidates.json (种子池) + sentences.json (扩展备查) 写 wordings.json "
            "(seeds提名+extra扩展+anchor/why/how_to_avoid/reason只写判断, glass cannon禁入)")
    try:
        w = json.loads(p.read_text(encoding="utf-8"))
    except Exception as err:
        raise SystemExit(f"step08 wordings.json 解析失败: {err}")
    if not isinstance(w, list) or len(w) < 3:
        raise SystemExit(f"step08 wordings须数组>=3条(N不定但设底线), got {len(w) if isinstance(w, list) else type(w)}")
    for i, e in enumerate(w):
        if not isinstance(e, dict):
            raise SystemExit(f"step08 wordings[{i}]须对象")
        if not isinstance(e.get("title"), str) or not e["title"].strip():
            raise SystemExit(f"step08 wordings[{i}]缺title")
        if e.get("severity") not in ("fatal", "risky", "trap"):
            raise SystemExit(f"step08 wordings[{i}] severity须fatal/risky/trap")
        if not isinstance(e.get("anchors"), list) or any(not isinstance(a, str) for a in e["anchors"]):
            raise SystemExit(f"step08 wordings[{i}] anchors须字符串数组(无则[])")
        if not isinstance(e.get("seeds"), list) or any(not isinstance(q, str) for q in e["seeds"]):
            raise SystemExit(f"step08 wordings[{i}] seeds须字符串数组")
        if e.get("anchors") and not e["seeds"]:
            raise SystemExit(f"step08 wordings[{i}] 锚定条seeds须非空(至少一句链回seed)")
        if not isinstance(e.get("extra"), list) or any(not isinstance(q, str) for q in e["extra"]):
            raise SystemExit(f"step08 wordings[{i}] extra须字符串数组(无则[])")
        for k in ("why", "how_to_avoid"):
            if not isinstance(e.get(k), str) or len(e[k].strip()) < 8:
                raise SystemExit(f"step08 wordings[{i}]缺{k}(人话一句>=8字)")
        if not isinstance(e.get("reason"), str) or len(e["reason"].strip()) < 4:
            raise SystemExit(f"step08 wordings[{i}]缺reason(分组/扩展依据, 锚定条也要)")
        if not isinstance(e.get("inferred"), bool):
            raise SystemExit(f"step08 wordings[{i}] inferred须bool")
    return w


def step08(workdir: Path, sentences: list[dict]) -> list[dict]:
    # 第一跳(代码) + 判断(agent) + 合并校验(代码): 锚定条至少一句种子直引, 扩展须出自sentences逐字.
    cands = _recall_08(workdir, sentences)
    seedpool = {c["quote"] for c in cands if isinstance(c, dict)}
    senttexts = {s["text"] for s in sentences if isinstance(s, dict)}
    wordings = _load_wordings_08(workdir)
    qlookup = _quote_lookup(sentences)
    pitfalls: list[dict] = []
    for e in wordings:
        seeds: list[str] = list(e["seeds"])
        extra: list[str] = list(e["extra"])
        if len(set(seeds)) != len(seeds) or len(set(extra)) != len(extra):
            raise SystemExit(f"step08 seeds/extra须去重: {e.get('title')}")
        if set(seeds) & set(extra):
            raise SystemExit(f"step08 seeds/extra须不交: {e.get('title')}")
        for q in seeds:
            if q not in seedpool:
                raise SystemExit(f"step08 seed须出自种子池逐字: {e.get('title')} :: {q[:40]}")
            if "glass cannon" in q.lower():
                raise SystemExit(f"step08 glass cannon系take排除: {e.get('title')}")
        for q in extra:
            if q not in senttexts:
                raise SystemExit(f"step08 extra须出自sentences逐字: {e.get('title')} :: {q[:40]}")
            if "glass cannon" in q.lower():
                raise SystemExit(f"step08 glass cannon系take排除: {e.get('title')}")
        akeys = list(e["anchors"])
        for a in akeys:
            low_a = a.lower()
            if not any(low_a in q.lower() for q in seeds):
                raise SystemExit(f"step08 anchor须出自本条种子句逐字: {e.get('title')}={a}")
        kind = "anchor" if akeys else "discretion"
        if kind == "anchor" and e["inferred"] is not False:
            raise SystemExit(f"step08 锚定条inferred须false(警告锚定非推断): {e.get('title')}")
        if kind == "discretion" and e["inferred"] is not True:
            raise SystemExit(f"step08 裁量条inferred须true: {e.get('title')}")
        qs = seeds + extra
        qd = []
        for q in qs:
            hits = qlookup.get(q, [])
            h = hits[0] if hits else {"start": None, "end": None, "t": None, "context": q[:300]}
            qd.append({"quote": q, "start": h["start"], "end": h["end"], "t": h["t"], "context": h["context"]})
        pitfalls.append({
            "title": str(e["title"]), "severity": str(e["severity"]), "kind": kind,
            "anchor": akeys[0] if akeys else None, "anchors": akeys,
            "seeds": seeds, "extra": extra,
            "why": str(e["why"]).strip(), "how_to_avoid": str(e["how_to_avoid"]).strip(),
            "quotes": qs, "quote_details": qd,
            "quote": qs[0], "reason": str(e["reason"]).strip(), "inferred": bool(e["inferred"]),
        })
    outdir = workdir / "steps" / "08-pitfalls"
    outdir.mkdir(parents=True, exist_ok=True)
    (outdir / "pitfalls.json").write_text(json.dumps(pitfalls, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    (workdir / "outputs").mkdir(parents=True, exist_ok=True)
    (workdir / "outputs" / "pitfalls.json").write_text(json.dumps(pitfalls, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
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
