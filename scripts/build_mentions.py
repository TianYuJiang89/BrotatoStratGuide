"""交叉表构建器 (#17): 字幕x术语命中表机器 gate.

扫描 `data/subs/<slug>.en-orig.vtt` (自动字幕, 仅取证) x 39 术语 + 注册表武器/道具名,
逐个命中计数并附原句, 输出 `data/mentions/<slug>.json` (本单定).

格式 (本单定):
{
  "slug": "<slug>",
  "vtt": "data/subs/<slug>.en-orig.vtt",
  "video_id": "<from builds source.video_id if present>",
  "generated_by": "scripts/build_mentions.py",
  "terms": {"Speed": {"count": 1, "quotes": ["原句..."]}, ... 39 全量},
  "weapons": {"Wrench": {"count": 1, "quotes": [...]}, ...},
  "items": {"Turret": {...}, ...}
}

用法:
  python scripts/build_mentions.py --slug engineer
  python scripts/build_mentions.py --all
  --data-dir / --subs-dir / --mentions-dir 供测试隔离 (默认 data/ data/subs/ data/mentions/).

匹配注意 (#14 回归 + #28 精度):
- Speed 只认移动速度, `attack speed` 不得污染 (负向前瞻排除 attack/structure/enemy/burning).
- Engineering 只认 `engineering`, 不认角色名 `engineer`.
- Range 用词边界, 不吞 `ranged`.
- Scar 只认道具 `Scar/scars`, 不吞 `scared/scary/scarf` (#28: 注册表兜底不用 \\w*, 只允常见复数 s/es/ies/ves; Fin/Acid/Bag/Tree 同理).
- 宁可多 warn 不可漏: 通用词 (damage/speed/range) 按词边界计, 复合提及双计.
"""

from __future__ import annotations

import argparse
import csv
import json
import re
import sys
from pathlib import Path


def load_terms(data_dir: Path) -> list[str]:
    path = data_dir / "terms.csv"
    with path.open(encoding="utf-8") as f:
        rows = list(csv.DictReader(f))
    return [str(r.get("en", "")).strip() for r in rows if r.get("en")]


def load_registry_names(data_dir: Path) -> tuple[list[str], list[str]]:
    path = data_dir / "wiki-cache.json"
    reg = json.loads(path.read_text(encoding="utf-8"))
    weapons: list[str] = []
    items: list[str] = []
    if isinstance(reg, dict):
        w = reg.get("weapons")
        if isinstance(w, dict):
            weapons = sorted(str(k) for k in w.keys())
        it = reg.get("items")
        if isinstance(it, dict):
            items = sorted(str(k) for k in it.keys())
    return (weapons, items)


def _wordnames_to_pattern(name: str) -> str:
    """注册表名兜底 pattern: 空格转 \\s+, 首尾词界, 尾只允常见复数 (s/es/ies/ves), 不用 \\w* (#28 scared/scary 误算 Scar)."""
    clean = name.strip().lower()
    if not clean:
        return r"\b\b"
    parts = clean.split()
    prefix = [re.escape(p) for p in parts[:-1]]
    last = parts[-1]
    vowels = set("aeiou")
    if last.endswith("s"):
        last_pat = re.escape(last) + r"(?:es)?"
    elif last.endswith("x") or last.endswith("z") or last.endswith("ch") or last.endswith("sh"):
        last_pat = re.escape(last) + r"(?:es)?"
    elif last.endswith("y") and len(last) > 1 and last[-2] not in vowels:
        last_pat = re.escape(last[:-1]) + r"(?:y|ies)"
    elif last.endswith("fe"):
        last_pat = re.escape(last[:-2]) + r"(?:fe|ves)"
    elif last.endswith("f") and not last.endswith("ff"):
        last_pat = re.escape(last[:-1]) + r"(?:f|ves)"
    elif last.endswith("o"):
        last_pat = re.escape(last) + r"(?:s|es)?"
    else:
        last_pat = re.escape(last) + r"(?:s)?"
    esc = (r"\s+".join(prefix) + r"\s+" + last_pat) if prefix else last_pat
    return r"\b" + esc + r"\b"


# 39 术语别名 (小写正则, IGNORECASE 编译).
# 设计原则: 高召回 (漏检=重演 #14), 精度只在已证误报处收紧
# (Speed 排 attack/structure/enemy/burning, Range 不吞 ranged).
TERM_PATTERNS: dict[str, list[str]] = {
    "Max HP": [r"\bmax\s*hps?\b", r"\bmax\s*healths?\b", r"\bmaximum\s*hps?\b", r"\bmaximum\s*healths?\b"],
    "HP Regeneration": [r"\bhp\s*regen(?:eration)?s?\b", r"\bhealth\s*regen(?:eration)?s?\b", r"\bregens?\b", r"\bregenerations?\b"],
    "Life Steal": [r"\blife\s*steals?\b", r"\blifesteals?\b", r"\blife[\s\-]*steals?\b"],
    "Damage": [r"\bdamages?\b"],
    "Melee Damage": [r"\bmelees?\b"],
    "Ranged Damage": [r"\branged\b"],
    "Elemental Damage": [r"\belemental\b"],
    "Attack Speed": [r"\battack\s*speeds?\b"],
    "Crit Chance": [r"\bcrits?\b", r"\bcriticals?\b", r"\bcrit\s*chances?\b", r"\bcrit\s*rates?\b"],
    "Engineering": [r"\bengineerings?\b"],
    "Range": [r"\branges?\b"],
    "Armor": [r"\barmors?\b", r"\barmours?\b"],
    "Dodge": [r"\bdodg(?:e(?:s|d)?|ing|y)\b"],
    "Speed": [
        r"\bmovespeeds?\b",
        r"\bmove\s*speeds?\b",
        r"\bmovement\s*speeds?\b",
        r"(?<!attack )(?<!structure )(?<!enemy )(?<!burning )\bspeeds?\b",
    ],
    "Luck": [r"\blucks?\b", r"\blucky\b"],
    "Harvesting": [r"\bharvest(?:s|ed|ing)?\b"],
    "Curse": [r"\bcurs(?:e(?:s|d)?|ing)\b"],
    "Consumable Heal": [r"\bconsumables?\b", r"\bheal(?:s|ed|ing)?\b"],
    "% Materials Healing": [r"\bmaterials?\s*healings?\b", r"\bmats?\s*healings?\b"],
    "% XP Gain": [r"\bxps?\b", r"\bexperiences?\b", r"\bxp\s*gains?\b"],
    "% Pickup Range": [r"\bpickups?\b", r"\bpick[\s\-]*ups?\b"],
    "% Items Price": [r"\bitems?\s*prices?\b"],
    "% Explosion Damage": [r"\bexplosions?\s*damages?\b", r"\bexplosions?\b"],
    "% Explosion Size": [r"\bexplosions?\s*sizes?\b", r"\bexplosions?\s*radius\b", r"\bexplosions?\s*ranges?\b"],
    "Bounces": [r"\bbounc(?:e(?:s|d)?|ing)\b"],
    "Piercing": [r"\bpierc(?:e(?:s|d)?|ing)\b"],
    "% Piercing Damage": [r"\bpierc(?:e|ing)\s*damages?\b"],
    "% Damage against Bosses": [r"\bboss\b", r"\bbosses\b"],
    "% Structure Attack Speed": [r"\bstructures?\s*attacks?\b"],
    "Structure Range": [r"\bstructures?\s*ranges?\b"],
    "% Burning Speed": [r"\bburnings?\s*speeds?\b", r"\bburnings?\b"],
    "Burning Spread": [r"\bburnings?\s*spreads?\b", r"\bburns?\s*spreads?\b"],
    "Knockback": [r"\bknockbacks?\b", r"\bknock\s*backs?\b", r"\bknock(?:s|ed|ing)?\b"],
    "% Double Material Chance": [r"\bdouble\s*mats?\b", r"\bdouble\s*materials?\b"],
    "Free Rerolls": [r"\breroll(?:s|ed|ing)?\b", r"\bfree\s*reroll(?:s|ed|ing)?\b"],
    "Trees": [r"\btrees?\b"],
    "% Enemies": [r"\benem(?:y|ies)\b"],
    "% Enemy Speed": [r"\benem(?:y|ies)\s*speeds?\b", r"\benem(?:y|ies)\b"],
    "% Reroll Price": [r"\brerolls?\s*prices?\b"],
}

WEAPON_PATTERNS: dict[str, list[str]] = {
    "SMG": [r"\bsmgs?\b"],
    "Pistol": [r"\bpistols?\b"],
    "Minigun": [r"\bminiguns?\b", r"\bmini\s*guns?\b"],
    "Wrench": [r"\bwrench(?:es)?\b"],
}

ITEM_PATTERNS: dict[str, list[str]] = {
    "Big Arms": [r"\bbig\s*arms?\b"],
    "Improved Tools": [r"\bimproved\s*tools?\b"],
    "Turret": [r"\bturrets?\b"],
    "Coffee": [r"\bcoffees?\b"],
}


def _compile(patterns: list[str]) -> list[re.Pattern[str]]:
    return [re.compile(p, re.IGNORECASE) for p in patterns]


def build_pattern_map(
    terms: list[str], weapons: list[str], items: list[str]
) -> dict[str, list[re.Pattern[str]]]:
    out: dict[str, list[re.Pattern[str]]] = {}
    for en in terms:
        pats = TERM_PATTERNS.get(en)
        if pats is None:
            pats = [_wordnames_to_pattern(en)]
        out[en] = _compile(pats)
    for en in weapons:
        pats = WEAPON_PATTERNS.get(en, [_wordnames_to_pattern(en)])
        out[f"weapon:{en}"] = _compile(pats)
    for en in items:
        pats = ITEM_PATTERNS.get(en, [_wordnames_to_pattern(en)])
        out[f"item:{en}"] = _compile(pats)
    return out


def detect_subs_source(text: str) -> str:
    """字幕来源判定 (#43): 有 karaoke 词级标签即 auto, 否则 manual.

    yt-dlp auto-sub raw 自带 `<c>` / `<00:xx>` 逐词时间戳 + 滚动窗口;
    人工字幕无此类标签. 折叠函数据此之外的重叠率自动 no-op,
    此处仅作 inputs 标注与审计展示用."""
    if "<c>" in text or "<00:" in text or "<c." in text:
        return "auto"
    return "manual"


def _overlap_len(prev_words: list[str], cur_words: list[str]) -> int:
    """词级后缀-前缀最长重叠 (#43 滚动折叠核心)."""
    maxk = min(len(prev_words), len(cur_words))
    for kk in range(maxk, 0, -1):
        if prev_words[-kk:] == cur_words[:kk]:
            return kk
    return 0


def _is_rolling(cues: list[str]) -> bool:
    """滚动判定: 重叠率>20% 即 auto 滚动窗口, 否则 manual/clean 直接沿用."""
    if len(cues) < 3:
        return False
    hits = 0
    for i in range(1, len(cues)):
        pw = cues[i - 1].split()
        cw = cues[i].split()
        if not pw or not cw:
            continue
        if cues[i] == cues[i - 1]:
            hits += 1
        elif _overlap_len(pw, cw) >= 3:
            hits += 1
        elif cues[i] in cues[i - 1] or cues[i - 1] in cues[i]:
            hits += 1
    return (hits / max(1, len(cues) - 1)) > 0.2


def fold_cue_texts(cues: list[str]) -> list[str]:
    """滚动折叠 (无时间戳版, #43-A): 词级去重重建全文后按标点切句.

    clean VTT 无重叠时自动 no-op 原样返回 (保测试与 manual 兼容)."""
    # 掉头: WEBVTT 元数据残留 (Kind:/Language:) 不进正文.
    cues = [c for c in cues if not c.strip().lower().startswith(("kind:", "language:"))]
    if "kind: captions" in " ".join(cues[:1]).lower():
        cues = cues[1:]
    if not _is_rolling(cues):
        return cues
    full_words: list[str] = []
    for cue in cues:
        cur_w = cue.split()
        if not cur_w:
            continue
        k = _overlap_len(full_words, cur_w)
        full_words.extend(cur_w[k:])
    if not full_words:
        return cues
    full_text = " ".join(full_words)
    parts = re.split(r"(?<=[.!?])\s+", full_text)
    sents = [p.strip() for p in parts if p.strip()]
    out: list[str] = []
    for s in sents:
        if len(s) > 500:
            s = s[:500]
        out.append(s)
    return out if out else cues


def fold_timed_cues(cues: list[dict]) -> list[dict]:
    """滚动折叠 (带时间戳版, #43-A): 同 fold_cue_texts 口径 + 句时间戳.

    句 start/end 取首词 cue start / 尾词 cue end, t=int(start_s).
    非滚动直接返回原 cues (manual 兼容)."""
    texts = [c.get("text", "") for c in cues if isinstance(c, dict)]
    if not _is_rolling([t for t in texts if t]):
        return cues
    # 掉无时间戳头 (Kind: captions 等), 保留其余原序.
    timed = [c for c in cues if isinstance(c, dict) and c.get("start") is not None]
    if not timed:
        return cues
    full_words: list[str] = []
    word_times: list[tuple] = []
    for c in timed:
        cur_w = str(c.get("text", "")).split()
        if not cur_w:
            continue
        k = _overlap_len(full_words, cur_w)
        for w in cur_w[k:]:
            full_words.append(w)
            word_times.append((c.get("start"), c.get("end"), c.get("start_s"), c.get("end_s")))
    if not full_words:
        return cues
    full_text = " ".join(full_words)
    bounds = [m.end() for m in re.finditer(r"(?<=[.!?])\s+", full_text)]
    off = 0
    word_starts: list[int] = []
    for w in full_words:
        word_starts.append(off)
        off += len(w) + 1
    sent_bounds = [0]
    for b in bounds:
        for idx, ws in enumerate(word_starts):
            if ws >= b:
                if idx > sent_bounds[-1]:
                    sent_bounds.append(idx)
                break
    sent_bounds.append(len(full_words))
    folded: list[dict] = []
    for i in range(len(sent_bounds) - 1):
        a, b = sent_bounds[i], sent_bounds[i + 1]
        if a >= b:
            continue
        txt = " ".join(full_words[a:b])
        if len(txt) > 500:
            txt = txt[:500]
        st, ed, ss, _es = word_times[a][0], word_times[b - 1][1], word_times[a][2], word_times[b - 1][3]
        folded.append({"text": txt, "start": st, "end": ed,
                       "start_s": ss, "end_s": word_times[b - 1][3]})
    return folded if folded else cues


def parse_vtt(text: str) -> list[str]:
    """VTT 解析: 按空行分块, 丢时间戳/序号/头, 每块 join 为一句原句 + #43 滚动折叠."""
    cues: list[str] = []
    # 统一换行, 按空行分块.
    blocks = re.split(r"\r?\n\s*\r?\n", text)
    for block in blocks:
        lines = [ln.strip() for ln in block.strip().splitlines()]
        # 去头: WEBVTT / NOTE / STYLE / REGION.
        if not lines:
            continue
        if lines[0].upper().startswith("WEBVTT"):
            lines = lines[1:]
        if not lines:
            continue
        if lines[0].upper().startswith(("NOTE", "STYLE", "REGION")):
            continue
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
            # 去 HTML 标签.
            no_tag = re.sub(r"<[^>]+>", "", ln).strip()
            if no_tag:
                content.append(no_tag)
        if content:
            cue = " ".join(content).strip()
            # 长度截断防膨胀, 保留原句可审.
            if len(cue) > 500:
                cue = cue[:500]
            cues.append(cue)
    # #43 滚动折叠: auto 滚动窗口折叠为整句, manual/clean 自动 no-op.
    return fold_cue_texts(cues)


def scan_cues(
    cues: list[str], pattern_map: dict[str, list[re.Pattern[str]]]
) -> dict[str, tuple[int, list[str]]]:
    """每 key 计数 + 原句 (cap 10 句防膨胀)."""
    result: dict[str, tuple[int, list[str]]] = {}
    lowered = [c.lower() for c in cues]
    for key, pats in pattern_map.items():
        hits: list[str] = []
        for idx, low in enumerate(lowered):
            for pat in pats:
                if pat.search(low):
                    hits.append(cues[idx])
                    break
        result[key] = (len(hits), hits[:10])
    return result


def _variant_id_for_covers(covers: list[str]) -> str:
    return "-".join(str(c).strip().lower().replace(" ", "-") for c in covers)


def _load_variants(data_dir: Path, slug: str) -> tuple[list[dict[str, object]], list[str]]:
    """覆盖制变体加载: builds/<slug>.json 内 variants 数组, 旧单层废除."""
    build_path = data_dir / "builds" / f"{slug}.json"
    if not build_path.exists():
        return ([], [f"missing build data: {build_path}"])
    try:
        raw = json.loads(build_path.read_text(encoding="utf-8"))
    except Exception as exc:
        return ([], [f"build load fail {slug}: {exc}"])
    if not isinstance(raw, dict):
        return ([], [f"build must be dict: {slug}"])
    variants_raw = raw.get("variants")
    if not isinstance(variants_raw, list) or not variants_raw:
        return ([], [f"missing section data: variants (须为非空数组, 旧单层键废除): {slug}"])
    out: list[dict[str, object]] = [v for v in variants_raw if isinstance(v, dict)]
    if len(out) != len(variants_raw):
        return ([], [f"variants must be dicts: {slug}"])
    return (out, [])


def _vtt_for_variant(subs_dir: Path, slug: str, variant_id: str) -> Path:
    """每变体字幕: data/subs/<slug>__<variant>.en-orig.vtt; 单变体兼容旧 <slug>.en-orig.vtt."""
    per = subs_dir / f"{slug}__{variant_id}.en-orig.vtt"
    if per.exists():
        return per
    legacy = subs_dir / f"{slug}.en-orig.vtt"
    return legacy


def build_one_variant(
    slug: str, variant: dict[str, object], data_dir: Path, subs_dir: Path, mentions_dir: Path,
    terms: list[str], weapons: list[str], items: list[str],
) -> tuple[list[str], list[str]]:
    covers_raw = variant.get("covers")
    covers = [str(c) for c in covers_raw] if isinstance(covers_raw, list) else []
    vid = str(variant.get("id", "") or _variant_id_for_covers(covers))
    vtt_path = _vtt_for_variant(subs_dir, slug, vid)
    if not vtt_path.exists():
        per = subs_dir / f"{slug}__{vid}.en-orig.vtt"
        return ([f"missing subtitle: {per} (先按 SOP §4 每变体独立入库字幕)"], [])
    try:
        cues = parse_vtt(vtt_path.read_text(encoding="utf-8"))
    except Exception as exc:
        return ([f"vtt parse fail: {exc}"], [])
    pattern_map = build_pattern_map(terms, weapons, items)
    scanned = scan_cues(cues, pattern_map)
    src = variant.get("source")
    video_id = str(src.get("video_id")) if isinstance(src, dict) and isinstance(src.get("video_id"), str) else ""
    terms_out: dict[str, dict[str, object]] = {}
    for en in terms:
        count, quotes = scanned.get(en, (0, []))
        terms_out[en] = {"count": count, "quotes": quotes}
    weapons_out: dict[str, dict[str, object]] = {}
    for en in weapons:
        count, quotes = scanned.get(f"weapon:{en}", (0, []))
        weapons_out[en] = {"count": count, "quotes": quotes}
    items_out: dict[str, dict[str, object]] = {}
    for en in items:
        count, quotes = scanned.get(f"item:{en}", (0, []))
        items_out[en] = {"count": count, "quotes": quotes}
    # vtt 相对路径: per-variant 优先, legacy 回落保留原串.
    try:
        repo = Path(__file__).resolve().parent.parent
        vtt_rel = str(vtt_path.relative_to(repo))
    except Exception:
        vtt_rel = f"data/subs/{slug}__{vid}.en-orig.vtt"
    payload: dict[str, object] = {
        "slug": slug,
        "variant": vid,
        "covers": covers,
        "label": str(variant.get("label", "")),
        "vtt": vtt_rel.replace("\\", "/"),
        "video_id": video_id,
        "generated_by": "scripts/build_mentions.py",
        "terms": terms_out,
        "weapons": weapons_out,
        "items": items_out,
    }
    mentions_dir.mkdir(parents=True, exist_ok=True)
    out_path = mentions_dir / f"{slug}__{vid}.json"
    out_path.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    return ([], [])


def build_one(
    slug: str, data_dir: Path, subs_dir: Path, mentions_dir: Path, variant_id: str | None = None,
) -> tuple[list[str], list[str]]:
    errors: list[str] = []
    warns: list[str] = []
    try:
        terms = load_terms(data_dir)
    except Exception as exc:
        return ([f"terms load fail: {exc}"], [])
    if len(terms) != 39:
        return ([f"terms must be 39, got {len(terms)}"], [])
    try:
        weapons, items = load_registry_names(data_dir)
    except Exception as exc:
        return ([f"registry load fail: {exc}"], [])
    variants, v_errors = _load_variants(data_dir, slug)
    if v_errors:
        return (v_errors, [])
    targets = [v for v in variants if variant_id is None or str(v.get("id", "")) == variant_id]
    if variant_id is not None and not targets:
        return ([f"unknown variant: {slug}__{variant_id} (covers slug 化)"], [])
    for variant in targets:
        v_errors, _ = build_one_variant(slug, variant, data_dir, subs_dir, mentions_dir, terms, weapons, items)
        errors.extend(v_errors)
    return (errors, warns)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="构建字幕x术语交叉表 (#17 机器 gate)")
    group = parser.add_mutually_exclusive_group(required=True)
    group.add_argument("--slug", help="按角色构建, 如 --slug engineer")
    group.add_argument("--all", action="store_true", help="全量构建 (有字幕者)")
    parser.add_argument("--data-dir", default="data")
    parser.add_argument("--subs-dir", default="")
    parser.add_argument("--mentions-dir", default="")
    parser.add_argument("--variant", default="", help="单变体 id, 如 --variant ultimate (须与 --slug 同用)")
    args = parser.parse_args(argv)

    repo = Path(__file__).resolve().parent.parent
    data_dir = Path(args.data_dir)
    if not data_dir.is_absolute():
        data_dir = repo / data_dir
    subs_dir = Path(args.subs_dir) if args.subs_dir else data_dir / "subs"
    if not subs_dir.is_absolute():
        subs_dir = repo / subs_dir
    mentions_dir = Path(args.mentions_dir) if args.mentions_dir else data_dir / "mentions"
    if not mentions_dir.is_absolute():
        mentions_dir = repo / mentions_dir

    if args.slug:
        variant_arg = str(args.variant).strip() or None
        errors, _ = build_one(args.slug, data_dir, subs_dir, mentions_dir, variant_arg)
        if errors:
            for err in errors:
                print(f"FAIL: {err}", file=sys.stderr)
            return 1
        suffix = f"__{variant_arg}" if variant_arg else " (全变体)"
        print(f"built mentions --slug {args.slug}{suffix} -> {mentions_dir}")
        return 0

    # --all: 有 build 数据且有字幕者逐个构建, 缺字幕者跳过 warn (不 fail, 待补).
    builds_dir = data_dir / "builds"
    slugs = sorted(p.stem for p in builds_dir.glob("*.json")) if builds_dir.exists() else []
    failed = False
    for slug in slugs:
        # 覆盖制: 每变体缺字幕单独 warn 跳过, 不 fail 整单.
        variants, v_errors = _load_variants(data_dir, slug)
        if v_errors or not variants:
            print(f"WARN: missing build variants, skip {slug} (待补)")
            continue
        for variant in variants:
            vid = str(variant.get("id", ""))
            vtt_path = _vtt_for_variant(subs_dir, slug, vid)
            if not vtt_path.exists():
                print(f"WARN: missing subtitle, skip {slug}__{vid} (待补)")
                continue
            errors, _ = build_one(slug, data_dir, subs_dir, mentions_dir, vid)
            if errors:
                for err in errors:
                    print(f"FAIL [{slug}__{vid}]: {err}", file=sys.stderr)
                failed = True
    print(f"built mentions --all -> {mentions_dir}")
    return 1 if failed else 0


if __name__ == "__main__":
    raise SystemExit(main())
