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
  steps/01-sentences/sentences.json (全量整句, agent 自捞)
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

    id 窗 (可选): 去重前预筛, 不改关键词口径, 不编数字 (#50 删 W1-5 旧口径, 窗口按调用方传参, 08 不传窗全量扫).
    纯采集无过滤 (#50: glass cannon 按名过滤已删, take 系出局走 08 锚规则 prompt + 召回 seedpool 约束, 不点名).
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


def step06(workdir: Path, sentences: list[dict], agent_fn=None, force: bool = False, timeout: float = 1800.0, model=None, thinking: str = "medium") -> list[dict]:
    """06-phases (#63: frozen fewshot + segmentation/wording 两段 agent; #45 码分桶已退役).

    调度 (loop, 语义零进代码): segmentation(串行, fewshot+全量整句→buckets, 自定义波次,
    phase 运营语言不抄章题, waves 原话作证, 桶间不重叠, N 不定) → wording×N(并行,
    每桶独立单 agent→三问+extra 真桶外) → 合并 (code: 桶内前缀须等于 buckets, 桶外补标 out_of_window).
    退役: buckets 码分桶、meta chapters 作 06 输入、窗内锁死、N 数帽.
    wordings.json schema 不变 (phase/goal/focus/pivot/extra_quotes), 07 无感.
    缺件/编 quote/编波次即 fail loud, 不回落不补空.
    """
    from step06_loop import run_step06_loop
    return run_step06_loop(workdir, sentences, agent_fn=agent_fn, force=force, timeout=timeout, model=model, thinking=thinking)


def step07(workdir: Path, sentences: list[dict], ratings: list[dict],
           grouping: list[dict], phases: list[dict], agent_fn=None,
           force: bool = False) -> dict:
    """优先级 TopN (#62: frozen fewshot + priority-ranking 单 agent; #49/#50 码切码顺延已退役).

    调度 (loop, 语义零进代码): 通览 grouping + 04 ratings + 05 weapons + 06 phases +
    全量整句 → upgrades/shop TopN + why/how_to_get (+analysis 全过程).
    N 动态由 agent 定 (码只验非空, 不验切分); 可推翻 group 建议, 拿 quote 说话;
    ban 件永不进 TopN. 退役: count 码切 (升级/商店双侧)、拒绝词表码顺延、
    不收敛多收/保底码规则 (Top1 意图进 fewshot, 码只验非空).
    缺件/编 quote/幻觉名/ban 进 TopN 即 fail loud, 不回落不补空.
    """
    from step0307_loop import run_step07_loop
    try:
        weapons = json.loads((workdir / "steps" / "05-weapons" / "weapons.json").read_text(encoding="utf-8"))
    except Exception:
        weapons = {"t1": [], "t2": []}
    return run_step07_loop(workdir, sentences, grouping, ratings, weapons, phases,
                           agent_fn=agent_fn, force=force)


# 08两跳召回((a)方案): 第一跳纯警告标记产种子池(零游戏名词) + agent提名主题扩展 + merge种子链约束.
# 标记只认警告言语行为(禁止/义务/翻车/风险/后悔), materials/swap/peacock等地名式名词一律不进;
# 主题由agent从seed出发提名, 每条锚定坑至少一句种子直引(链回seed), 扩展须出自sentences逐字.
# (#50 收敛: 删纯语法粘连 "'d "; 情态须同句另含非情态锚才收, 去注水; take 系出局走 prompt 锚规则 + 召回约束, 代码侧不点名)
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
    "avoid",
]
# 情态单独不成种子 (#50): 须同句另含一个非情态锚才收. 非情态 = 警告实词/禁止/翻车/风险 (don't/can't/never/dangerous/mistake 等).
# "'d " 已删 (纯语法粘连, 去注水); make sure/make certain/be sure/remember 视为非情态 (建议动作, 单独可收).
_MODAL_SIGNALS = {
    "must", "should", "must not", "shouldn't", "should not",
    "need to", "needs to", "have to", "has to", "got to", "gotta", "had to",
    "wish", "should have", "could have", "would have", "if only", "supposed to",
}


def _recall_08(workdir: Path, sentences: list[dict]) -> list[dict]:
    """第一跳(代码, 无判断): 任一警告标记逐字命中即收为种子, 保序去重全量, 落candidates.json(种子池).

    #50 收敛: 情态单独不成种子 (sigs 全落 _MODAL 即跳过, 须同句另含非情态锚); "'d " 已删.
    take 系出局走 prompt 锚规则 (agent 提名时不收 take 系 verified 拿取, 不点名), 召回侧纯标记 + 情态约束, 不读 verbs/grouping (DAG 08 与段1并行).
    """
    qs, qd = _collect(sentences, MARKER_SIGNALS)
    by_q = {d["quote"]: d for d in qd if isinstance(d, dict)}
    cands: list[dict] = []
    for q in qs:
        low = q.lower()
        sigs = sorted({s for s in MARKER_SIGNALS if s.lower() in low})
        if sigs and all(s in _MODAL_SIGNALS for s in sigs):
            continue  # 情态单独不成种子, 去注水
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
            "(seeds提名+extra扩展+anchor/why/how_to_avoid/reason只写判断, take系verified拿取出局不点名)")
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
            # (#50: take 系出局走 prompt 锚规则 + 召回 seedpool 约束, 代码侧不点名; merge 只校验种子链, 不做按名过滤)
        for q in extra:
            if q not in senttexts:
                raise SystemExit(f"step08 extra须出自sentences逐字: {e.get('title')} :: {q[:40]}")
            # (#50: extra 允许 take 作为解法证据 (如 horde 波前合核弹), take 出局仅约束召回 seeds 提名, 不点名)
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
        print("子 prompt 见 prompts/step06-phases-fewshot.md (FROZEN, segmentation/wording #63) / step07-priorities.md / step08-pitfalls.md "
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
    print(f"[segment2] 06-phases: {len(phases)} 段 (运营波次自定义, 不抄章题) -> steps/06-phases/phases.json")
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
