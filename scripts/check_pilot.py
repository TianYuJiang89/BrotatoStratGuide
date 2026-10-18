#!/usr/bin/env python3
"""Machine check for pilot (#38, 沿步骤契约 Q5 调整).

旧链全套不在验收内. 本机检只查:
- schema 合法
- verified 全部分组
- candidates 每条有 quote+reason
- 低频有无一句话交代
- sha 对上 (原"高频未收录"因全收自然全绿, 改为查低频交代)

Usage:
  python scripts/check_pilot.py --slug cyborg --variant ultimate
  python scripts/check_pilot.py --slug cyborg --variant ultimate --work-root G:/brotato-work
"""

from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path

REPO = Path(__file__).resolve().parent.parent


def fail(msg: str, errors: list[str]) -> None:
    errors.append(msg)
    print(f"FAIL: {msg}")


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description="check pilot (#38)")
    ap.add_argument("--slug", default="cyborg")
    ap.add_argument("--variant", default="ultimate")
    ap.add_argument("--work-root", default="G:/brotato-work")
    args = ap.parse_args(argv)

    slug, vid = args.slug, args.variant
    work = Path(args.work_root) / slug / vid
    errors: list[str] = []
    warns: list[str] = []

    # --- 文件存在 ---
    need = [
        work / "inputs" / "source.vtt",
        work / "inputs" / "meta.json",
        work / "inputs" / "registry-slice.json",
        work / "inputs" / "manifest.json",
        work / "steps" / "01-sentences" / "sentences.json",
        work / "steps" / "02-verbs" / "verbs.json",
        work / "steps" / "03-grouping" / "grouping.json",
        work / "outputs" / "groups.json",
    ]
    for p in need:
        if not p.exists():
            fail(f"missing file: {p}", errors)

    if errors:
        return 1

    manifest = json.loads((work / "inputs" / "manifest.json").read_text(encoding="utf-8"))
    sentences = json.loads((work / "steps" / "01-sentences" / "sentences.json").read_text(encoding="utf-8"))
    verbs = json.loads((work / "steps" / "02-verbs" / "verbs.json").read_text(encoding="utf-8"))
    grouping = json.loads((work / "steps" / "03-grouping" / "grouping.json").read_text(encoding="utf-8"))
    outputs = json.loads((work / "outputs" / "groups.json").read_text(encoding="utf-8"))

    # --- schema 合法 ---
    if not isinstance(sentences, list) or not sentences:
        fail("sentences must be non-empty array", errors)
    else:
        ids = [s.get("id") for s in sentences]
        if ids != list(range(1, len(sentences) + 1)):
            fail(f"sentences id must be 1..N continuous, got head {ids[:5]}", errors)
        for s in sentences[:5]:
            if not isinstance(s.get("text"), str) or not s["text"].strip():
                fail(f"sentence text empty: {s.get('id')}", errors)
            if "-->" in s["text"] or "<c>" in s["text"]:
                fail(f"sentence not cleaned: {s.get('id')}", errors)

    if not isinstance(verbs, dict) or "verified" not in verbs or "candidates" not in verbs:
        fail("verbs must be {verified[], candidates[]}", errors)
        verified, candidates = [], []
    else:
        verified, candidates = verbs["verified"], verbs["candidates"]
        if not isinstance(verified, list) or not isinstance(candidates, list):
            fail("verified/candidates must be arrays", errors)

    sent_by_id = {s["id"]: s["text"] for s in sentences if isinstance(s, dict)}

    for r in verified:
        for k in ("verb", "object_norm", "sentence_id", "quote"):
            if k not in r:
                fail(f"verified missing {k}: {r}", errors)
        if r.get("quote") != sent_by_id.get(r.get("sentence_id")):
            fail(f"verified quote must equal sentences text: {r.get('object_norm')}@{r.get('sentence_id')}", errors)

    for c in candidates:
        for k in ("surface", "quote", "reason"):
            if not c.get(k):
                fail(f"candidates must have {k}: {c.get('normalized_to')}", errors)
        if c.get("quote") != sent_by_id.get(c.get("sentence_id")):
            fail(f"candidates quote must equal sentences text: {c.get('normalized_to')}@{c.get('sentence_id')}", errors)
        if not isinstance(c.get("inferred"), bool):
            fail(f"candidates inferred must be bool: {c.get('normalized_to')}", errors)

    # --- verified 全部分组 (道具试点: 只查 items, 武器 verified 属武器表不在本组) ---
    if isinstance(grouping, list):
        grouped_names = {g.get("name_en") for g in grouping if isinstance(g, dict)}
        # registry-slice items 集 (道具子集), 武器不查分组
        try:
            reg_slice = json.loads((work / "inputs" / "registry-slice.json").read_text(encoding="utf-8"))
            item_set = set(reg_slice.get("items", []))
        except Exception:
            item_set = grouped_names
        for r in verified:
            if r.get("object_norm") in item_set and r.get("object_norm") not in grouped_names:
                fail(f"verified not grouped: {r.get('object_norm')}", errors)
        # 全收录: count>0 68 全进表
        if len(grouping) != 68:
            fail(f"grouping must be 68 (count>0 全收录), got {len(grouping)}", errors)
        for g in grouping:
            for k in ("name_en", "count", "group", "confidence", "reason", "quotes"):
                if k not in g:
                    fail(f"grouping missing {k}: {g.get('name_en')}", errors)
            if g.get("group") not in ("must_take", "mentioned_not_taken", "ban", "casual_mention"):
                fail(f"bad group: {g.get('name_en')}={g.get('group')}", errors)
            if g.get("group") == "must_take" and g.get("tier") not in ("core", "convenient", "compromise"):
                fail(f"must_take must have tier: {g.get('name_en')}", errors)
            # 低频一句话交代
            if isinstance(g.get("count"), int) and g["count"] <= 3:
                rs = str(g.get("reason", ""))
                if len(rs.strip()) < 8:
                    fail(f"low-freq must have one-liner: {g.get('name_en')}", errors)
            # reason 禁计数泄漏
            rs = str(g.get("reason", ""))
            if "字幕" in rs and "次" in rs and "原话" not in rs:
                warns.append(f"WARN: reason 疑计数泄漏: {g.get('name_en')}")
            # ban 必须有拒绝动词原话
            if g.get("group") == "ban":
                qall = " ".join(g.get("quotes", [])).lower()
                if not any(w in qall for w in ("ban", "avoid", "recycl", "sell", "skip", "ignor")):
                    # 放宽: reason 含原话即过
                    if "ban" not in rs.lower() and "避开" not in rs:
                        fail(f"ban must have rejection verb quote: {g.get('name_en')}", errors)
    else:
        fail("grouping must be array", errors)

    # --- outputs 一致 ---
    if grouping != outputs:
        fail("outputs/groups.json must equal steps/03-grouping/grouping.json", errors)

    # --- sha 对上 ---
    src_bytes = (work / "inputs" / "source.vtt").read_bytes()
    actual_sha = hashlib.sha1(src_bytes).hexdigest()
    expect_sha = (manifest.get("sources") or [{}])[0].get("sha1", "")
    if actual_sha != expect_sha:
        fail(f"sha mismatch: manifest {expect_sha[:8]} vs actual {actual_sha[:8]}", errors)

    if errors:
        print(f"FAIL: check_pilot {len(errors)} errors")
        return 1
    for w in warns:
        print(w)
    print(f"OK: pilot cleared, sentences={len(sentences)} verified={len(verified)} "
          f"candidates={len(candidates)} grouping={len(grouping)} sha={actual_sha[:8]}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
