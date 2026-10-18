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


def step06(workdir: Path, sentences: list[dict]) -> list[dict]:
    # 三段关键词 (现场扫, 不照抄 chapters; chapters 仅备查)
    k_early = ["early", "start", "first", "lock", "ranged", "minigun", "screwdriver",
               "elite", "quickly", "first half", "beginning"]
    k_mid = ["engineering", "horde", "nuke", "nuclear", "mid", "swap", "second half",
             "materials", "convert", "transition to the engineering"]
    k_late = ["late", "boss", "heal", "life steal", "peacock", "wave 16", "wave 17",
              "wave 18", "wave 20", "final", "knock back", "flies", "elite"]
    q1, d1 = _collect(sentences, k_early, id_max=150)
    q2, d2 = _collect(sentences, k_mid, id_min=80, id_max=300)
    q3, d3 = _collect(sentences, k_late, id_min=200)
    if not q1 or not q2 or not q3:
        raise SystemExit(f"step06 现场扫 Quotes 不足 (early={len(q1)} mid={len(q2)} late={len(q3)}): sentences 疑异常")
    phases = [
        {"phase": "W1-5", "waves": "W1-5",
         "goal": f"开局前半波远程清场立住，锁枪补第二把远程保证 elite 击杀；原话“{_short(q1[0])}…”",
         "focus": f"配装重心：加特林开局锁1把 + 螺丝刀中期补，商店直购不拖；原话“{_short(q1[1] if len(q1) > 1 else q1[0])}…”",
         "pivot": f"转向点 W5→W6：前半远程压制结束，中期转工程养结构，horde/elite 提前准备；原话“{_short(q2[0])}…”",
         "quotes": q1, "quote_details": d1},
        {"phase": "W6-12", "waves": "W6-12",
         "goal": f"中期工程转换后靠螺丝刀+结构站场，horde 波用核弹过渡；原话“{_short(q2[0])}…”",
         "focus": f"配装重心：螺丝刀成型 + 口袋工厂/炮塔养后半波，材料顺路捡不落地；原话“{_short(q2[1] if len(q2) > 1 else q2[0])}…”",
         "pivot": f"转向点 W12→W13：后期 boss/elite 血量上涨，需高基础伤害抢转换前击杀；原话“{_short(q3[0])}…”",
         "quotes": q2, "quote_details": d2},
        {"phase": "W13-20", "waves": "W13-20",
         "goal": f"后期高工程+高吸血站桩，boss 先杀 whale，怪多即回血；原话“{_short(q3[0])}…”",
         "focus": f"配装重心：生命窃取+消耗品续航顶残血站桩，peacock 波控刷怪；原话“{_short(q3[1] if len(q3) > 1 else q3[0])}…”",
         "pivot": f"终局 W20：range half 结束即收，engineering half 靠炮塔/口袋工厂保险；原话“{_short(q3[2] if len(q3) > 2 else q3[0])}…”",
         "quotes": q3, "quote_details": d3},
    ]
    outdir = workdir / "steps" / "06-phases"
    outdir.mkdir(parents=True, exist_ok=True)
    (outdir / "phases.json").write_text(json.dumps(phases, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    (workdir / "outputs").mkdir(parents=True, exist_ok=True)
    (workdir / "outputs" / "phases.json").write_text(json.dumps(phases, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    return phases


def step07(workdir: Path, sentences: list[dict], ratings: list[dict],
           grouping: list[dict], phases: list[dict]) -> dict:
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


def step08(workdir: Path, sentences: list[dict]) -> list[dict]:
    specs = [
        ("半波转换踩空", "fatal",
         ["swap", "transition", "halfway", "kill elites", "before", "convert"],
         "前半波没打完 elite/boss，转换后变近战刮痧",
         "看顶栏 halfway，前半波集火 elite， engineering half 靠螺丝刀+结构补"),
        ("材料落地不捡", "risky",
         ["materials on the ground", "picking them up", "mid game", "worry"],
         "中期材料落地不捡，经济崩盘",
         "材料顺路捡，不跨波囤，中期必清地"),
        ("站位撞出生点", "risky",
         ["mistake", "awkward", "spawning", "knock back", "stargazers"],
         "站位撞投射物出生点 + 击退丢失后难处理",
         "开局记出生点，不贴左墙；丢击退后靠走位拉扯"),
        ("Peacock刷怪失控", "trap",
         ["peacock", "flies", "wave 16", "mini boss", "spawn", "do not want", "dangerous"],
         "Peacock 波 +30% 伤 + 刷怪失控（小怪/放出器）",
         "horde 波提前合核弹清场，peacock 波控刷怪数，enhanced flies 用前半远程点掉"),
    ]
    pitfalls = []
    for title, sev, keys, why_tail, avoid in specs:
        qs, qd = _collect(sentences, keys)
        if not qs:
            raise SystemExit(f"step08 现场扫不足 {title}: keywords={keys}")
        pitfalls.append({
            "title": title, "severity": sev,
            "why": f"{why_tail}；原话“{_short(qs[0])}…”",
            "how_to_avoid": f"{avoid}；原话“{_short(qs[1] if len(qs) > 1 else qs[0])}…”",
            "quotes": qs, "quote_details": qd,
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
    print(f"[segment2] 06-phases: {len(phases)} 段 (W1-5/6-12/13-20) -> steps/06-phases/phases.json")
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
