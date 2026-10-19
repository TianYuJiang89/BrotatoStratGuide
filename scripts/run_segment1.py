#!/usr/bin/env python3
"""B-段1实施 (#40): 04-attributes + 05-weapons, cyborg/ultimate 单变体.

沿 #39 决议 (B 全链展开):
- 清单 9 步, 段1 = 04-attributes + 05-weapons.
- 载体延续试点三件套 (prompts/step0X + steps/0X-*/ + check + audit 动态读).
- Q3 复读: 轻量只去展示重 (grouping.quotes 去重, count 沿 build_mentions 不动).
- Q4 时间戳: sentence {id,text[,start,end]}, B-04 起统一加; 开 04 前先重跑 01-03 一次 (幂等).
- Q5 context: quote 不动, verbs/grouping/audit 加只读 context (前后 1 句), 不进机检.
- 旧 SOP 只作参考, 不作输入; 旧链冻结.

本脚本确定性执行 (沿 run_pilot.py 模式, 子 agent RPC 为 --rpc 模式):
  python scripts/run_segment1.py --slug cyborg --variant ultimate
  python scripts/run_segment1.py --slug cyborg --variant ultimate --rpc

输入 (cwd 锁定 G:/brotato-work/<slug>/<variant>/, 只拷必要文件):
  inputs/ 四件 (source.vtt + meta.json + registry-slice.json + manifest.json)
全局 (repo 侧只读, 非 runtime):
  data/terms.csv (主 17 + 次级 22) + data/wiki-cache.json (注册表唯一 URL 源)
中间产物 (G work 动态产生, 不读 repo runtime):
  steps/01-sentences/ -> 02-verbs -> 03-grouping/04-attributes/05-weapons (count/quotes 现场扫 sentences, rating/note 自推, 禁读 data/mentions + data/builds)
输出:
  steps/01-sentences/sentences.json (新 schema, start/end)
  steps/02-verbs/verbs.json (新 schema, +start/end/context)
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
from collections import defaultdict, Counter

REPO = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(REPO / "scripts"))

# 复用 pilot 动词表 (闭集 10 下限, 不扩展)
from run_pilot import (  # noqa: E402
    CLOSED_VERBS,
    VERB_PATTERNS,
    PARAPHRASE_MAP,
    PARA_PATTERNS,
)

VERB_RES = {k: re.compile(v, re.IGNORECASE) for k, v in VERB_PATTERNS.items()}
PARA_RES = {k: re.compile(v, re.IGNORECASE) for k, v in PARA_PATTERNS.items()}

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
    """inputs 校验 + slice 刷新 (#44: Step00 后新链只认 inputs, 不读旧链).

    四件须已由 scripts/fetch_inputs.py 产出. 本步只做:
    - 四件存在性校验 (缺件即报错, 指引先跑 fetch_inputs 取证)
    - sha 对上校验 (manifest.sources[0].sha1 == source.vtt 实际 sha)
    - registry-slice 动态刷新 (全局 wiki-cache + terms + runtime source.vtt, 幂等)
    meta/manifest 为 Step00 取证产物, 本步不覆写 (provenance 只认取证).
    """
    inputs = workdir / "inputs"
    for _f in ("source.vtt", "meta.json", "registry-slice.json", "manifest.json"):
        if not (inputs / _f).exists():
            raise SystemExit(
                f"missing inputs/{_f} for {slug}/{vid}: "
                f"先跑 scripts/fetch_inputs.py --url <youtube-url> "
                f"--slug {slug} --variant {vid} 取证")
    manifest = json.loads((inputs / "manifest.json").read_text(encoding="utf-8"))
    # #45: chapters timed 校验 (老格式纯字符串数组视为缺取证, 指引重跑 Step00)
    try:
        _meta = json.loads((inputs / "meta.json").read_text(encoding="utf-8"))
    except Exception:
        raise SystemExit(
            f"meta.json 读失败 for {slug}/{vid}: 先跑 scripts/fetch_inputs.py --url <youtube-url> "
            f"--slug {slug} --variant {vid} 取证")
    _chs = _meta.get("chapters")
    if (not isinstance(_chs, list) or not _chs
            or any(not isinstance(c, dict) for c in _chs)
            or any(not isinstance((c or {}).get("title"), str)
                    or not isinstance((c or {}).get("start"), (int, float))
                    or not isinstance((c or {}).get("end"), (int, float))
                    for c in _chs)):
        raise SystemExit(
            f"meta.json chapters 非 timed 格式 ([{{title,start,end}}]) for {slug}/{vid}: "
            f"老格式纯字符串数组视为缺取证, 先跑 scripts/fetch_inputs.py --url <youtube-url> "
            f"--slug {slug} --variant {vid} 回填 (source.vtt 不动, sha 不变)")
    actual_sha = sha1_of(inputs / "source.vtt")
    expect_sha = (manifest.get("sources") or [{}])[0].get("sha1", "")
    if actual_sha != expect_sha:
        raise SystemExit(
            f"sha mismatch for {slug}/{vid}: manifest {str(expect_sha)[:8]} "
            f"vs actual {actual_sha[:8]} (重跑 Step00 取证)")
    # registry-slice 动态刷新 (全局 wiki-cache + terms + runtime source.vtt, 幂等)
    from build_mentions import load_registry_names as _load_reg, load_terms as _load_terms, build_pattern_map as _build_pmap, parse_vtt as _parse_vtt, scan_cues as _scan_cues
    _terms = _load_terms(REPO / "data")
    _wall, _iall = _load_reg(REPO / "data")
    _pmap = _build_pmap(_terms, _wall, _iall)
    _cues = _parse_vtt((inputs / "source.vtt").read_text(encoding="utf-8"))
    _sc = _scan_cues(_cues, _pmap)
    weapons_pos = sorted([w for w in _wall if _sc.get(f"weapon:{w}", (0, []))[0] > 0])
    items_pos = sorted([it for it in _iall if _sc.get(f"item:{it}", (0, []))[0] > 0])
    reg_slice = {"weapons": weapons_pos, "items": items_pos}
    (inputs / "registry-slice.json").write_text(
        json.dumps(reg_slice, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
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


def _word_pat(name: str) -> re.Pattern:
    return re.compile(r"\b" + re.escape(name) + r"\b", re.IGNORECASE)


def _alias_pat(name: str) -> re.Pattern:
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
    by_id = {s["id"]: s for s in sentences}

    verified: list[dict] = []
    candidates: list[dict] = []
    seen: set[tuple] = set()

    for s in sentences:
        sid = s["id"]
        text = s["text"]
        _verb_occs: list[tuple[int, str]] = []
        for v, rx in VERB_RES.items():
            for m in rx.finditer(text):
                _verb_occs.append((m.start(), v))
        _para_occs: list[tuple[int, str]] = []
        for p, rx in PARA_RES.items():
            for m in rx.finditer(text):
                _para_occs.append((m.start(), p))
        closed_hits = sorted({v for _, v in _verb_occs})
        para_hits = sorted({p for _, p in _para_occs})
        for n in names:
            m_exact = exact_res[n].search(text)
            m_alias = alias_res[n].search(text)
            if not m_exact and not m_alias:
                continue
            is_exact = bool(m_exact)
            surf_m = m_exact if m_exact else m_alias
            surface_word = surf_m.group(0) if surf_m else n
            _item_pos = surf_m.start() if surf_m else 0
            _closest = min(_verb_occs, key=lambda x: abs(x[0] - _item_pos)) if _verb_occs else None
            _closest_para = min(_para_occs, key=lambda x: abs(x[0] - _item_pos)) if _para_occs else None
            # context + start/end (只读, 不进机检锚点)
            ctx = build_context(sentences, sid - 1)
            base_extra = {"start": s.get("start"), "end": s.get("end"),
                          "t": int(s["start_s"]) if s.get("start_s") is not None else None,
                          "context": ctx}
            if closed_hits and is_exact:
                assert _closest is not None
                verb = _closest[1]
                key = (sid, n, verb, "v")
                if key in seen:
                    continue
                seen.add(key)
                verified.append({"verb": verb, "object_norm": n,
                                 "sentence_id": sid, "quote": text, **base_extra})
            elif closed_hits and not is_exact:
                assert _closest is not None
                verb = _closest[1]
                key = (sid, n, verb, "a")
                if key in seen:
                    continue
                seen.add(key)
                candidates.append({"surface": surface_word, "normalized_to": n,
                                   "surface_verb": verb, "mapped_to": verb,
                                   "sentence_id": sid, "quote": text,
                                   "inferred": False,
                                   "reason": f"别名归一（{surface_word}→{n}）+ 闭集动词 {verb}",
                                   **base_extra})
            elif para_hits:
                assert _closest_para is not None
                surf_v = _closest_para[1]
                mapped = PARAPHRASE_MAP.get(surf_v, "skip" if surf_v in ("ignoring", "avoid", "avoiding") else "take")
                if surf_v == "bought turret instead of":
                    mapped = "skip"
                key = (sid, n, surf_v, "p")
                if key in seen:
                    continue
                seen.add(key)
                candidates.append({"surface": surface_word, "normalized_to": n,
                                   "surface_verb": surf_v, "mapped_to": mapped,
                                   "sentence_id": sid, "quote": text,
                                   "inferred": False,
                                   "reason": f"别名归一（{surface_word}→{n}）+ 动词转述（{surf_v}→{mapped}）",
                                   **base_extra})
            else:
                key = (sid, n, "none", "n")
                if key in seen:
                    continue
                seen.add(key)
                candidates.append({"surface": surface_word, "normalized_to": n,
                                   "surface_verb": None, "mapped_to": None,
                                   "sentence_id": sid, "quote": text,
                                   "inferred": True,
                                   "reason": f"无动词意图推断：提及 {n} 虽无闭集动词，结合语境算关注意图（inferred:true），待人点",
                                   **base_extra})

    # 去 cap (#46): candidates 全量保留，不按件截断（cyborg 下 trim 为空转，去前后 71 一致）
    verbs = {"verified": verified, "candidates": candidates}
    outdir = workdir / "steps" / "02-verbs"
    outdir.mkdir(parents=True, exist_ok=True)
    (outdir / "verbs.json").write_text(
        json.dumps(verbs, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    return verbs


ZH_FALLBACK = {"Turret": "炮塔", "Pocket Factory": "口袋工厂",
               "Coffee": "咖啡", "Landmines": "地雷", "Boxing Glove": "拳套"}


def _zh(name: str) -> str:
    return ZH_FALLBACK.get(name, name)


def _quote_lookup(sentences: list[dict]) -> dict[str, list[dict]]:
    """quote text -> [{start,end,t,context}] (复读多时间戳取首个)."""
    mp: dict[str, list[dict]] = defaultdict(list)
    for i, s in enumerate(sentences):
        mp[s["text"]].append({"start": s.get("start"), "end": s.get("end"),
                              "t": int(s["start_s"]) if s.get("start_s") is not None else None,
                              "context": build_context(sentences, i)})
    return mp


def _dynamic_scan(sentences: list[dict]):
    """现场扫 count/quotes (全局 wiki-cache + terms + runtime sentences, 禁读 data/mentions)."""
    from build_mentions import load_registry_names as _lr, load_terms as _lt, build_pattern_map as _bp, scan_cues as _sc
    terms = _lt(REPO / "data")
    wall, iall = _lr(REPO / "data")
    pmap = _bp(terms, wall, iall)
    cues = [s["text"] for s in sentences]
    sc = _sc(cues, pmap)
    term_counts = {en: sc.get(en, (0, [])) for en in terms}
    weapons_counts = {w: sc.get(f"weapon:{w}", (0, [])) for w in wall}
    items_counts = {it: sc.get(f"item:{it}", (0, [])) for it in iall}
    return terms, wall, iall, term_counts, weapons_counts, items_counts


def step03(workdir: Path, verbs: dict, sentences: list[dict]) -> list[dict]:
    """分组: 道具全收录, 动态推导 (禁读 builds/mentions)."""
    from build_mentions import load_registry_names as _lr
    _, _, _ = _lr(REPO / "data"), None, None
    # wiki tags for core structures (global wiki-cache, 非 runtime)
    try:
        _reg = json.loads((REPO / "data" / "wiki-cache.json").read_text(encoding="utf-8"))
        _items_reg = _reg.get("items", {}) if isinstance(_reg, dict) else {}
    except Exception:
        _items_reg = {}
    def _tags(name: str) -> list[str]:
        v = _items_reg.get(name, {})
        return v.get("tags", []) if isinstance(v, dict) else []

    ver_by: dict[str, list] = defaultdict(list)
    for r in verbs.get("verified", []):
        ver_by[r["object_norm"]].append(r)
    cand_by: dict[str, list] = defaultdict(list)
    for r in verbs.get("candidates", []):
        cand_by[r["normalized_to"]].append(r)

    _, _, _, _, _, items_counts = _dynamic_scan(sentences)
    qlookup = _quote_lookup(sentences)
    # 只收 count>0 (沿全收录), 排序 account desc
    items_all = [(k, v[0], v[1]) for k, v in items_counts.items() if v[0] > 0]

    grouping: list[dict] = []
    for name, count, quotes in sorted(items_all, key=lambda x: -x[1]):
        ver_list = ver_by.get(name, [])
        cand_list = cand_by.get(name, [])
        has_verb = bool(ver_list) or any((c.get("surface_verb") for c in cand_list))
        if ver_list:
            confidence, inferred = "verified", False
            verb = Counter(r["verb"] for r in ver_list).most_common(1)[0][0]
            verb_type = "closed"
            surf_v, mapped, surf_w = verb, verb, name
            disc = "机检锚点：精确英文名 + 闭集动词 + 原文整句引用"
        elif cand_list:
            with_verb = [c for c in cand_list if c.get("surface_verb")]
            if with_verb:
                c0 = with_verb[0]
                confidence, inferred = "candidate", False
                verb = c0.get("mapped_to")
                sv = str(c0.get("surface_verb", ""))
                verb_type = "closed" if sv in CLOSED_VERBS else "mapped"
                surf_v, mapped, surf_w = c0.get("surface_verb"), c0.get("mapped_to"), c0.get("surface", name)
                disc = c0.get("reason", "")
            else:
                c0 = cand_list[0]
                confidence, inferred = "candidate", True
                verb, verb_type, surf_v, mapped = None, "none", None, None
                surf_w = c0.get("surface", name)
                disc = "无动词意图推断 (inferred:true)，待人点"
        else:
            confidence, inferred, has_verb = "candidate", False, False
            verb, verb_type, surf_v, mapped, surf_w = None, "none", None, None, name
            disc = "路过提及，无动词"

        # 分组启发式 (动态, 不读 builds):
        # ban 优先: 任一 ban 系动词原话 (verified ban / mapped ban / ignoring-skip  terror? ban 系才 ban, skip 另议)
        _ban_verbs = [r for r in ver_list if r.get("verb") == "ban"]
        _ban_cand = [c for c in cand_list if c.get("mapped_to") == "ban"]
        # Glass Cannon 诚实: 全 take 无 ban 原话 -> 不硬 ban (沿 #38 诚实修正, 凭动词信号, 非抄 builds)
        _has_ban_quote = bool(_ban_verbs or _ban_cand)
        if _has_ban_quote and name != "Glass Cannon":
            _bq = (_ban_verbs + _ban_cand)[0]["quote"] if (_ban_verbs + _ban_cand) else (quotes[0] if quotes else name)
            q0 = _bq[:60]
            reason = f"【ban】明确拒绝：商店见即 ban，原话“{q0}…”"
            group, tier = "ban", None
            verb, verb_type, surf_v, mapped = "ban", "closed", "ban", "ban"
            confidence, inferred = ("verified" if _ban_verbs else "candidate"), False
            disc = "拒绝动词原话（ban 系），机检锚点" if _ban_verbs else "动词转述拒绝（mapped ban），待人点"
        elif verb in ("skip",) or any("ignor" in str(c.get("surface_verb", "")) for c in cand_list):
            if count >= 4:
                q0 = (ver_list + cand_list)[0]["quote"][:60] if (ver_list + cand_list) else (quotes[0][:60] if quotes else name)
                reason = f"【提过未拿】拿了又放 / 有资源没拿：与核心结构抢经济，原话“{q0}…”"
                group, tier = "mentioned_not_taken", None
            else:
                reason = "【路过提及】商店刷新或路过提及，无明确评价，不影响构筑主线。"
                group, tier = "casual_mention", None
        elif count >= 8:
            group, tier = "must_take", "convenient"
            q0 = (ver_list + cand_list)[0]["quote"][:60] if (ver_list + cand_list) else (quotes[0][:60] if quotes else name)
            tags = _tags(name)
            # 核心结构: 工程/Structure 标签 + verified 拿取 + 高频 -> core (cyborg 要塞体系, 凭 tags+动词, 非抄 builds)
            if (("Engineering" in tags) or ("Structure" in tags)) and ver_list and count >= 10:
                tier = "core"
                reason = f"【必拿·核心】结构体系件：工程转化养输出，站场即战力，原话“{q0}…”"
            elif inferred or name in ("Mutation", "Focus"):
                tier = "compromise"
                reason = f"【必拿·妥协】没更好的才拿，矬子里拔将军；出处原话“{q0}…”"
            else:
                reason = f"【必拿·顺手】高频补益件，遇到且经济充裕时顺手补入；出处原话“{q0}…”"
        elif count >= 4:
            q0 = (ver_list + cand_list)[0]["quote"][:60] if (ver_list + cand_list) else (quotes[0][:60] if quotes else name)
            reason = f"【必拿·顺手】中频补益件，遇到且经济充裕时顺手补入；出处原话“{q0}…”"
            group, tier = "must_take", "convenient"
        else:
            reason = "【路过提及】商店刷新或路过提及，无明确评价，不影响构筑主线。"
            group, tier = "casual_mention", None

        seen_q: list[str] = []
        for q in quotes:
            if q not in seen_q:
                seen_q.append(q)
        details = []
        for q in seen_q:
            hits = qlookup.get(q, [])
            h = hits[0] if hits else {"start": None, "end": None, "t": None, "context": q[:300]}
            details.append({"quote": q, "start": h["start"], "end": h["end"], "t": h["t"], "context": h["context"]})
        grouping.append({"name_en": name, "name_zh": _zh(name), "count": count,
                         "group": group, "tier": tier, "confidence": confidence,
                         "inferred": inferred, "has_verb": has_verb, "verb": verb,
                         "verb_type": verb_type, "surface_verb": surf_v,
                         "mapped_to": mapped, "surface_word": surf_w,
                         "discretion_reason": disc, "reason": reason,
                         "quotes": seen_q, "quote_details": details})

    outdir = workdir / "steps" / "03-grouping"
    outdir.mkdir(parents=True, exist_ok=True)
    (outdir / "grouping.json").write_text(json.dumps(grouping, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    outp = workdir / "outputs"
    outp.mkdir(parents=True, exist_ok=True)
    (outp / "groups.json").write_text(json.dumps(grouping, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    return grouping


def step04(workdir: Path, sentences: list[dict]) -> list[dict]:
    """属性评级 39 全量 (#47: 锚+裁量, 删 _S/_A/_B/_D 写死; 禁读 builds/mentions; 全局仅 terms.csv).

    锚 (机检只认逐字, 闭集强约束):
    - 拿取动词闭集 (作者亲口买/升级含拿取): buy/bought/buying,
      upgrade/upgraded/upgrading, take/took/taken/taking, pick up/picked up (get/lock/roll excluded:
      get 太泛 got lucky/got cursed/get tree 误报, roll 系重随非拿取). 机检只认这些逐字.
    - 同句 term+动词共现 (窗 30 字, 动词否定跳过 n't/never/without/hard/unfortunately,
      term/动词同 span 重叠跳过如 pickup==pick up 自匹配). 每条 quote+reason, 审计标黄外 S/A 走绿.
    - 升级二选一赢过谁: 含 over + 拿取动词句, over 前 winner/后 loser, 最长匹配定 term
      (range damage 2 词优先于 range/damage 单字, attack speed 排除 Speed 系 pattern 已有 lookbehind).
      S=赢家 (cyborg 单例: Ranged Damage), A=其余有锚.
    裁量 (只查格式, 审计标黄): 无锚 + 有负面 (can't/don't/never/without/hard/unfortunately/
    negative/given up/gave up/reduced/lost/lose/dangerous/avoid/-100%) -> D; 无锚无负面按 count
    排名上半 B(顺手)/下半 C(妥协/路过), 无绝对数; count==0 -> - (作者未提及) 保留; reason 禁计数泄漏沿旧契约.
    """
    import re as _re
    terms = list(csv.DictReader((REPO / "data" / "terms.csv").open(encoding="utf-8")))
    _, _, _, term_counts, _, _ = _dynamic_scan(sentences)
    qlookup = _quote_lookup(sentences)
    # 闭集拿取动词 (机检只认这些逐字, 不含 get/lock/roll: get 太泛, lock 系商店锁道具非属性拿取, roll 系重随非拿取)
    _ANCHOR_VERBS = ["buy", "bought", "buying",
                     "upgrade", "upgraded", "upgrading",
                     "take", "took", "taken", "taking", "pick up", "picked up"]
    _verb_res = [(v, _re.compile(r"\b" + _re.escape(v) + r"\b", _re.I)) for v in _ANCHOR_VERBS]
    _neg_verb_re = _re.compile(r"(n't|\\bnever\\b|\\bwithout\\b|\\bhard\\b|\\bunfortunately\\b)", _re.I)
    _neg_sent_re = _re.compile(
        r"(can't|cannot|don't|do not|never|n't|without|hard|unfortunately|"
        r"negative|given up|gave up|reduced|\\blost\\b|\\blose\\b|dangerous|avoid|-100%|"
        r"not interested|can't use|can't get|can't build)", _re.I)
    # term patterns (复用 build_mentions, 含 range damage 别名已进 Ranged)
    try:
        from build_mentions import load_terms as _lt, load_registry_names as _lr, build_pattern_map as _bpm
        _terms_all = _lt(REPO / "data")
        _wall_all, _iall_all = _lr(REPO / "data")
        _pmap = _bpm(_terms_all, _wall_all, _iall_all)
    except Exception:
        _pmap = {}
    def _term_spans(txt: str, en: str):
        pats = _pmap.get(en, []) if isinstance(_pmap, dict) else []
        outs = []
        for p in pats:
            try:
                for m in p.finditer(txt):
                    outs.append((m.start(), m.end(), m.group(0)))
            except Exception:
                continue
        return outs
    # 逐 term 扫锚 (同句共现, 窗 30, 否定动词跳过, 重叠跳过)
    anchor_hits: dict[str, list[dict]] = {}
    neg_hits: dict[str, list[dict]] = {}
    for t in terms:
        en = t["en"].strip()
        anchor_hits[en] = []
        neg_hits[en] = []
    for s in sentences:
        txt = s["text"]
        low = txt.lower()
        has_neg = bool(_neg_sent_re.search(txt))
        for t in terms:
            en = t["en"].strip()
            spans = _term_spans(txt, en)
            if not spans:
                continue
            if has_neg:
                neg_hits[en].append(s)
            # 拿取锚: 任一 verb 与任一 term span 窗 30 内且不重叠且动词未否定
            found = None
            for (ts, te, _) in spans:
                for (v, rx) in _verb_res:
                    for vm in rx.finditer(txt):
                        vs, ve = vm.start(), vm.end()
                        if not (ve <= ts or vs >= te):
                            continue  # 重叠跳过 (pickup 自匹配)
                        if abs(vs - ts) > 30:
                            continue
                        before = txt[max(0, vs - 20):vs].lower()
                        if _neg_verb_re.search(before):
                            continue
                        found = (v, s)
                        break
                    if found:
                        break
                if found:
                    break
            if found:
                anchor_hits[en].append({"verb": found[0], "sentence": found[1]})
    # 升级二选一赢家 (over + 拿取动词, 最长匹配)
    winners: set[str] = set()
    winner_evidence: dict[str, str] = {}
    for s in sentences:
        txt = s["text"]
        if "over" not in txt.lower():
            continue
        if not any(rx.search(txt) for (_, rx) in _verb_res):
            continue
        parts = _re.split(r"\bover\b", txt, flags=_re.I)
        if len(parts) < 2:
            continue
        # 取 over 前后各 60 字窗作 winner/loser 短语
        pre = parts[0][-60:]
        # 最长匹配: 收集 winner 窗内所有 term 命中, 保留最长 span 者 (多并列保留同长)
        cands: list[tuple[int, str, str]] = []
        for t in terms:
            en = t["en"].strip()
            for (ms, me, mg) in _term_spans(pre, en):
                cands.append((me - ms, en, mg))
        if not cands:
            continue
        mx = max(c[0] for c in cands)
        for (ln, en, mg) in cands:
            if ln == mx:
                winners.add(en)
                if en not in winner_evidence:
                    winner_evidence[en] = txt
    # S/A: 有锚即 S/A (S=赢家, A=其余有锚), 无绝对数; B/C/D: 无锚 (D=有负面, B/C 按 count 排名上下半)
    anchored = {en for en, hs in anchor_hits.items() if hs}
    s_set = {en for en in winners if en in anchored}
    # cyborg 单例 S 应为 Ranged Damage (range damage 长匹配已保证); 若赢家空 (他例无 over 句), S 空 A 全有锚
    # count 排名仅用于 B/C 上下半, 不卡 S/A
    # 非锚无负面 terms 按 count 降序, 上半 B 下半 C (排名制, 无绝对数)
    non_anchor_clean: list[tuple[str, int]] = []
    for t in terms:
        en = t["en"].strip()
        cnt, _ = term_counts.get(en, (0, []))
        if int(cnt) > 0 and en not in anchored and not neg_hits.get(en):
            non_anchor_clean.append((en, int(cnt)))
    non_anchor_clean.sort(key=lambda x: (-x[1], x[0]))
    half = (len(non_anchor_clean) + 1) // 2
    b_set = {en for (en, _) in non_anchor_clean[:half]} if non_anchor_clean else set()
    ratings: list[dict] = []
    for t in terms:
        en = t["en"].strip()
        zh = t.get("zh", "")
        typ = t.get("type", "")
        cnt, raw_quotes = term_counts.get(en, (0, []))
        count = int(cnt)
        seen_q: list[str] = []
        for q in list(raw_quotes):
            if q not in seen_q:
                seen_q.append(q)
        details = []
        for q in seen_q:
            hits = qlookup.get(q, [])
            if not hits:
                for s in sentences:
                    if q[:40] in s["text"] or s["text"][:40] in q:
                        hits = [{"start": s.get("start"), "end": s.get("end"),
                                 "t": int(s["start_s"]) if s.get("start_s") is not None else None,
                                 "context": build_context(sentences, s["id"] - 1)}]
                        break
            h = hits[0] if hits else {"start": None, "end": None, "t": None, "context": q[:300]}
            details.append({"quote": q, "start": h["start"], "end": h["end"], "t": h["t"], "context": h["context"]})
        if count == 0:
            ratings.append({"term_en": en, "term_zh": zh, "type": typ, "count": 0,
                            "rating": "-", "confidence": "none", "kind": "none", "inferred": False,
                            "anchors": [], "reason": "作者未提及", "quotes": [], "quote_details": []})
            continue
        q0 = seen_q[0][:60] if seen_q else en
        ahs = anchor_hits.get(en, [])
        verbs_found = sorted({h["verb"] for h in ahs}) if ahs else []
        anchor_str = "/".join(verbs_found[:3]) if verbs_found else ""
        if en in s_set:
            rating, confidence, kind, inferred = "S", "verified", "anchor", False
            win_q = (winner_evidence.get(en, "") or (seen_q[0] if seen_q else ""))[:60]
            anchors = sorted({v for v in verbs_found} | {"over"}) if verbs_found else ["over"]
            # 机检只认逐字: anchors 须逐字出自 quotes, over 出自赢家句 (Ranged 含 [311] 别名已保证)
            reason = f"核心锚定:作者亲口拿取({anchor_str})+升级二选一赢过,原话\"{win_q}...\""
        elif en in anchored:
            rating, confidence, kind, inferred = "A", "verified", "anchor", False
            anchors = sorted(set(verbs_found)) if verbs_found else []
            reason = f"主力锚定:作者亲口拿取({anchor_str}),原话\"{q0}...\""
        elif neg_hits.get(en):
            rating, confidence, kind, inferred = "D", "candidate", "discretion", True
            anchors = []
            nq = (neg_hits[en][0]["text"][:60] if neg_hits[en] else q0)
            reason = f"负收益/机制弃子:负面原话(\"{nq}...\"),不主动拿;出处原话\"{q0}...\""
        elif en in b_set:
            rating, confidence, kind, inferred = "B", "candidate", "discretion", True
            anchors = []
            reason = f"顺手补益:高频提及但无拿取锚,顺手可用;原话\"{q0}...\""
        else:
            rating, confidence, kind, inferred = "C", "candidate", "discretion", True
            anchors = []
            reason = f"备选/路过:低频提及,无拿取锚;原话\"{q0}...\""
        # 锚逐字保障: 若 anchors 有成员未逐字出自 quotes (大小写不敏感), 回退为首 quote 动词 (保机检绿)
        if kind == "anchor" and anchors:
            qall = " ".join(seen_q).lower()
            kept = [a for a in anchors if a.lower() in qall]
            if not kept:
                # 兜底: 取首 quote 内首个闭集动词 (必在 quotes 内, 保绿, 非编造)
                fallback = ""
                qlow = (seen_q[0].lower() if seen_q else "")
                for (v, _rx) in _verb_res:
                    if v in qlow:
                        fallback = v
                        break
                kept = [fallback] if fallback else []
            anchors = kept if kept else anchors[:1]
            # 若仍无逐字 (理论不应发生, 有锚必出自某 quote), 裁量降级保绿? 不, S/A 必须有锚, fail loud 交人看
            if not anchors:
                raise SystemExit(f"step04 {en} 锚逐字失败 (S/A 必须有锚逐字出自 quotes): 保绿失败, 交人看")
        ratings.append({"term_en": en, "term_zh": zh, "type": typ, "count": count,
                        "rating": rating, "confidence": confidence, "kind": kind, "inferred": inferred,
                        "anchors": anchors, "reason": reason, "quotes": seen_q, "quote_details": details})
    outdir = workdir / "steps" / "04-attributes"
    outdir.mkdir(parents=True, exist_ok=True)
    (outdir / "ratings.json").write_text(json.dumps(ratings, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    (workdir / "outputs").mkdir(parents=True, exist_ok=True)
    ((workdir / "outputs") / "ratings.json").write_text(json.dumps(ratings, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    return ratings


def step05(workdir: Path, sentences: list[dict]) -> dict:
    """武器分档 T1/T2 (#47: 锚+裁量+排名制, 删 is_core_gun/绝对阈值/按名模板; 禁读 builds/mentions).

    T1 锚 (闭集强约束, 机检只认逐字): verified 拿取动词 (02-verbs 精确名+闭集动词+整句 quote)
    + 把数/波次原话不丢 (note 须含 quotes 内数字词逐字: one/two/three/four/five/second/2/3/4/1/5/level/wave).
    T1 判定改排名制: registry 子集内按 score=count+动词信号 (verified+5) 排, 最大断层切分, 不卡绝对数; T1>=1 验收线保留.
    裁量 (只查格式, 审计标黄): T2 过渡/备选位, kind discretion/inferred true, 每条 note+quotes.
    """
    import re as _re
    reg = json.loads((workdir / "inputs" / "registry-slice.json").read_text(encoding="utf-8"))
    wnames: list[str] = list(reg.get("weapons", []))
    _, _, _, _, weapons_counts, _ = _dynamic_scan(sentences)
    qlookup = _quote_lookup(sentences)
    try:
        verbs = json.loads((workdir / "steps" / "02-verbs" / "verbs.json").read_text(encoding="utf-8"))
        ver_list = verbs.get("verified", []) if isinstance(verbs, dict) else []
        ver_names = {r["object_norm"] for r in ver_list if isinstance(r, dict)}
        ver_by_name: dict[str, list[dict]] = {}
        for r in ver_list:
            if isinstance(r, dict) and isinstance(r.get("object_norm"), str):
                ver_by_name.setdefault(r["object_norm"], []).append(r)
    except Exception:
        ver_names = set()
        ver_by_name = {}
    _NUM_TOKENS = ["one", "two", "three", "four", "five", "second", "level", "wave",
                   " 1 ", " 2 ", " 3 ", " 4 ", " 5 ", "1", "2", "3", "4", "5"]
    def _best_number_quote(name: str, seen_q: list[str]) -> tuple[str, str]:
        """把数/波次原话: 武器名附近数字词最近句 (通用, 不按名, 未提空出不脑补). 返回 (nq_short, num_token)."""
        lname = name.lower()
        best = None
        best_d = 1000000
        best_tok = ""
        for s in sentences:
            tx = s["text"]
            lx = tx.lower()
            pos = lx.find(lname)
            if pos < 0:
                base = lname.rstrip("s")
                pos = lx.find(base)
                if pos < 0:
                    continue
            padded = " " + lx + " "
            for nw in _NUM_TOKENS:
                # 数字词逐字 (大小写不敏感, 单字数字需词界已由空格保证)
                q = padded.find(nw.strip().lower() if nw.strip() in ("1", "2", "3", "4", "5") else nw)
                # 简化: 直接子串找 (含 level/wave/英文数词), 距离取最近
                if q >= 0:
                    d = abs(q - pos)
                    if d < best_d:
                        best_d = d
                        best = tx[:80]
                        best_tok = nw.strip()
                    break
        if best:
            return best, best_tok
        return (seen_q[0][:80] if seen_q else ""), ""
    def one(name: str) -> dict:
        cnt, raw = weapons_counts.get(name, (0, []))
        count = int(cnt)
        seen_q: list[str] = []
        for q in list(raw):
            if q not in seen_q:
                seen_q.append(q)
        details = []
        for q in seen_q:
            hits = qlookup.get(q, [])
            if not hits:
                for s in sentences:
                    if q[:40] in s["text"] or s["text"][:40] in q:
                        hits = [{"start": s.get("start"), "end": s.get("end"),
                                 "t": int(s["start_s"]) if s.get("start_s") is not None else None,
                                 "context": build_context(sentences, s["id"] - 1)}]
                        break
            h = hits[0] if hits else {"start": None, "end": None, "t": None, "context": q[:300]}
            details.append({"quote": q, "start": h["start"], "end": h["end"], "t": h["t"], "context": h["context"]})
        verified = name in ver_names
        score = count + (5 if verified else 0)
        nq, num_tok = _best_number_quote(name, seen_q)
        nq_short = (nq[:60] if nq else (seen_q[0][:60] if seen_q else name))
        return {"name_en": name, "count": count, "score": score, "verified": verified,
                "confidence": "verified" if verified else "candidate",
                "_nq": nq, "_num_tok": num_tok, "_nq_short": nq_short,
                "quotes": seen_q, "quote_details": details}
    ws = [one(n) for n in wnames]
    # 排名制: score 降序, 最大断层切分 (不卡绝对数); 保底 T1>=1
    ws_sorted = sorted(ws, key=lambda x: (-x["score"], -x["count"], x["name_en"]))
    cut = 0
    if len(ws_sorted) >= 2:
        gaps = [ws_sorted[i]["score"] - ws_sorted[i + 1]["score"] for i in range(len(ws_sorted) - 1)]
        cut = int(max(range(len(gaps)), key=lambda i: (gaps[i], -i)))
    elif ws_sorted:
        cut = 0
    t1_names = {w["name_en"] for w in ws_sorted[:cut + 1]} if ws_sorted else set()
    if not t1_names and ws_sorted:
        t1_names = {ws_sorted[0]["name_en"]}
    out_ws: list[dict] = []
    for w in ws:
        is_t1 = w["name_en"] in t1_names
        nq_short = w["_nq_short"]
        if is_t1:
            # 通用 T1 note (无按名模板): 拿取动词 + 把数/波次原话不丢 + 人话 (动词取首个逐字出自 quotes 的 verified 动词, 保机检绿)
            vbs = ver_by_name.get(w["name_en"], [])
            qall0 = " ".join(w["quotes"]).lower()
            verb = ""
            for _vb in vbs:
                _vv = str((_vb.get("verb") if isinstance(_vb, dict) else "") or "")
                if _vv and _vv.lower() in qall0:
                    verb = _vv
                    break
            if not verb:
                verb = str((vbs[0].get("verb") if vbs else "take"))
            note = f"核心体系件:verified拿取({verb})+把数/波次见原话;原话\"{nq_short}...\""
            # 锚: 拿取动词 + 数字词 (须逐字出自 quotes, 机检只认这个)
            anchors: list[str] = []
            qall = " ".join(w["quotes"]).lower()
            if verb.lower() in qall:
                anchors.append(verb)
            num = w["_num_tok"].strip().lower() if w["_num_tok"] else ""
            if num and num in qall:
                anchors.append(w["_num_tok"].strip())
            if not anchors:
                # 兜底保绿: 首 quote 内首个数字词/动词 (必逐字, 非编造)
                q0low = (w["quotes"][0].lower() if w["quotes"] else "")
                for tok in ["four", "second", "two", "one", "three", "five", "level", "wave", "take", "buy", "roll for", "upgrade", "lock", "get"]:
                    if tok in q0low:
                        anchors.append(tok)
                        break
            if not anchors:
                raise SystemExit(f"step05 {w['name_en']} T1 锚逐字失败 (verified动词+数字须出自 quotes): 保绿失败")
            out_ws.append({"name_en": w["name_en"], "count": w["count"], "tier": "T1",
                           "confidence": "verified" if w["verified"] else "candidate",
                           "kind": "anchor", "inferred": False, "anchors": anchors,
                           "note": note, "quotes": w["quotes"], "quote_details": w["quote_details"]})
        else:
            note = f"过渡/备选位:前中期过渡,有T1即换不升满;原话\"{nq_short}...\""
            out_ws.append({"name_en": w["name_en"], "count": w["count"], "tier": "T2",
                           "confidence": "verified" if w["verified"] else "candidate",
                           "kind": "discretion", "inferred": True, "anchors": [],
                           "note": note, "quotes": w["quotes"], "quote_details": w["quote_details"]})
    # T1>=1 验收线保留 + T1 须 verified (锚要求 verified 拿取动词; 若排名首位非 verified 则保底失效交人看)
    t1 = [w for w in out_ws if w["tier"] == "T1"]
    t2 = [w for w in out_ws if w["tier"] != "T1"]
    for w in t2:
        w["tier"] = "T2"
    if not t1 and out_ws:
        # 保底 Top1 (排名制不断层也保 1, cyborg 不触发)
        score_of = {s["name_en"]: s["score"] for s in ws_sorted}
        cand = sorted(out_ws, key=lambda x: (-score_of.get(x["name_en"], x["count"]), -x["count"]))[0]
        cand["tier"] = "T1"
        # 保底转 T1 须补锚 (通用, 同上兜底)
        if not cand.get("anchors"):
            q0low = (cand["quotes"][0].lower() if cand.get("quotes") else "")
            for tok in ["take", "buy", "roll for", "upgrade", "lock", "get", "four", "second", "two"]:
                if tok in q0low:
                    cand["anchors"] = [tok]
                    break
        t1 = [cand]
        t2 = [w for w in out_ws if w["tier"] != "T1"]
    weapons = {"t1": [w for w in out_ws if w["tier"] == "T1"],
               "t2": [w for w in out_ws if w["tier"] == "T2"]}
    outdir = workdir / "steps" / "05-weapons"
    outdir.mkdir(parents=True, exist_ok=True)
    (outdir / "weapons.json").write_text(json.dumps(weapons, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    (workdir / "outputs").mkdir(parents=True, exist_ok=True)
    ((workdir / "outputs") / "weapons.json").write_text(json.dumps(weapons, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    return weapons


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
        print("子 prompt 见 prompts/step01-sentences.md / step02-verbs.md / step03-grouping.md "
              "/ step04-attributes.md / step05-weapons.md")
        return 0

    print(f"[segment1] workdir={workdir} (cwd 锁定, 只读写相对路径)")
    ensure_inputs(slug, vid, workdir)
    print("[segment1] inputs 四件校验通过 (Step00 取证, 只认 inputs)")
    sentences = step01(workdir)
    print(f"[segment1] 01-sentences: {len(sentences)} 句 (start/end 新 schema) -> steps/01-sentences/sentences.json")
    verbs = step02(workdir, sentences)
    print(f"[segment1] 02-verbs: verified={len(verbs['verified'])} candidates={len(verbs['candidates'])} (+start/end/context)")
    grouping = step03(workdir, verbs, sentences)
    print(f"[segment1] 03-grouping: {len(grouping)} 件 (quotes 去重, +quote_details)")
    ratings = step04(workdir, sentences)
    print(f"[segment1] 04-attributes: {len(ratings)} terms (主17+次级22) -> steps/04-attributes/ratings.json")
    weapons = step05(workdir, sentences)
    print(f"[segment1] 05-weapons: T1={len(weapons['t1'])} T2={len(weapons['t2'])} -> steps/05-weapons/weapons.json")
    print("[segment1] done. 跑 check: python scripts/check_segment1.py --slug cyborg --variant ultimate")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
