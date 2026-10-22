#!/usr/bin/env python3
"""B-段1实施 (#40, #66 02退役): 01-sentences 直达 03-grouping/04-attributes/05-weapons, cyborg/ultimate 单变体.

沿 #39 决议 (B 全链展开) + #66 (02 整步退役):
- 清单 8 步 (02 已退役), 段1 = 01 + 03 + 04 + 05 (01 直达 03, 02 跳过).
- 载体延续试点三件套 (prompts/step0X + steps/0X-*/ + check + audit 动态读).
- Q3 复读: 轻量只去展示重 (grouping.quotes 去重, count 沿 build_mentions 不动).
- Q4 时间戳: sentence {id,text[,start,end]}, B-04 起统一加; 开 04 前先重跑 01-03 一次 (幂等).
- Q5 context: quote 不动, grouping/audit 加只读 context (前后 1 句), 不进机检 (#66: verbs 已退役).
- 旧 SOP 只作参考, 不作输入; 旧链冻结.

本脚本确定性执行 (沿 run_pilot.py 模式, 子 agent RPC 为 --rpc 模式):
  python scripts/run_segment1.py --slug cyborg --variant ultimate
  python scripts/run_segment1.py --slug cyborg --variant ultimate --rpc

输入 (cwd 锁定 G:/brotato-work/<slug>/<variant>/, 只拷必要文件):
  inputs/ 三件 (source.vtt + meta.json + manifest.json)
全局 (repo 侧只读, 非 runtime):
  data/terms.csv (主 17 + 次级 22) + data/wiki-cache.json (注册表唯一 URL 源)
中间产物 (G work 动态产生, 不读 repo runtime):
  steps/01-sentences/ -> 03-grouping/04-attributes/05-weapons (count/quotes 现场扫 sentences, rating/note 自推, 禁读 data/mentions + data/builds)
  (#66: 02-verbs 已退役, verbs.json 停产, 01 直达 03/04/05, 不经 02)
输出:
  steps/01-sentences/sentences.json (新 schema, start/end)
  steps/03-grouping/grouping.json (= outputs/groups.json, +quote_details)
  steps/04-attributes/ratings.json (+ outputs/ratings.json)
  steps/05-weapons/weapons.json (+ outputs/weapons.json)
"""

from __future__ import annotations

import argparse
import csv
import hashlib
import json
import re
import sys
from pathlib import Path

REPO = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(REPO / "scripts"))

# #66 02 退役: pilot 动词表导入已删 (step02 停产, 01 直达 03/04/05).

TS_RE = re.compile(
    r"(\d{2}):(\d{2}):(\d{2})[.,](\d{3})\s*-->\s*(\d{2}):(\d{2}):(\d{2})[.,](\d{3})"
)


def _ts_to_sec(h: str, m: str, s: str, ms: str) -> float:
    return int(h) * 3600 + int(m) * 60 + int(s) + int(ms) / 1000.0


def _fmt_ts(h: str, m: str, s: str, ms: str) -> str:
    return f"{h}:{m}:{s}.{ms}"


def parse_vtt_timed(text: str) -> list[dict]:
    """Timed VTT 解析: 与 parse_vtt 同文本口径 + start/end.

    - 按空行分块 (同 build_mentions.parse_vtt 正则), 复读原样保留.
    - 时间戳与文本分块时 (滚动字幕), 用 pending 关联到下一文本句.
    - 文本清洗与旧口径完全一致 (去头/去时间戳行/去序号/去 HTML tag/join/cap 500).
    - 返回 [{text, start, end, start_s, end_s}] (无时间戳则 None, 如首句 header).
    """
    blocks = re.split(r"\r?\n\s*\r?\n", text)
    cues: list[dict] = []
    pending: dict | None = None
    for block in blocks:
        lines = [ln.strip() for ln in block.strip().splitlines()]
        if not lines:
            continue
        if lines[0].upper().startswith("WEBVTT"):
            lines = lines[1:]
        if not lines:
            continue
        if lines[0].upper().startswith(("NOTE", "STYLE", "REGION")):
            continue
        # 本块时间戳 (取首个 --> 行)
        blk_start = blk_end = None
        blk_ss = blk_es = None
        for ln in lines:
            if "-->" in ln:
                m = TS_RE.search(ln)
                if m:
                    h1, mi1, s1, ms1, h2, mi2, s2, ms2 = m.groups()
                    blk_start = _fmt_ts(h1, mi1, s1, ms1)
                    blk_end = _fmt_ts(h2, mi2, s2, ms2)
                    blk_ss = _ts_to_sec(h1, mi1, s1, ms1)
                    blk_es = _ts_to_sec(h2, mi2, s2, ms2)
                break
        if blk_start is not None:
            pending = {"start": blk_start, "end": blk_end,
                       "start_s": blk_ss, "end_s": blk_es}
        # 本块文本 (同旧口径)
        content: list[str] = []
        for ln in lines:
            if not ln:
                continue
            if "-->" in ln:
                continue
            if re.fullmatch(r"\d+", ln):
                continue
            if ln.strip().lower().startswith(("kind:", "language:")):
                continue
            no_tag = re.sub(r"<[^>]+>", "", ln).strip()
            if no_tag:
                content.append(no_tag)
        if content:
            cue = " ".join(content).strip()
            if len(cue) > 500:
                cue = cue[:500]
            ts = pending if pending is not None else {
                "start": None, "end": None, "start_s": None, "end_s": None}
            cues.append({"text": cue, **ts})
            # 文本已消费, pending 清零 (下一文本需新的时间戳; 无则 None)
            # 注意: 滚动复读每句前必有时间戳块, 故清零后下一时间戳块会重新 pending.
            # 若连续两文本块无时间戳间隔 (不应发生), 第二句将无时间戳, 诚实置空.
            pending = None
    # #43 滚动折叠: 与 build_mentions 同口径, auto 折叠为整句, manual 自动 no-op.
    try:
        from build_mentions import fold_timed_cues as _fold_timed
    except Exception:
        _fold_timed = None
    if _fold_timed is not None:
        try:
            folded = _fold_timed(cues)
            if folded:
                return folded
        except Exception:
            pass
    return cues


def sha1_of(path: Path) -> str:
    h = hashlib.sha1()
    h.update(path.read_bytes())
    return h.hexdigest()


def ensure_inputs(slug: str, vid: str, workdir: Path) -> dict:
    """inputs 校验 + slice 退役 (#61: Step00 后新链只认 inputs, 不读旧链).

    三件须已由 scripts/fetch_inputs.py 产出. 本步只做:
    - 三件存在性校验 (缺件即报错, 指引先跑 fetch_inputs 取证)
    - sha 对上校验 (manifest.sources[0].sha1 == source.vtt 实际 sha)
    - registry-slice 残留即删 (#61 退役, 不读不刷新)
    meta/manifest 为 Step00 取证产物, 本步不覆写 (provenance 只认取证).
    #67 章节门拆除: meta.chapters 可空数组, 下游 (06 segmentation) 不读章节, 此处不验章节.
    """
    inputs = workdir / "inputs"
    for _f in ("source.vtt", "meta.json", "manifest.json"):
        if not (inputs / _f).exists():
            raise SystemExit(
                f"missing inputs/{_f} for {slug}/{vid}: "
                f"先跑 scripts/fetch_inputs.py --url <youtube-url> "
                f"--slug {slug} --variant {vid} 取证")
    # #61 退役: 旧 registry-slice.json 若残留即删 (不读, 不刷新)
    _stale = inputs / "registry-slice.json"
    if _stale.exists():
        try:
            _stale.unlink()
        except Exception:
            pass
    manifest = json.loads((inputs / "manifest.json").read_text(encoding="utf-8"))
    # #67 章节门拆除: 不验 meta.chapters（可空数组，下游不读章节）。只验三件 + sha。
    actual_sha = sha1_of(inputs / "source.vtt")
    expect_sha = (manifest.get("sources") or [{}])[0].get("sha1", "")
    if actual_sha != expect_sha:
        raise SystemExit(
            f"sha mismatch for {slug}/{vid}: manifest {str(expect_sha)[:8]} "
            f"vs actual {actual_sha[:8]} (重跑 Step00 取证)")
    return manifest


def build_context(sentences: list[dict], idx: int) -> str:
    """前后 1 句拼接只读 context (不进机检, quote 保持逐字原文). cap 300 字."""
    parts: list[str] = []
    if idx > 0:
        parts.append(sentences[idx - 1]["text"])
    parts.append(sentences[idx]["text"])
    if idx + 1 < len(sentences):
        parts.append(sentences[idx + 1]["text"])
    ctx = " … ".join(parts)
    if len(ctx) > 300:
        ctx = ctx[:300]
    return ctx


def step01(workdir: Path) -> list[dict]:
    src = (workdir / "inputs" / "source.vtt").read_text(encoding="utf-8")
    timed = parse_vtt_timed(src)
    sentences = [{"id": i + 1, "text": c["text"],
                  "start": c["start"], "end": c["end"],
                  "start_s": c["start_s"], "end_s": c["end_s"],
                  "t": (int(c["start_s"]) if c.get("start_s") is not None else None)}
                 for i, c in enumerate(timed)]
    outdir = workdir / "steps" / "01-sentences"
    outdir.mkdir(parents=True, exist_ok=True)
    (outdir / "sentences.json").write_text(
        json.dumps(sentences, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    return sentences


def step03(workdir: Path, sentences: list[dict], agent_fn=None, force: bool = False) -> list[dict]:
    """分组: frozen fewshot + discovery/evidence/grouping-ranking 三段 agent (#62; #48/#50 锚+裁量已退役).

    调度 (loop, 语义零进代码): discovery(串行, fewshot 发现段+全量整句→candidates, completeness 归它,
    scope 自此脱离 slice) → evidence×N(并行, 每件独立单 agent→group 建议/quotes/analysis/note)
    → grouping-ranking(串行, 通览全量整句+N 份 evidence→定四组, 拿 quote 说话禁数帽).
    退役: slice(03 输入+fetch 产+ensure 刷+check 认)、closed/mapped 动词锚、verb_type/has_verb/
    inferred/confidence 码检、拒绝动词表、count 最大断层、不断层多收/保底 Top1 码规则
    (Top1 意图进 fewshot, 码只验非空)、03 不读 verbs (#66 02 退役, verbs 留给自家消费者注释保留)。
    缺件/编 quote/幻觉名即 fail loud, 不回落不补空。
    """
    from step0307_loop import run_step03_loop
    return run_step03_loop(workdir, sentences, agent_fn=agent_fn, force=force)


def step04(workdir: Path, sentences: list[dict], agent_fn=None, force: bool = False) -> list[dict]:
    """属性评级 39 全量 (#60: frozen fewshot + for-loop 单属性 agent x39; #47/#50 锚+裁量已退役).

    调度 (loop, 语义零进代码): 每属性独立起一个 LLM agent, 每次只塞 基准fewshot
    + 该角色全量整句 (含 start/end/t) + 这一个属性名, 输出 {term_en, rating, quotes,
    analysis, summary} (count 由代码回填, agent 不填). 锚规则 (动词闭集/同句窗/over/
    负面词表/count上下半) 全删, 不查动词, 不查 over, 不设 S/A 数量帽 (#58 已毙).
    缺件/编 quote 即 fail loud, 不回落不补空.
    """
    from step04_loop import run_step04_loop
    return run_step04_loop(workdir, sentences, agent_fn=agent_fn, force=force)

def step05(workdir: Path, sentences: list[dict], agent_fn=None, force: bool = False) -> dict:
    """武器分档 T1/T2 (#61: frozen fewshot + discovery/evidence/ranking 三段 agent; #47/#50 锚+裁量已退役).

    调度 (loop, 语义零进代码): discovery(串行, fewshot 发现段+全量整句→candidates, completeness 归它)
    → evidence×N(并行, 每把独立单 agent, fewshot+全量整句+一名→tier建议/quotes/analysis/note)
    → ranking(串行, 通览全量整句+N份evidence→切t1/t2+note定稿, T1>=1由它保, 可推翻 evidence tier).
    退役: confidence/kind/inferred/anchors/score+5/断层/数字词表/verified加分/T1-note-必含数字码检、
    inputs/registry-slice.json (fetch 停产+旧文件删)、05 不读 02-verbs (#66 02 退役, 注释保留)。
    note 保意图不保码检 (码只查非空)。缺件/编 quote/幻觉名即 fail loud, 不回落不补空。
    """
    from step05_loop import run_step05_loop
    return run_step05_loop(workdir, sentences, agent_fn=agent_fn, force=force)


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description="B-段1实施 (#40)")
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
        print("子 prompt 见 prompts/step01-sentences.md "
              "/ prompts/step03-grouping-fewshot.md (FROZEN, discovery/evidence/grouping-ranking 三段 agent, #62) "
              "/ prompts/step04-ratings-fewshot.md (FROZEN, for-loop x39) / prompts/step05-{discovery,evidence,ranking}-fewshot.md "
              "(FROZEN v2, 三本手册各贴各, discovery/evidence/ranking 三段 agent, #61)")
        return 0

    print(f"[segment1] workdir={workdir} (cwd 锁定, 只读写相对路径)")
    ensure_inputs(slug, vid, workdir)
    print("[segment1] inputs 三件校验通过 (Step00 取证, 只认 inputs, #61 slice 已退役, #66 02 已退役)")
    sentences = step01(workdir)
    print(f"[segment1] 01-sentences: {len(sentences)} 句 (start/end 新 schema) -> steps/01-sentences/sentences.json")
    grouping = step03(workdir, sentences)
    print(f"[segment1] 03-grouping: {len(grouping)} 件 (quotes 去重, +quote_details)")
    ratings = step04(workdir, sentences)
    print(f"[segment1] 04-attributes: {len(ratings)} terms (主17+次级22) -> steps/04-attributes/ratings.json")
    weapons = step05(workdir, sentences)
    print(f"[segment1] 05-weapons: T1={len(weapons['t1'])} T2={len(weapons['t2'])} -> steps/05-weapons/weapons.json")
    print("[segment1] done. 跑 check: python scripts/check_segment1.py --slug cyborg --variant ultimate")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
