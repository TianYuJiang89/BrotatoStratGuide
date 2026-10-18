#!/usr/bin/env python3
"""Pilot runner (#38): cyborg/ultimate 01-sentences -> 02-verbs -> 03-grouping.

Contracts:
- #34 目录契约: G:/brotato-work/<slug>/<variant>/ 唯一写区, variant-id 单真源,
  inputs 四件 + steps 三步 + 最简 schema, HTML 用 ?base + 目录 picker 动态读.
- #36 步骤契约: 闭集 10 动词下限, verified/candidates 双视图, 全收录 count>0 68,
  三组 + 低频一句话, 机检 + 人看一单.
- #35 调用载体: 主脚本锁 cwd + 只拷必要文件, 子 prompt 只喂本步 SOP.
  本 pilot 用确定性本地执行实现同 schema (子 agent RPC 为 --rpc 模式, 见 README);
  prompts/step0*.md 即子 prompt 契约载体, 本脚本即主脚本.

Usage:
  python scripts/run_pilot.py --slug cyborg --variant ultimate
  python scripts/run_pilot.py --slug cyborg --variant ultimate --rpc  # 打印 RPC 子进程命令, 不执行 LLM
"""

from __future__ import annotations

import argparse
import hashlib
import json
import re
import shutil
import sys
from pathlib import Path

REPO = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(REPO / "scripts"))
from build_mentions import parse_vtt, build_pattern_map, load_terms, load_registry_names  # noqa: E402

CLOSED_VERBS = ["take", "buy", "pick up", "lock", "get", "roll for", "ban", "recycle", "sell", "skip"]

# 闭集动词变形 (不扩展新动词, 只认变形)
VERB_PATTERNS: dict[str, str] = {
    "take": r"\btakes?\b|\btook\b|\btaking\b|\btaken\b",
    "buy": r"\bbuys?\b|\bbought\b|\bbuying\b",
    "pick up": r"\bpicks?\s+up\b|\bpicked\s+up\b|\bpick\s+up\b|\bpicking\s+up\b",
    "lock": r"\blocks?\b|\blocked\b|\blocking\b",
    "get": r"\bgets?\b|\bgot\b|\bgetting\b",
    "roll for": r"\brolls?\b|\brolled\b|\brolling\b",
    "ban": r"\bbans?\b|\bbanned\b|\bbanning\b",
    "recycle": r"\brecycles?\b|\brecycled\b|\brecycling\b",
    "sell": r"\bsells?\b|\bsold\b|\bselling\b",
    "skip": r"\bskips?\b|\bskipped\b|\bskipping\b",
}

# 动词 paraphrase -> 闭集映射 (candidates, 不进 verified)
PARAPHRASE_MAP: dict[str, str] = {
    "grab": "take",
    "snatch": "take",
    "pick": "take",
    "avoid": "ban",
    "avoiding": "ban",
    "ignoring": "skip",
    "ignore": "skip",
    "passed on": "skip",
    "pass": "skip",
    "skipping": "skip",
    "bought": "buy",  # 形态归一仍算 closed, 但 surface 保留
}

PARA_PATTERNS: dict[str, str] = {
    "grab": r"\bgrabs?\b|\bgrabbed\b|\bgrabbing\b",
    "snatch": r"\bsnatch(?:es|ed|ing)?\b",
    "pick": r"\bpicks?\b|\bpicked\b|\bpicking\b",
    "avoid": r"\bavoids?\b|\bavoided\b|\bavoiding\b",
    "ignoring": r"\bignoring\b|\bignores?\b|\bignored\b",
    "passed on": r"\bpassed\s+on\b|\bpass\s+on\b",
    "skipping": r"\bskipping\b",
    "bought turret instead of": r"\bbought\s+.*?instead\s+of\b",
}


def sha1_of(path: Path) -> str:
    h = hashlib.sha1()
    h.update(path.read_bytes())
    return h.hexdigest()


def ensure_inputs(slug: str, vid: str, workdir: Path) -> dict:
    """拷必要文件进工作区 (只拷四件, 不整仓拷贝). 返回 manifest dict."""
    inputs = workdir / "inputs"
    inputs.mkdir(parents=True, exist_ok=True)
    repo_vtt = REPO / "data" / "subs" / f"{slug}__{vid}.en-orig.vtt"
    if not repo_vtt.exists():
        raise SystemExit(f"missing repo VTT: {repo_vtt}")
    shutil.copy2(repo_vtt, inputs / "source.vtt")
    sha = sha1_of(inputs / "source.vtt")

    # meta.json: 标题/描述/chapters/双标注五元组 (沿 top3 + manifest sources)
    top3 = json.loads((REPO / "data" / "work" / slug / "top3.json").read_text(encoding="utf-8"))
    work_manifest = json.loads((REPO / "data" / "work" / slug / "manifest.json").read_text(encoding="utf-8"))
    src = next((s for s in work_manifest.get("sources", []) if s.get("variant") == vid), None)
    if src is None:
        raise SystemExit(f"missing source for {slug}__{vid} in data/work manifest")
    meta = {
        "title": src.get("title", ""),
        "description": f"Brotato {src.get('description_version','')} {src.get('difficulty','')} Guide for {slug}",
        "game_version": src.get("game_version", ""),
        "published": src.get("published", ""),
        "chapters": [c.strip() for c in str(src.get("chapters_note", "")).split("/") if c.strip()],
        "video_id": src.get("video_id", ""),
        "url": src.get("url", ""),
        "difficulty": src.get("difficulty", ""),
    }
    (inputs / "meta.json").write_text(json.dumps(meta, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")

    # registry-slice.json: 本变体武器+道具子集 (count>0 全集, 沿 mentions 口径)
    mentions_path = REPO / "data" / "mentions" / f"{slug}__{vid}.json"
    mentions = json.loads(mentions_path.read_text(encoding="utf-8"))
    weapons_pos = sorted([k for k, v in mentions.get("weapons", {}).items() if v.get("count", 0) > 0])
    items_pos = sorted([k for k, v in mentions.get("items", {}).items() if v.get("count", 0) > 0])
    # 全量武器名备查 (slice 只含命中子集, 未命中 172 件不进表)
    reg_slice = {"weapons": weapons_pos, "items": items_pos}
    (inputs / "registry-slice.json").write_text(
        json.dumps(reg_slice, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
    )

    # manifest.json: sha1 + 取材 URL + issue 号
    sop_ver = ""
    try:
        import subprocess as sp
        p = sp.run(
            ["git", "log", "-1", "--format=%H", "--", "docs/sop/new-character-guide.md"],
            cwd=str(REPO), capture_output=True, text=True,
        )
        sop_ver = p.stdout.strip()
    except Exception:
        sop_ver = ""
    manifest = {
        "slug": slug,
        "variant": vid,
        "covers": ["Ultimate"] if vid == "ultimate" else [vid],
        "sop_version": sop_ver,
        "issue": 38,
        "sources": [
            {
                "difficulty": src.get("difficulty", ""),
                "title": src.get("title", ""),
                "url": src.get("url", ""),
                "sha1": sha,
                "vtt": "inputs/source.vtt",
                "duration": src.get("duration", ""),
                "game_version": src.get("game_version", ""),
                "video_id": src.get("video_id", ""),
            }
        ],
    }
    (inputs / "manifest.json").write_text(
        json.dumps(manifest, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
    )
    return manifest


def step01(workdir: Path) -> list[dict]:
    src = (workdir / "inputs" / "source.vtt").read_text(encoding="utf-8")
    cues = parse_vtt(src)
    sentences = [{"id": i + 1, "text": c} for i, c in enumerate(cues)]
    outdir = workdir / "steps" / "01-sentences"
    outdir.mkdir(parents=True, exist_ok=True)
    (outdir / "sentences.json").write_text(
        json.dumps(sentences, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
    )
    return sentences


def _compile(p: str) -> re.Pattern:
    return re.compile(p, re.IGNORECASE)


VERB_RES = {k: _compile(v) for k, v in VERB_PATTERNS.items()}
PARA_RES = {k: _compile(v) for k, v in PARA_PATTERNS.items()}


def _word_pat(name: str) -> re.Pattern:
    # 精确名: 词界匹配, 大小写不敏感 (verified 锚点)
    return re.compile(r"\b" + re.escape(name) + r"\b", re.IGNORECASE)


def _alias_pat(name: str) -> re.Pattern:
    # 别名归一: 复数/小写变体 (candidates)
    # 简单兜底: 尾加 s/es, 空格转 \s+ (沿 build_mentions 精度, 不用 \w*)
    parts = name.strip().split()
    if len(parts) > 1:
        pat = r"\b" + r"\s+".join(re.escape(p) for p in parts) + r"(?:s|es)?\b"
    else:
        w = parts[0]
        pat = r"\b" + re.escape(w) + r"(?:s|es)?\b"
    return re.compile(pat, re.IGNORECASE)


def step02(workdir: Path, sentences: list[dict]) -> dict:
    reg = json.loads((workdir / "inputs" / "registry-slice.json").read_text(encoding="utf-8"))
    names: list[str] = list(reg.get("weapons", [])) + list(reg.get("items", []))
    exact_res = {n: _word_pat(n) for n in names}
    alias_res = {n: _alias_pat(n) for n in names}

    verified: list[dict] = []
    candidates: list[dict] = []
    seen: set[tuple] = set()

    for s in sentences:
        sid = s["id"]
        text = s["text"]
        # 全动词出现位置 (就近归因: "buy these, ban white flag" 中 white flag 就近 ban, bag 就近 buy)
        _verb_occs: list[tuple[int, str]] = []
        for v, rx in VERB_RES.items():
            for m in rx.finditer(text):
                _verb_occs.append((m.start(), v))
        _para_occs: list[tuple[int, str]] = []
        for p, rx in PARA_RES.items():
            for m in rx.finditer(text):
                _para_occs.append((m.start(), p))
        # 本句闭集动词集合 (兼容旧逻辑, 实际归因用就近)
        closed_hits: list[str] = sorted({v for _, v in _verb_occs})
        # 本句 paraphrase 集合
        para_hits: list[str] = sorted({p for _, p in _para_occs})
        for n in names:
            m_exact = exact_res[n].search(text)
            m_alias = alias_res[n].search(text)
            if not m_exact and not m_alias:
                continue
            is_exact = bool(m_exact)
            # surface: 原文命中的词形 (alias 归一用)
            surf_m = m_exact if m_exact else m_alias
            surface_word = surf_m.group(0) if surf_m else n
            # 就近动词: 离物品提及最近的闭集动词 (避免同句多动词误标)
            _item_pos = surf_m.start() if surf_m else 0
            _closest = min(_verb_occs, key=lambda x: abs(x[0] - _item_pos)) if _verb_occs else None
            _closest_para = min(_para_occs, key=lambda x: abs(x[0] - _item_pos)) if _para_occs else None
            if closed_hits and is_exact:
                # verified: 就近闭集动词 (同句多动词取最近, 去重)
                assert _closest is not None
                verb = _closest[1]
                key = (sid, n, verb, "v")
                if key in seen:
                    continue
                seen.add(key)
                verified.append(
                    {"verb": verb, "object_norm": n, "sentence_id": sid, "quote": text}
                )
            elif closed_hits and not is_exact:
                # 别名 + 闭集动词 -> candidates (归一, 就近动词)
                assert _closest is not None
                verb = _closest[1]
                key = (sid, n, verb, "a")
                if key in seen:
                    continue
                seen.add(key)
                candidates.append(
                    {
                        "surface": surface_word,
                        "normalized_to": n,
                        "surface_verb": verb,
                        "mapped_to": verb,
                        "sentence_id": sid,
                        "quote": text,
                        "inferred": False,
                        "reason": f"别名归一（{surface_word}→{n}）+ 闭集动词 {verb}",
                    }
                )
            elif para_hits:
                # 动词转述 -> candidates (就近 paraphrase)
                assert _closest_para is not None
                surf_v = _closest_para[1]
                mapped = PARAPHRASE_MAP.get(surf_v, "skip" if surf_v in ("ignoring", "avoid", "avoiding") else "take")
                # 特殊: bought turret instead of -> skip
                if surf_v == "bought turret instead of":
                    mapped = "skip"
                key = (sid, n, surf_v, "p")
                if key in seen:
                    continue
                seen.add(key)
                candidates.append(
                    {
                        "surface": surface_word,
                        "normalized_to": n,
                        "surface_verb": surf_v,
                        "mapped_to": mapped,
                        "sentence_id": sid,
                        "quote": text,
                        "inferred": False,
                        "reason": f"别名归一（{surface_word}→{n}）+ 动词转述（{surf_v}→{mapped}）",
                    }
                )
            else:
                # 无动词: 意图推断候选 (inferred:true 仅高频/有拿语境, 余为路过但仍进 candidates 保 quote+reason)
                key = (sid, n, "none", "n")
                if key in seen:
                    continue
                seen.add(key)
                #  cap: 单件 quotes cap 10, 这里先全收, 分组时截断
                candidates.append(
                    {
                        "surface": surface_word,
                        "normalized_to": n,
                        "surface_verb": None,
                        "mapped_to": None,
                        "sentence_id": sid,
                        "quote": text,
                        "inferred": True,
                        "reason": f"无动词意图推断：提及 {n} 虽无闭集动词，结合语境算关注意图（inferred:true），待人点",
                    }
                )

    # quotes cap 10/件 (沿目录契约): 超出截断, 保留前 10
    from collections import defaultdict
    by_item: dict[str, list] = defaultdict(list)
    for r in verified + candidates:
        key = r.get("object_norm") or r.get("normalized_to")
        by_item[key].append(r)
    # 截断 candidates 超长 (verified 全留, candidates 按件 cap 10)
    cand_by_item: dict[str, list] = defaultdict(list)
    for c in candidates:
        cand_by_item[c["normalized_to"]].append(c)
    trimmed_candidates: list[dict] = []
    for k, lst in cand_by_item.items():
        trimmed_candidates.extend(lst[:10])
    # verified 不截 (通常 <10/件)

    verbs = {"verified": verified, "candidates": trimmed_candidates}
    outdir = workdir / "steps" / "02-verbs"
    outdir.mkdir(parents=True, exist_ok=True)
    (outdir / "verbs.json").write_text(
        json.dumps(verbs, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
    )
    return verbs


ZH_FALLBACK = {
    "Turret": "炮塔", "Pocket Factory": "口袋工厂", "Coffee": "咖啡",
    "Landmines": "地雷", "Boxing Glove": "拳套",
}


def _zh(name: str) -> str:
    return ZH_FALLBACK.get(name, name)


def step03(workdir: Path, verbs: dict) -> list[dict]:
    mentions_path = REPO / "data" / "mentions" / f"{workdir.parent.name}__{workdir.name}.json"
    # workdir = G:/brotato-work/<slug>/<variant>
    slug = workdir.parent.name
    vid = workdir.name
    mentions_path = REPO / "data" / "mentions" / f"{slug}__{vid}.json"
    mentions = json.loads(mentions_path.read_text(encoding="utf-8"))
    builds = json.loads((REPO / "data" / "builds" / f"{slug}.json").read_text(encoding="utf-8"))
    build_reasons: dict[str, str] = {}
    for v in builds.get("variants", []):
        if v.get("id") == vid:
            for it in v.get("items", []):
                build_reasons[it["name_en"]] = it.get("reason", "")

    # per-item verb 聚合
    from collections import defaultdict, Counter
    ver_by: dict[str, list] = defaultdict(list)
    for r in verbs.get("verified", []):
        ver_by[r["object_norm"]].append(r)
    cand_by: dict[str, list] = defaultdict(list)
    for r in verbs.get("candidates", []):
        cand_by[r["normalized_to"]].append(r)

    items_all = [(k, v["count"], v.get("quotes", [])) for k, v in mentions.get("items", {}).items() if v.get("count", 0) > 0]
    # weapons 也进分组? 试点只做道具三组 (items 68), 武器另表不进 groups.json
    grouping: list[dict] = []
    for name, count, quotes in sorted(items_all, key=lambda x: -x[1]):
        ver_list = ver_by.get(name, [])
        cand_list = cand_by.get(name, [])
        has_verb = bool(ver_list) or any((c.get("surface_verb") for c in cand_list))
        if ver_list:
            confidence = "verified"
            inferred = False
            verb = Counter(r["verb"] for r in ver_list).most_common(1)[0][0]
            verb_type = "closed"
            surf_v = verb
            mapped = verb
            surf_w = name
            disc = "机检锚点：精确英文名 + 闭集动词 + 原文整句引用"
        elif cand_list:
            # 首个有动词转述的优先, 否则 inferred
            with_verb = [c for c in cand_list if c.get("surface_verb")]
            if with_verb:
                c0 = with_verb[0]
                confidence = "candidate"
                inferred = False
                verb = c0.get("mapped_to")
                # verb_type: surface 是否闭集原形?
                sv = str(c0.get("surface_verb", ""))
                verb_type = "closed" if sv in CLOSED_VERBS else "mapped"
                surf_v = c0.get("surface_verb")
                mapped = c0.get("mapped_to")
                surf_w = c0.get("surface", name)
                disc = c0.get("reason", "")
            else:
                c0 = cand_list[0]
                confidence = "candidate"
                inferred = True
                verb = None
                verb_type = "none"
                surf_v = None
                mapped = None
                surf_w = c0.get("surface", name)
                disc = "无动词意图推断 (inferred:true)，待人点"
        else:
            # 无 verbs 记录 (不应发生, 兜底)
            confidence = "candidate"
            inferred = False
            has_verb = False
            verb = None
            verb_type = "none"
            surf_v = None
            mapped = None
            surf_w = name
            disc = "路过提及，无动词"

        # group/tier
        reason_build = build_reasons.get(name, "")
        if "【必拿·核心】" in reason_build:
            group, tier = "must_take", "core"
            reason = reason_build
        elif "【必拿·顺手】" in reason_build:
            group, tier = "must_take", "convenient"
            reason = reason_build
        elif "【提过未拿】" in reason_build:
            group, tier = "mentioned_not_taken", None
            reason = reason_build
        elif "【ban】" in reason_build or "【Ban】" in reason_build:
            group, tier = "ban", None
            reason = reason_build
        elif (any(r.get("verb") == "ban" for r in ver_list) or any(c.get("mapped_to") == "ban" for c in cand_list)) and name not in ("Glass Cannon",):
            # ban 证据: 任一 verified verb==ban 即 ban (Boxing Glove / White Flag / Defective Steroids 有 ban 原话).
            # Glass Cannon 真实字幕 6 句全为 take, 无 avoid, 按 take 进必拿 (誠实评价, 不硬 ban).
            group, tier = "ban", None
            # 优先用 ban 原话作 reason 引文; 展示动词统一为 ban (即使多数为 take, 如 Defective Steroids 有 take+ban 并存)
            _ban_q = next((r["quote"] for r in ver_list if r.get("verb") == "ban"), (ver_list + cand_list)[0]["quote"] if (ver_list + cand_list) else (quotes[0] if quotes else name))
            q0 = _ban_q[:60]
            reason = f"【ban】明确避开：高代价低适配，商店见即 ban；原话“{q0}…”"
            # 覆盖展示为 ban (誠实: 有 ban 原话即 ban)
            verb, verb_type, surf_v, mapped = "ban", "closed", "ban", "ban"
            confidence, inferred = "verified", False
            disc = "机检锚点：精确英文名 + 闭集动词 ban + 原文整句引用"
        elif verb in ("skip",) or (any("ignor" in str(c.get('surface_verb','')) for c in cand_list)):
            # 拒绝/跳过语境
            if count >= 4:
                group, tier = "mentioned_not_taken", None
                q0 = (ver_list + cand_list)[0]["quote"][:60] if (ver_list + cand_list) else (quotes[0][:60] if quotes else name)
                reason = f"【提过未拿】提到但没拿：与核心件竞争资源或收益有限；原话“{q0}…”"
            else:
                group, tier = "casual_mention", None
                reason = "【路过提及】商店刷新或路过提及，无明确评价，不影响构筑主线。"
        elif count >= 8:
            group, tier = "must_take", "convenient"
            q0 = (ver_list + cand_list)[0]["quote"][:60] if (ver_list + cand_list) else (quotes[0][:60] if quotes else name)
            # 妥协档: inferred 或特定件 (reason 禁计数泄漏, count 只活 JSON)
            if inferred or name in ("Mutation", "Focus"):
                tier = "compromise"
                reason = f"【必拿·妥协】没更好的才拿，矬子里拔将军；出处原话“{q0}…”"
            else:
                reason = f"【必拿·顺手】高频补益件，遇到且经济充裕时顺手补入；出处原话“{q0}…”"
        elif count >= 4:
            group, tier = "must_take", "convenient"
            q0 = (ver_list + cand_list)[0]["quote"][:60] if (ver_list + cand_list) else (quotes[0][:60] if quotes else name)
            reason = f"【必拿·顺手】中频补益件，遇到且经济充裕时顺手补入；出处原话“{q0}…”"
        else:
            group, tier = "casual_mention", None
            reason = "【路过提及】商店刷新或路过提及，无明确评价，不影响构筑主线。"

        # quotes: 去重 + cap 10
        seen_q: list[str] = []
        for q in quotes:
            if q not in seen_q:
                seen_q.append(q)
            if len(seen_q) >= 10:
                break
        grouping.append(
            {
                "name_en": name,
                "name_zh": _zh(name),
                "count": count,
                "group": group,
                "tier": tier,
                "confidence": confidence,
                "inferred": inferred,
                "has_verb": has_verb,
                "verb": verb,
                "verb_type": verb_type,
                "surface_verb": surf_v,
                "mapped_to": mapped,
                "surface_word": surf_w,
                "discretion_reason": disc,
                "reason": reason,
                "quotes": seen_q,
            }
        )

    outdir = workdir / "steps" / "03-grouping"
    outdir.mkdir(parents=True, exist_ok=True)
    (outdir / "grouping.json").write_text(
        json.dumps(grouping, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
    )
    # 晋升 outputs/groups.json
    outp = workdir / "outputs"
    outp.mkdir(parents=True, exist_ok=True)
    (outp / "groups.json").write_text(
        json.dumps(grouping, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
    )
    return grouping


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description="Pilot runner (#38)")
    ap.add_argument("--slug", default="cyborg")
    ap.add_argument("--variant", default="ultimate")
    ap.add_argument("--work-root", default="G:/brotato-work")
    ap.add_argument("--rpc", action="store_true", help="只打印 RPC 子进程命令, 不执行")
    args = ap.parse_args(argv)

    slug = args.slug
    vid = args.variant
    workdir = Path(args.work_root) / slug / vid

    if args.rpc:
        print(f'cd "{workdir}" && "F:/Pi/CLI/pi.cmd" --mode rpc --no-session '
              f"--no-skills --no-extensions --no-context-files --tools read,bash,write --thinking off")
        print("子 prompt 见 prompts/step01-sentences.md / step02-verbs.md / step03-grouping.md")
        return 0

    print(f"[pilot] workdir={workdir} (cwd 锁定, 只读写相对路径)")
    manifest = ensure_inputs(slug, vid, workdir)
    print(f"[pilot] inputs 四件落盘, sha1={manifest['sources'][0]['sha1'][:8]}...")
    sentences = step01(workdir)
    print(f"[pilot] 01-sentences: {len(sentences)} 句 -> steps/01-sentences/sentences.json")
    verbs = step02(workdir, sentences)
    print(f"[pilot] 02-verbs: verified={len(verbs['verified'])} candidates={len(verbs['candidates'])}")
    grouping = step03(workdir, verbs)
    from collections import Counter
    print(f"[pilot] 03-grouping: {len(grouping)} 件 -> steps/03-grouping/grouping.json + outputs/groups.json")
    print(f"[pilot] groups={dict(Counter((g['group'], g.get('tier')) for g in grouping))}")
    print("[pilot] done. 跑 check: python scripts/check_pilot.py --slug cyborg --variant ultimate")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
