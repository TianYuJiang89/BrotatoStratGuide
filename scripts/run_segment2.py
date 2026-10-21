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
  steps/03-grouping/grouping.json + steps/04-attributes/ratings.json + steps/05-weapons/weapons.json (07 聚合; 08 ban scope 只读 grouping ban 名)
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
           force: bool = False, timeout: float = 1800.0, model=None,
           thinking: str = "medium") -> dict:
    """07-priorities (#65: frozen fewshot + selection/wording 两段 agent; 双侧码切/动词表/verified 已退役).

    调度 (loop, 语义零进代码): selection(串行, 选择 fewshot+04 ratings+05 weapons+03 grouping+06 phases+
    全量整句→{upgrades[{name,quotes}],shop[{name,quotes}]}, N 动态, 保底意图, S/A 优先 B 可例外+须论证,
    T1/ban 不进 shop 意图进 fewshot) → wording×N(并行, 每项独立单 agent→{why,how_to_get}, 数字不丢,
    未提空出) → 合并 (code: quote_details 回填, shop∩T1=∅, shop∩ban=∅, 非空).
    退役: count 双侧码切、拒绝动词表、verified 门、T1 码规则 (改意图+码验交集)、保底 Top1 码规则
    (改意图+码验非空)、why 沿 reason 不重评、07 读 verbs. 07 读 04/05/06/03 新 schema (以落盘为准).
    缺件/编 quote/编数字/幻觉名/ban 进 TopN/T1 进 shop 即 fail loud, 不回落不补空.
    """
    from step07_loop import run_step07_loop
    try:
        weapons = json.loads((workdir / "steps" / "05-weapons" / "weapons.json").read_text(encoding="utf-8"))
    except Exception:
        weapons = {"t1": [], "t2": []}
    return run_step07_loop(workdir, sentences, grouping, ratings, weapons, phases,
                           agent_fn=agent_fn, force=force, timeout=timeout,
                           model=model, thinking=thinking)


def step08(workdir: Path, sentences: list[dict], grouping: list[dict] | None = None, agent_fn=None, force: bool = False, timeout: float = 1800.0, model=None, thinking: str = "medium") -> list[dict]:
    """08-pitfalls (#64: frozen fewshot + discovery/wording 两段 agent; 警告子串召回已退役).

    调度 (loop, 语义零进代码): discovery(串行, fewshot 发现段+全量整句→candidates[{title建议,seeds≥1,extra}],
    N 不定, 无事件空数组诚实交) → wording×N(并行, 每条独立单 agent, 发现 fewshot+分级 fewshot+全量整句+一条→
    {title,severity,why,how_to_avoid,reason,seeds,extra}, trap 须论证看着赚) → 合并 (code: quotes=seeds+extra,
    quote_details 回填, 桶间不重叠, ban 反向 allowlist).
    退役: 警告标记子串召回、N≥3机检(<3讨论同退)、anchors(并入 seeds)、inferred 绿黄、take 闭集动词表
    (意图进 fewshot 码不管)、wordings quotes[0]须种子等窗位规则 (窗机制随码召回一起退)。
    severity 三档保留 (码只验合法值)。wordings.json schema 瘦身 (去 anchors/inferred; ban 避让靠输入新 grouping+码验)。
    缺件/编 quote/编坑/ban 名进坑即 fail loud, 不回落不补空。
    """
    from step08_loop import run_step08_loop
    return run_step08_loop(workdir, sentences, grouping=grouping, agent_fn=agent_fn, force=force, timeout=timeout, model=model, thinking=thinking)

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
        print("子 prompt 见 prompts/step06-phases-fewshot.md (FROZEN, segmentation/wording #63) / prompts/step07-priorities-fewshot.md "
              "(FROZEN, selection/wording 两段 agent, #65) / prompts/step08-pitfalls-fewshot.md (FROZEN, discovery/wording 两段 agent, #64) "
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
    pitfalls = step08(workdir, sentences, grouping)
    print(f"[segment2] 08-pitfalls: {len(pitfalls)} 条 (discovery+wording, 退役码召回) -> steps/08-pitfalls/pitfalls.json")
    priorities = step07(workdir, sentences, ratings, grouping, phases)
    print(f"[segment2] 07-priorities: upgrades={len(priorities['upgrades'])} shop={len(priorities['shop'])} "
          f"-> steps/07-priorities/priorities.json")
    guide = step09(workdir, grouping, ratings, weapons, phases, priorities, pitfalls)
    print(f"[segment2] 09-assemble: guide sha={guide['sha'][:8]} -> steps/09-assemble/guide.json (= outputs/guide.json)")
    print("[segment2] done. 跑 check: python scripts/check_segment2.py --slug cyborg --variant ultimate")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
