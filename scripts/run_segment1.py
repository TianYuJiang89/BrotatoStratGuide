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
  inputs/ 三件 (source.vtt + meta.json + manifest.json)
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
    CLOSED_VERBS,  # 闭集 10 下限 (#48 不动)
    VERB_PATTERNS,  # 闭集变形种子
    PARAPHRASE_MAP,  # 转述种子 (#48: 种子保留，agent 补走 candidates 格式)
    PARA_PATTERNS,  # 转述种子 pattern
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
    """inputs 校验 + slice 退役 (#61: Step00 后新链只认 inputs, 不读旧链).

    四件须已由 scripts/fetch_inputs.py 产出. 本步只做:
    - 四件存在性校验 (缺件即报错, 指引先跑 fetch_inputs 取证)
    - sha 对上校验 (manifest.sources[0].sha1 == source.vtt 实际 sha)
    - registry-slice 动态刷新 (全局 wiki-cache + terms + runtime source.vtt, 幂等)
    meta/manifest 为 Step00 取证产物, 本步不覆写 (provenance 只认取证).
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
    # #61 registry-slice 已退役: 全量注册表 (wiki-cache weapons+items) 直读, 不读 slice.
    # slice 曾为 count>0 子集; 全量只多不少, verb 匹配无损 (空命中自然无 verified/candidates).
    from build_mentions import load_registry_names as _load_reg
    _wall, _iall = _load_reg(REPO / "data")
    names: list[str] = list(_wall) + list(_iall)
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
                # #48 种子 + agent 补：种子保留 (PARAPHRASE_MAP/PARA_PATTERNS)，agent 补的每条走 candidates
                # （surface_verb/mapped_to/reason，字段已在 schema，不加字段；check 只查格式）。
                # 去写死：删 `bought turret instead of` 按句特判，instead-of 类转述由 agent 补（种子只保 grab/snatch/pick/avoid/ignoring 等）。
                assert _closest_para is not None
                surf_v = _closest_para[1]
                mapped = PARAPHRASE_MAP.get(surf_v, "skip" if surf_v in ("ignoring", "avoid", "avoiding") else "take")
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
    """分组: 锚+裁量 (#48: 删阈值 + 删全部按名特判; 只认动词信号; 68 全收录保留; 禁读 builds/mentions).

    锚 (机检只认逐字):
    - ban 系原话 (ban/recycle/sell 闭集原话, 或 candidates mapped_to==ban 含 agent 补) -> ban, 无按名例外.
    - 拿取系原话 (take/buy/pick up/lock/get/roll for 闭集原话, 或 mapped_to 落拿取系含 agent 补) + 高频 -> must_take.
      高频无固定数: 68 件 count 的 mean+stdev 动态 cutoff #50 口径 (count>=cutoff 即高频, 无 >=8/>=4 写死;
      换视频 count 分布变 cutoff 跟着动, 口径不动, 值不动).
    - skip 系原话 (skip 闭集原话, 或 mapped_to==skip 如 ignoring->skip 含 agent 补) + 高频 -> mentioned_not_taken;
      skip 系低频 -> casual (低频路过照旧).
    裁量 (只查格式, 审计标黄): 无动词或信号冲突无法定级 -> candidate + inferred true, reason 写清拿不准.
    """
    import statistics as _stats
    # #48 动词信号集 (闭集 10 下限内划分, 无按名, 无阈值) #50 口径: _BAN/_TAKE/_SKIP 构成为本视频动词分布口径,
    # 换视频新增转述 (如 snatch→take 新变体) 走 agent 补 candidates, 不改集合, 值不动.
    _BAN = {"ban", "recycle", "sell"}  # ban 系原话
    _TAKE = {"take", "buy", "pick up", "lock", "get", "roll for"}  # 拿取系原话
    _SKIP = {"skip"}  # 跳过系原话 (mapped skip 含 ignoring->skip 等种子 + agent 补)

    ver_by: dict[str, list] = defaultdict(list)
    for r in verbs.get("verified", []):
        ver_by[r["object_norm"]].append(r)
    cand_by: dict[str, list] = defaultdict(list)
    for r in verbs.get("candidates", []):
        cand_by[r["normalized_to"]].append(r)

    _, _, _, _, _, items_counts = _dynamic_scan(sentences)
    qlookup = _quote_lookup(sentences)
    # 只收 count>0 (沿全收录), 排序 count desc; 高频 cutoff 动态 (mean+stdev, 无固定数)
    items_all = [(k, v[0], v[1]) for k, v in items_counts.items() if v[0] > 0]
    _counts = [c for _, c, _ in items_all]
    _cutoff = (_stats.mean(_counts) + _stats.pstdev(_counts)) if len(_counts) >= 2 else 0

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

        # 分组只认动词信号 (#48, 无阈值无按名, 不读 builds/tags): ban > skip > 拿取+高频 > 路过; 拿不准进 candidates 位.
        _ban_verbs = [r for r in ver_list if r.get("verb") in _BAN]
        _ban_cand = [c for c in cand_list if c.get("mapped_to") in _BAN]
        _skip_verbs = [r for r in ver_list if r.get("verb") in _SKIP]
        _skip_cand = [c for c in cand_list if c.get("mapped_to") in _SKIP]
        _take_verbs = [r for r in ver_list if r.get("verb") in _TAKE]
        _take_cand = [c for c in cand_list if c.get("mapped_to") in _TAKE]
        _has_ban = bool(_ban_verbs or _ban_cand)
        _has_skip = bool(_skip_verbs or _skip_cand or any("ignor" in str(c.get("surface_verb", "")) for c in cand_list))
        _has_take = bool(_take_verbs or _take_cand)
        _is_high = count >= _cutoff
        if _has_ban:
            _bq = (_ban_verbs + _ban_cand)[0]["quote"] if (_ban_verbs + _ban_cand) else (quotes[0] if quotes else name)
            q0 = _bq[:60]
            reason = f"【ban】明确拒绝：拒绝动词原话（ban 系），原话[{q0}...]"
            group, tier = "ban", None
            verb, verb_type, surf_v, mapped = "ban", "closed", "ban", "ban"
            confidence, inferred = ("verified" if _ban_verbs else "candidate"), False
            disc = "拒绝动词原话（ban 系），机检锚点" if _ban_verbs else "动词转述拒绝（mapped ban，含 agent 补），待人点"
        elif _has_skip and _is_high:
            q0 = (ver_list + cand_list)[0]["quote"][:60] if (ver_list + cand_list) else (quotes[0][:60] if quotes else name)
            reason = f"【提过未拿】跳过语境（skip/ignoring 原话），有资源没拿，原话[{q0}...]"
            group, tier = "mentioned_not_taken", None
            # verb 保持 skip 信号 (verified skip 则 closed，否则 mapped)
            if _skip_verbs:
                verb, verb_type, surf_v, mapped = "skip", "closed", "skip", "skip"
                confidence, inferred = "verified", False
                disc = "跳过动词原话（skip 系），机检锚点"
            else:
                _sc0 = (_skip_cand or cand_list)[0] if (_skip_cand or cand_list) else None
                sv0 = str((_sc0 or {}).get("surface_verb", "skip"))
                verb, verb_type = "skip", ("closed" if sv0 in CLOSED_VERBS else "mapped")
                surf_v, mapped = (_sc0 or {}).get("surface_verb", "skip"), "skip"
                confidence, inferred = "candidate", False
                disc = f"动词转述跳过（{sv0}→skip，含 agent 补），待人点"
        elif _has_take and _is_high:
            group, tier = "must_take", "convenient"
            q0 = (ver_list + cand_list)[0]["quote"][:60] if (ver_list + cand_list) else (quotes[0][:60] if quotes else name)
            # 本变体统一 convenient (删 core/compromise 按名分档；无 Engineering/Structure tags，无 Mutation/Focus 特判)
            reason = f"【必拿·顺手】拿取动词原话（{_take_verbs[0].get('verb') if _take_verbs else (_take_cand[0].get('mapped_to') if _take_cand else 'take')}）+ 高频提及，遇到即拿，原话[{q0}...]"
            # confidence/inferred 保持锚信号：有 verified 拿取即 verified 绿，否则 candidate 黄
            if _take_verbs:
                confidence, inferred = "verified", False
            else:
                confidence, inferred = "candidate", False
        else:
            reason = "【路过提及】商店刷新或路过提及，无明确评价，不影响构筑主线。"
            group, tier = "casual_mention", None
            # confidence/inferred 保持：有动词即原信号，拿不准（无动词）进 candidates 位标黄
            if not has_verb:
                confidence, inferred = "candidate", True

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
    inputs/registry-slice.json (fetch 停产+旧文件删)、05 读 02-verbs。
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
        print("子 prompt 见 prompts/step01-sentences.md / step02-verbs.md / step03-grouping.md "
              "/ prompts/step04-ratings-fewshot.md (FROZEN, for-loop x39) / prompts/step05-{discovery,evidence,ranking}-fewshot.md "
              "(FROZEN v2, 三本手册各贴各, discovery/evidence/ranking 三段 agent, #61)")
        return 0

    print(f"[segment1] workdir={workdir} (cwd 锁定, 只读写相对路径)")
    ensure_inputs(slug, vid, workdir)
    print("[segment1] inputs 三件校验通过 (Step00 取证, 只认 inputs, #61 slice 已退役)")
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
