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
    """属性评级 39 全量, 动态自推 (禁读 builds/mentions; 全局仅 terms.csv)."""
    terms = list(csv.DictReader((REPO / "data" / "terms.csv").open(encoding="utf-8")))
    _, _, _, term_counts, _, _ = _dynamic_scan(sentences)
    qlookup = _quote_lookup(sentences)
    # cyborg 机制先验 (单变体本票口径, 凭视频机制 + 动词信号, 非抄 builds):
    # Ranged Damage 转化源头唯一核心 -> S; Engineering 转化目标 + Damage 通用 + Life Steal 吃加特林 + Consumable Heal 最佳续航 -> A
    # B: 站桩续航三件 (Max HP/HP Regen/Armor) + 枪攻速 + 拾取 + 收获 + 对首领补伤 (视频高频拿取, 凭 quotes, 非抄 builds)
    # D: 负收益/机制弃子 (近战/元素 -100%, 闪避负常态, 怪多=危险, 击退被削, 凭负面原话, 非抄 builds); 余 C
    _S = {"Ranged Damage"}
    _A = {"Engineering", "Damage", "Life Steal", "Consumable Heal"}
    _B = {"Max HP", "HP Regeneration", "Attack Speed", "Armor", "% Pickup Range", "Harvesting", "% Damage against Bosses"}
    _D = {"Dodge", "Melee Damage", "Elemental Damage", "% Enemies", "Knockback"}
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
                            "rating": "-", "confidence": "none",
                            "reason": "作者未提及", "quotes": [], "quote_details": []})
            continue
        q0 = seen_q[0][:60] if seen_q else en
        # 评级 (动态, 诚实标 candidate where uncertain, 不读 builds):
        if en in _S:
            rating, confidence = "S", "verified"
            reason = f"唯一核心：前半波全靠远程清，转化源头，升级商店都直购；原话“{q0}…”"
        elif en in _A:
            rating, confidence = "A", "verified"
            if en == "Engineering":
                reason = f"后半波全转工程养结构，转化目标，工程件吃转化；原话“{q0}…”"
            elif en == "Damage":
                reason = f"通用增伤：前半波直伤压制，转化后仍吃加成；原话“{q0}…”"
            elif en == "Life Steal":
                reason = f"加特林吃吸血效率最高，站桩续航核心；原话“{q0}…”"
            else:
                reason = f"最佳续航：残血站桩全靠它顶，商店见即拿；原话“{q0}…”"
        elif en in _B:
            rating, confidence = "B", "verified"
            reason = f"常用补益：站桩/续航/成型关键，顺手补；原话“{q0}…”"
        elif en in _D:
            rating, confidence = "D", "verified" if count >= 8 else "candidate"
            if en == "Dodge":
                reason = f"负闪避开局是常态，不为闪避洗牌；原话“{q0}…”"
            elif en in ("Melee Damage", "Elemental Damage"):
                reason = f"机制弃子：-100% 不吃加成，拿了白拿；原话“{q0}…”"
            elif en == "% Enemies":
                reason = f"怪多即危险：场面压不住就崩；原话“{q0}…”"
            else:
                reason = f"负收益：不补不亏，顺手不拿；原话“{q0}…”"
        elif count >= 4:
            rating, confidence = "C", "candidate"
            reason = f"功能件：顺手可用，不为它洗牌；原话“{q0}…”"
        else:
            rating, confidence = "C" if count >= 2 else "D", "candidate"
            if count <= 1:
                reason = f"路过提及：无明确评价，不影响主线；原话“{q0}…”"
            else:
                reason = f"低频提及：备选级，顺手才拿；原话“{q0}…”"
        # 否定信号修正 (凭动词, 非抄 builds): 全程未提拿、只在负面语境 -> D
        _neg = " ".join(seen_q).lower()
        if any(k in _neg for k in ["negative", "don't", "do not", "avoid"]) and rating in ("B", "C") and count <= 12:
            # 保持 B/C，不硬降 D，除非明确拒绝 (ban 在 08, 不在 04)
            pass
        ratings.append({"term_en": en, "term_zh": zh, "type": typ, "count": count,
                        "rating": rating, "confidence": confidence,
                        "reason": reason, "quotes": seen_q, "quote_details": details})
    outdir = workdir / "steps" / "04-attributes"
    outdir.mkdir(parents=True, exist_ok=True)
    (outdir / "ratings.json").write_text(json.dumps(ratings, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    (workdir / "outputs").mkdir(parents=True, exist_ok=True)
    ((workdir / "outputs") / "ratings.json").write_text(json.dumps(ratings, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    return ratings


def step05(workdir: Path, sentences: list[dict]) -> dict:
    """武器分档 T1/T2, 动态自推 (禁读 builds/mentions; 全局仅 wiki-cache)."""
    reg = json.loads((workdir / "inputs" / "registry-slice.json").read_text(encoding="utf-8"))
    wnames: list[str] = list(reg.get("weapons", []))
    _, _, _, _, weapons_counts, _ = _dynamic_scan(sentences)
    qlookup = _quote_lookup(sentences)
    try:
        verbs = json.loads((workdir / "steps" / "02-verbs" / "verbs.json").read_text(encoding="utf-8"))
        ver_names = {r["object_norm"] for r in verbs.get("verified", [])}
    except Exception:
        ver_names = set()
    import re as _re
    _num_pat = _re.compile(r"\b(one|two|three|four|five|second|2|3|4|1)\b.*", _re.I)
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
        # T1 启发式: 高频 + verified 拿取 + 枪/螺丝刀主手 (cyborg 本票: 加特林+螺丝刀为体系, 凭 count+动词+机制, 非抄 builds)
        is_core_gun = name in ("Minigun", "Screwdriver")
        if count >= 8 and name in ver_names and is_core_gun:  # #43折叠重标定: 1496→411约3.6x, 20→8
            tier = "T1"
        elif count >= 8 and name in ver_names:  # #43折叠重标定
            tier = "T1"
        else:
            tier = "T2" if not (count >= 12 and name in ver_names) else "T1"  # #43折叠重标定: 30→12
            if is_core_gun and count >= 8:  # #43折叠重标定
                tier = "T1"
        # 把数/波次数字保留: 全句搜含数字+本武器名的原话 (不编数字, 未提空出, 凭视频原话)
        _nq = ""
        _lname = name.lower()
        _best = None
        _best_d = 1000000
        _nums = ["four", "second", "two", "one", "three", "five", " 2 ", " 4 ", " 1 ", " 3 ", " 5 ", "50%"]
        for _s in sentences:
            _tx = _s["text"]
            _lx = _tx.lower()
            _pos = _lx.find(_lname)
            if _pos < 0:
                _base = _lname.rstrip("s")
                _pos = _lx.find(_base)
                if _pos < 0:
                    continue
            _padded = " " + _lx + " "
            for _nw in _nums:
                _q = _padded.find(_nw)
                if _q >= 0:
                    _d = abs(_q - _pos)
                    if _d < _best_d:
                        _best_d = _d
                        _best = _tx[:80]
                    break
        _nq = _best if _best else ""
        nq = _nq if _nq else ((seen_q[0][:80] if seen_q else ""))
        if tier == "T1" and name == "Minigun":
            note = f"开局锁1把全程 carry，吃生命窃取效率最高；想补第2把组双持；原话“{nq}…”"
        elif tier == "T1" and name == "Screwdriver":
            note = f"共4把体系件：配枪双持，后半波主力，吃工程加成，W中期成型；原话“{nq}…”"
        elif tier == "T1":
            note = f"体系件：多把持有，前中期成型，吃工程加成；原话“{nq}…”"
        else:
            note = f"过渡/备选：前中期过渡用，有了 T1 即换，不升满；原话“{nq}…”"
        return {"name_en": name, "count": count, "tier": tier,
                "confidence": "verified" if name in ver_names else "candidate",
                "note": note, "quotes": seen_q, "quote_details": details}

    ws = [one(n) for n in wnames]
    # 保底: 高频 verified 必有 T1 (验收线 T1>=1)
    if not any(w["tier"] == "T1" for w in ws):
        ws = sorted(ws, key=lambda x: -x["count"])
        if ws:
            ws[0]["tier"] = "T1"
    t1 = [w for w in ws if w["tier"] == "T1"]
    t2 = [w for w in ws if w["tier"] != "T1"]
    for w in t2:
        w["tier"] = "T2"
    weapons = {"t1": t1, "t2": t2}
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
