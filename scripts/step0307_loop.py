#!/usr/bin/env python3
"""Step03+07 agent loop (#62, #74 六组): frozen fewshot + discovery/evidence/ranking.

Deterministic-first:
- 固定代码只做: prompt 组装 (任务手册 + 全量整句 + 词汇表/一名/N份evidence/上游结果) /
  输出形状校验 / count 回填 (=len(quotes), agent 不填) / quote_details 重建
  (sentences lookup, 不信 agent) / 名在表 (道具词汇表 wiki-cache items,
  升级名在 ratings term_en, 幻觉即 fail) / 去重 / ban 件禁入 TopN /
  六组覆盖 candidates 自洽 / wishlist+taken 披露码保 / 落盘 (candidates.json + grouping.json +
  per_item/* + ranking.json + priorities.json + 日志).
- agent judgment 只做: discovery 补全 (completeness 归它, slice 已退役) /
  evidence 单件判断 (group建议+quotes+analysis+note, wishlist/taken 须带披露) / grouping-ranking 定六组
  (拿 quote 说话禁数帽, 可推翻 evidence group, 锁/买=拿除非明确不拿) / priority-ranking 定
  upgrades/shop TopN (N 动态由它定, 可推翻 group 建议, 禁断层码切; shop 只禁 ban+T1, wishlist/taken 可进由 agent 定).
- 缺件/编 quote/幻觉名/ban 进 TopN/缺披露即 fail loud, 不回落不补空.

输入:
- fewshot03: prompts/step03-grouping-fewshot.md (FROZEN v4 六组, #74)
- fewshot07: prompts/step07-priorities-fewshot.md (FROZEN)
- sentences: steps/01-sentences/sentences.json
- item vocab: data/wiki-cache.json items (全局唯一, 不读 registry-slice, 不读 02-verbs)
- 07 上游: grouping + ratings + weapons + phases (现场读 steps, 不读旧链)

输出 (03):
- steps/03-grouping/candidates.json: [{name_en, count, quotes, quote_details}]
- steps/03-grouping/per_item/<Safe>.json: evidence 原始 (validated, 无 count)
- steps/03-grouping/ranking.json: {must_take[], wishlist[], taken[], mentioned_not_taken[], ban[], casual_mention[]} (#74 六组)
  每项 {name_en, note} (wishlist note 须含没拿到/未拿到, taken note 须含无下文, 缺披露即 fail)
- steps/03-grouping/grouping.json (+ outputs/groups.json):
  [{name_en, count, group, quotes, analysis, note, quote_details}] (#74 六组, 同上披露)
  - tier/confidence/inferred/has_verb/verb/verb_type/mapped_to/surface_*/reason 全退役 (出现即 fail).

输出 (07):
- steps/07-priorities/ranking.json: agent 原始 {upgrades[], shop[]}
- steps/07-priorities/priorities.json (+ outputs/priorities.json):
  {upgrades[], shop[]} 每项 {name, kind, why, how_to_get, quotes, analysis, quote_details}
  - count/断层/拒绝动词表码逻辑全退役 (出现即 fail 倒在形状层; 码只验非空+子集+ban出局).
"""

from __future__ import annotations

import concurrent.futures
import hashlib
import json
import re
import subprocess
import sys
import time
from collections import defaultdict
from pathlib import Path
from typing import NoReturn

REPO = Path(__file__).resolve().parent.parent

FEWSHOT_03_REL = "prompts/step03-grouping-fewshot.md"
FEWSHOT_07_REL = "prompts/step07-priorities-fewshot.md"
# #74 六组: must_take(拿+战果) / wishlist(想要+追没拿到) / taken(拿/锁无下文) /
# mentioned_not_taken(明确没拿) / ban(拒绝) / casual_mention(纯嘴提无买无锁).
# 显示层: 必拿区=must_take+wishlist(强制没拿到标记), taken 单列必拿与 ban 之间.
VALID_GROUPS = ("must_take", "wishlist", "taken", "mentioned_not_taken", "ban", "casual_mention")
RETIRED_03_FIELDS = ("tier", "confidence", "inferred", "has_verb", "verb", "verb_type",
                     "mapped_to", "surface_verb", "surface_word", "discretion_reason",
                     "reason", "anchors", "score", "kind")
NOTE_MAX_LEN = 120
NOTE_SHORT_RE = re.compile(r'原话["“]([^"”]+)["”]')


def _note_shorts(note: str) -> list[str]:
    return [s.strip() for s in NOTE_SHORT_RE.findall(note or "") if s.strip()]


def _fail_short(who: str, note: str, quotes: list[str]) -> None:
    shorts = _note_shorts(note)
    if not shorts:
        _fail(f"{who} note 缺短引标记 原话\"...\" (人话须带逐字短引, 缺件即 fail)")
    for s in shorts:
        if not any(s in q for q in quotes):
            _fail(f"{who} note 短引须逐字出自 quotes: {s[:60]!r} 改写/编造即 fail")


def _check_disclosure(who: str, group: str, note: str) -> None:
    """#74 披露码保: wishlist 须带没拿到/未拿到, taken 须带无下文, 缺披露即 fail."""
    if group == "wishlist":
        if ("没拿到" not in note) and ("未拿到" not in note):
            _fail(f"{who} wishlist 缺披露即 fail: note 须含“没拿到”/“未拿到” (想要+追但没拿到, 缺件即 fail)")
    elif group == "taken":
        if "无下文" not in note:
            _fail(f"{who} taken 缺披露即 fail: note 须含“无下文” (拿/锁无反悔但无战果, 缺件即 fail)")


def _fail(msg: str) -> NoReturn:
    raise SystemExit(f"step0307-loop FAIL: {msg}")


def load_fewshot03() -> str:
    p = REPO / FEWSHOT_03_REL
    if not p.exists():
        _fail(f"missing {FEWSHOT_03_REL} (frozen fewshot 缺件即 fail, 不回落)")
    txt = p.read_text(encoding="utf-8")
    if "FROZEN" not in txt:
        _fail(f"{FEWSHOT_03_REL} 缺 FROZEN 头 (freeze 完整性 fail)")
    return txt


def load_fewshot07() -> str:
    p = REPO / FEWSHOT_07_REL
    if not p.exists():
        _fail(f"missing {FEWSHOT_07_REL} (frozen fewshot 缺件即 fail, 不回落)")
    txt = p.read_text(encoding="utf-8")
    if "FROZEN" not in txt:
        _fail(f"{FEWSHOT_07_REL} 缺 FROZEN 头 (freeze 完整性 fail)")
    return txt


def load_item_vocab() -> list[str]:
    p = REPO / "data" / "wiki-cache.json"
    if not p.exists():
        _fail("missing data/wiki-cache.json (道具词汇表缺件即 fail)")
    try:
        d = json.loads(p.read_text(encoding="utf-8"))
    except Exception as e:
        _fail(f"wiki-cache.json 读失败: {e!r}")
    items = d.get("items")
    if not isinstance(items, dict) or not items:
        _fail("wiki-cache items 非法 (须为非空对象)")
    names = sorted(items.keys())
    if len(names) < 10:
        _fail(f"items vocab 过小: {len(names)} (疑文件损坏)")
    return names


def build_context(sentences: list[dict], idx: int) -> str:
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


def _quote_lookup(sentences: list[dict]) -> dict[str, list[dict]]:
    mp: dict[str, list[dict]] = defaultdict(list)
    for i, s in enumerate(sentences):
        mp[s["text"]].append({
            "start": s.get("start"), "end": s.get("end"),
            "t": int(s["start_s"]) if s.get("start_s") is not None else None,
            "context": build_context(sentences, i),
        })
    return mp


def _sentences_blob(sentences: list[dict]) -> str:
    lines: list[str] = []
    for s in sentences:
        lines.append(json.dumps({"id": s.get("id"), "text": s.get("text", ""),
                                 "start": s.get("start"), "end": s.get("end"),
                                 "t": s.get("t")}, ensure_ascii=False))
    return "\n".join(lines)


DISCOVERY_CHUNK_SIZE = 40


def chunk_vocab(vocab: list[str], size: int = DISCOVERY_CHUNK_SIZE) -> list[list[str]]:
    """词汇表动态分片 (排序后定长切, 片数=ceil(n/size), 不写死片数)."""
    vs = sorted(set(vocab))
    if not vs:
        _fail("道具词汇表为空 (缺件即 fail)")
    return [vs[i:i + size] for i in range(0, len(vs), size)]


def build_discovery_prompt(sentences: list[dict], chunk: list[str],
                           chunk_id: int, chunk_total: int, fewshot_text: str) -> str:
    if not isinstance(sentences, list) or not sentences:
        _fail("sentences 为空 (缺件即 fail)")
    if not chunk:
        _fail("discovery 分片为空 (缺件即 fail)")
    blob = _sentences_blob(sentences)
    chunk_line = ", ".join(chunk)
    prompt = (
        fewshot_text
        + "\n\n## 该角色全量整句（含 start/end/t，原样全量，不截断）\n\n"
        + "```json\n" + blob + "\n```\n\n"
        + f"## 本批道具名单（分片 {chunk_id + 1}/{chunk_total}，共 {len(chunk)} 件，逐个打勾，一个不许漏）\n\n"
        + chunk_line + "\n\n"
        + "---\n\n# TASK_DISCOVERY（只判本批：逐个打勾收/丢，覆盖本批全部）\n\n"
        + "## 输出契约（只输出一件 JSON 对象，不输出其它文字）\n\n"
        + '{"收": [{"name_en": "<本批一字不差>", "quotes": ["逐字出自上表，去重，≥1"]}], '
        + '"丢": ["<本批一字不差>", ...]}\n\n'
        + "- 本批每件必须出现在收或丢中恰好一次：收+丢==本批名单（机检：缺件/重叠/陌生名即 fail）。\n"
        + "- 收=真聊道具（买/锁/拿/升/ban/skip 语义皆算真聊，判据见上文发现段例子）；丢=路过名词（类别口头/属性词/地图同名/动词同形）。\n"
        + "- name_en 须与本批一字不差；幻觉名即 fail。\n"
        + "- 收的 quotes 须逐字等于上表某条 text，去重，每件 ≥1。编 quote 即 fail。\n"
        + "- 只判本批名单，不判其它；你不输出 count。缺件即 fail，不回落不补空。\n"
    )
    return prompt


def build_evidence_prompt(name_en: str, sentences: list[dict], fewshot_text: str) -> str:
    if not name_en or not isinstance(name_en, str):
        _fail("TASK_ITEM 缺道具名 (缺件即 fail)")
    if not isinstance(sentences, list) or not sentences:
        _fail("sentences 为空 (缺件即 fail)")
    blob = _sentences_blob(sentences)
    prompt = (
        fewshot_text
        + "\n\n## 该角色全量整句（含 start/end/t，原样全量，不截断）\n\n"
        + "```json\n" + blob + "\n```\n\n"
        + "\n\n---\n\n# TASK_EVIDENCE（本轮只判这一件道具，其它一律不判）\n\n"
        + f"TASK_ITEM: {name_en}\n\n"
        + "## 输出契约（只输出一件 JSON 对象，不输出其它文字）\n\n"
        + '{"name_en": "<与 TASK_ITEM 一字不差>", "group": "must_take/wishlist/taken/mentioned_not_taken/ban/casual_mention（建议，六组 #74）", '
        + '"quotes": ["逐字出自上表，去重，非空"], '
        + '"analysis": "来源→机制→分组", '
        + '"note": "≤120字人话+短引（wishlist 须含没拿到/未拿到，taken 须含无下文）"}\n\n'
        + "- name_en 须与 TASK_ITEM 一字不差；幻觉名即 fail。\n"
        + "- quotes 须逐字等于上表某条 text，去重，非空；空证据即 fail（道具无 `-` 档）。编 quote 即 fail。\n"
        + "- analysis 写全过程（来源→机制→分组；锁/买=拿除非明确不拿 skip/recycle/sell/ban）。\n"
        + "- note ≤120 字，人话 + 短引（短引须出自本条 quotes 逐字；wishlist 须披露没拿到/未拿到，taken 须披露无下文，缺披露即 fail）。\n"
        + "- 你不输出 count。缺件即 fail，不回落不补空。\n"
    )
    return prompt


def build_grouping_ranking_prompt(sentences: list[dict], evidences: list[dict],
                                  fewshot_text: str) -> str:
    if not isinstance(sentences, list) or not sentences:
        _fail("sentences 为空 (缺件即 fail)")
    if not evidences:
        _fail("evidences 为空 (缺件即 fail)")
    blob = _sentences_blob(sentences)
    ev_blob = json.dumps(evidences, ensure_ascii=False, indent=2)
    names = ", ".join(e.get("name_en", "") for e in evidences)
    prompt = (
        fewshot_text
        + "\n\n## 该角色全量整句（含 start/end/t，原样全量，不截断）\n\n"
        + "```json\n" + blob + "\n```\n\n"
        + "## N 份 evidence（通览，全量，不截断）\n\n"
        + "```json\n" + ev_blob + "\n```\n\n"
        + "\n\n---\n\n# TASK_GROUPING（只定六组 #74，不编 quote；Top1 意图由你保）\n\n"
        + f"候选名单（须全部分组，一件不丢）: {names}\n\n"
        + "## 输出契约（只输出一件 JSON 对象，不输出其它文字）\n\n"
        + '{"must_take": [{"name_en": "<候选一字不差>", "note": "≤120字定稿人话+短引"}], '
        + '"wishlist": [{"name_en": "...", "note": "...须含没拿到/未拿到..."}], '
        + '"taken": [{"name_en": "...", "note": "...须含无下文..."}], '
        + '"mentioned_not_taken": [{"name_en": "...", "note": "..."}], '
        + '"ban": [{"name_en": "...", "note": "..."}], '
        + '"casual_mention": [{"name_en": "...", "note": "..."}]}\n\n'
        + "- 六组须覆盖候选名单（一把不多一把不少）；幻觉名即 fail。\n"
        + "- 可推翻 evidence group 建议；切分拿 quote 说话，禁数帽；锁/买=拿除非明确不拿（skip/recycle/sell/ban 为反悔）。\n"
        + "- note 每条 ≤120 字，人话 + 短引（短引须出自对应 evidence quotes 逐字；wishlist 须披露没拿到/未拿到，taken 须披露无下文，缺披露即 fail）。\n"
        + "- 你不输出 quotes/analysis/count（只定 group+note）。缺件即 fail。\n"
    )
    return prompt


def build_priority_ranking_prompt(sentences: list[dict], grouping: list[dict],
                                  ratings: list[dict], weapons: dict,
                                  phases: list[dict], fewshot_text: str) -> str:
    if not isinstance(sentences, list) or not sentences:
        _fail("sentences 为空 (缺件即 fail)")
    if not grouping:
        _fail("grouping 为空 (缺件即 fail)")
    if not ratings:
        _fail("ratings 为空 (缺件即 fail)")
    blob = _sentences_blob(sentences)
    grp_blob = json.dumps(grouping, ensure_ascii=False, indent=2)
    rat_blob = json.dumps([{"term_en": r.get("term_en"), "rating": r.get("rating"),
                            "count": r.get("count")} for r in ratings
                           if isinstance(r, dict)], ensure_ascii=False, indent=2)
    w_blob = json.dumps(weapons, ensure_ascii=False)[:4000]
    ph_blob = json.dumps([{"phase": p.get("phase"), "waves": p.get("waves")}
                          for p in (phases or []) if isinstance(p, dict)],
                         ensure_ascii=False, indent=2)[:4000]
    prompt = (
        fewshot_text
        + "\n\n## 该角色全量整句（含 start/end/t，原样全量，不截断）\n\n"
        + "```json\n" + blob + "\n```\n\n"
        + "## grouping 六组 #74（建议，可推翻）\n\n```json\n" + grp_blob + "\n```\n\n"
        + "## 04 ratings（升级候选只认 term_en）\n\n```json\n" + rat_blob + "\n```\n\n"
        + "## 05 weapons（备查：T1 不重复进商店）\n\n```json\n" + w_blob + "\n```\n\n"
        + "## 06 phases（节奏备查，空段跳过）\n\n```json\n" + ph_blob + "\n```\n\n"
        + "\n\n---\n\n# TASK_PRIORITY（只定 TopN，不编 quote；N 由你定，ban 永不出局）\n\n"
        + "## 输出契约（只输出一件 JSON 对象，不输出其它文字）\n\n"
        + '{"upgrades": [{"name": "<ratings term_en 一字不差>", "why": "≤120字人话+短引", '
        + '"how_to_get": "≤120字人话", "quotes": ["逐字，去重，非空"], '
        + '"analysis": "来源→机制→TopN"}], '
        + '"shop": [{"name": "<grouping candidates 一字不差，非 ban>", "why": "≤120字人话+短引", '
        + '"how_to_get": "≤120字人话", "quotes": ["逐字，去重，非空"], '
        + '"analysis": "来源→分组→TopN"}]}\n\n'
        + "- upgrades ≥1 且 shop ≥1（Top1 意图由你保，码只验非空，不验断层）。\n"
        + "- shop 须出自 grouping candidates 且不在 ban 组；ban 件进 TopN 即 fail。\n"
        + "- upgrades 须出自 ratings term_en；幻觉名即 fail。\n"
        + "- quotes 须逐字等于全量整句某条 text，去重，非空；编 quote 即 fail。\n"
        + "- why 须带短引（须逐字出自本条 quotes）；how_to_get 原话数字不丢，未提空出不脑补。\n"
        + "- 你不输出 count。缺件即 fail，不回落不补空。\n"
    )
    return prompt


def validate_discovery_chunk(data: dict, chunk_items: list[str],
                             sentences: list[dict]) -> dict:
    """单分片打勾校验: 收/丢恰好覆盖本批 (缺件/重叠/陌生名即 fail)."""
    if not isinstance(data, dict):
        _fail(f"discovery 输出须为 JSON 对象, got {type(data)}")
    for f in RETIRED_03_FIELDS:
        if f in data:
            _fail(f"discovery 字段 {f} 已退役 (#62, 出现即 fail)")
    if "count" in data:
        _fail("discovery 不许填 count (只活代码)")
    for k in ("收", "丢"):
        if k not in data:
            _fail(f"discovery 缺 {k} (缺件即 fail, 不补空)")
    got = data["收"]
    dropped = data["丢"]
    if not isinstance(got, list) or not isinstance(dropped, list):
        _fail("discovery 收/丢须为数组")
    if any(not isinstance(x, str) for x in dropped):
        _fail("discovery 丢须为字符串数组")
    chunk_set = set(chunk_items)
    sent_texts = {s.get("text") for s in sentences if isinstance(s, dict)}
    seen: set[str] = set()
    out_got: list[dict] = []
    for c in got:
        if not isinstance(c, dict):
            _fail("discovery 收条目须为对象")
        for k in ("name_en", "quotes"):
            if k not in c:
                _fail(f"discovery 收条目缺 {k} (缺件即 fail)")
        name = c.get("name_en")
        if not isinstance(name, str) or name not in chunk_set:
            _fail(f"discovery 幻觉名即 fail: {name!r} 不在本批名单 (逐字)")
        if name in seen:
            _fail(f"discovery 收/丢须去重: {name!r}")
        seen.add(name)
        qs = c.get("quotes")
        if not isinstance(qs, list) or not qs or any(not isinstance(q, str) for q in qs):
            _fail(f"discovery {name} quotes 须为非空字符串数组 (空证据即 fail)")
        if len(qs) != len(set(qs)):
            _fail(f"discovery {name} quotes 须去重")
        for q in qs:
            if q not in sent_texts:
                _fail(f"discovery {name} 编 quote 即 fail: {q[:60]!r} 不在整句内 (逐字)")
        out_got.append({"name_en": name, "quotes": list(qs)})
    for name in dropped:
        if name not in chunk_set:
            _fail(f"discovery 丢陌生名即 fail: {name!r} 不在本批名单")
        if name in seen:
            _fail(f"discovery 收/丢须互斥: {name!r}")
        seen.add(name)
    if seen != chunk_set:
        _fail(f"discovery 收+丢须==本批名单 (缺件即 fail): 缺 {sorted(chunk_set - seen)}")
    return {"收": out_got, "丢": sorted(dropped)}


def validate_evidence(data: dict, name_en: str, sentences: list[dict]) -> dict:
    if not isinstance(data, dict):
        _fail(f"{name_en} evidence 输出须为 JSON 对象, got {type(data)}")
    if "count" in data:
        _fail(f"{name_en} evidence 不许填 count (只活代码)")
    for f in RETIRED_03_FIELDS:
        if f in data:
            _fail(f"{name_en} 字段 {f} 已退役 (#62, 出现即 fail)")
    for k in ("name_en", "group", "quotes", "analysis", "note"):
        if k not in data:
            _fail(f"{name_en} evidence 缺 {k} (缺件即 fail, 不补空)")
    if data.get("name_en") != name_en:
        _fail(f"evidence name_en 须一字不差: 期望 {name_en!r}, 实得 {data.get('name_en')!r}")
    if data.get("group") not in VALID_GROUPS:
        _fail(f"{name_en} evidence group 须为六组之一 #74, got {data.get('group')!r}")
    qs = data.get("quotes")
    if not isinstance(qs, list) or not qs or any(not isinstance(q, str) for q in qs):
        _fail(f"{name_en} evidence 空证据即 fail (quotes 须非空)")
    if len(qs) != len(set(qs)):
        _fail(f"{name_en} evidence quotes 须去重")
    sent_texts = {s.get("text") for s in sentences if isinstance(s, dict)}
    for q in qs:
        if q not in sent_texts:
            _fail(f"{name_en} 编 quote 即 fail: {q[:60]!r} 不在整句内 (逐字)")
    ana = data.get("analysis")
    if not isinstance(ana, str) or len(ana.strip()) < 4:
        _fail(f"{name_en} evidence analysis 须为非空人话 (缺件即 fail)")
    note = data.get("note")
    if not isinstance(note, str) or not note.strip():
        _fail(f"{name_en} evidence note 缺件即 fail")
    if len(note) > NOTE_MAX_LEN:
        _fail(f"{name_en} evidence note 须≤{NOTE_MAX_LEN}字, got {len(note)}")
    _fail_short(f"{name_en} evidence", note, [q for q in qs if isinstance(q, str)])
    _check_disclosure(f"{name_en} evidence", data.get("group", ""), note)
    return {"name_en": name_en, "group": data.get("group"),
            "quotes": list(qs), "analysis": str(ana).strip(), "note": str(note).strip()}


def validate_grouping_ranking(data: dict, candidate_names: list[str],
                              evidences: list[dict]) -> dict:
    if not isinstance(data, dict):
        _fail(f"grouping-ranking 输出须为 JSON 对象, got {type(data)}")
    for f in RETIRED_03_FIELDS:
        if f in data:
            _fail(f"grouping-ranking 字段 {f} 已退役 (#62, 出现即 fail)")
    if "count" in data:
        _fail("grouping-ranking 不许填 count (只活代码)")
    for k in VALID_GROUPS:
        if k not in data:
            _fail(f"grouping-ranking 缺 {k} (缺件即 fail)")
        if not isinstance(data[k], list):
            _fail(f"grouping-ranking {k} 须为数组")
    ev_by = {e.get("name_en"): e for e in evidences if isinstance(e, dict)}
    seen: set[str] = set()
    out: dict[str, list[dict]] = {k: [] for k in VALID_GROUPS}
    for grp in VALID_GROUPS:
        for e in data[grp]:
            if not isinstance(e, dict):
                _fail(f"grouping-ranking {grp} 条目须为对象")
            for k in ("name_en", "note"):
                if k not in e:
                    _fail(f"grouping-ranking {grp} 缺 {k} (缺件即 fail)")
            name = e.get("name_en")
            note = e.get("note")
            if name in seen:
                _fail(f"grouping-ranking {name!r} 重复 (六组须==candidates 去重)")
            seen.add(name)
            if name not in set(candidate_names):
                _fail(f"grouping-ranking 幻觉名即 fail: {name!r} 不在 candidates 内")
            if name not in ev_by:
                _fail(f"grouping-ranking {name!r} 无对应 evidence (缺件即 fail)")
            if not isinstance(note, str) or not note.strip():
                _fail(f"grouping-ranking {name} note 缺件即 fail (意图保, 码只查非空)")
            if len(note) > NOTE_MAX_LEN:
                _fail(f"grouping-ranking {name} note 须≤{NOTE_MAX_LEN}字, got {len(note)}")
            _evq = ev_by.get(name, {}).get("quotes", [])
            _fail_short(f"grouping-ranking {name}", note,
                        [q for q in _evq if isinstance(q, str)])
            _check_disclosure(f"grouping-ranking {name}", grp, note)
            out[grp].append({"name_en": name, "note": str(note).strip()})
    if set(seen) != set(candidate_names):
        _fail(f"grouping-ranking 六组须==candidates 自洽: 期望 {sorted(candidate_names)}, 实得 {sorted(seen)}")
    return out


def validate_priority(data: dict, sentences: list[dict],
                      grouping: list[dict], ratings: list[dict]) -> dict:
    if not isinstance(data, dict):
        _fail(f"priority 输出须为 JSON 对象, got {type(data)}")
    if "count" in data:
        _fail("priority 不许填 count (只活代码)")
    for k in ("upgrades", "shop"):
        if k not in data:
            _fail(f"priority 缺 {k} (缺件即 fail)")
    ups = data["upgrades"]
    shs = data["shop"]
    if not isinstance(ups, list) or not ups:
        _fail("priority upgrades 须为非空数组 (N 动态由 agent 定, 码只验非空)")
    if not isinstance(shs, list) or not shs:
        _fail("priority shop 须为非空数组 (N 动态由 agent 定, 码只验非空)")
    sent_texts = {s.get("text") for s in sentences if isinstance(s, dict)}
    cand_names = {g.get("name_en") for g in grouping if isinstance(g, dict)}
    ban_names = {g.get("name_en") for g in grouping
                 if isinstance(g, dict) and g.get("group") == "ban"}
    rating_names = {r.get("term_en") for r in ratings if isinstance(r, dict)}
    seen: set[str] = set()
    out_ups: list[dict] = []
    out_shop: list[dict] = []
    for name, kind, arr, out_arr, allowed in (
            ("upgrades", "upgrade", ups, out_ups, rating_names),
            ("shop", "shop", shs, out_shop, cand_names)):
        for e in arr:
            if not isinstance(e, dict):
                _fail(f"priority {name} 条目须为对象")
            for k in ("name", "why", "how_to_get", "quotes", "analysis"):
                if k not in e:
                    _fail(f"priority {name} 缺 {k} (缺件即 fail, 不补空)")
            nm = e.get("name")
            if nm in seen:
                _fail(f"priority {nm!r} 重复 (upgrades+shop 去重)")
            seen.add(nm)
            if nm not in allowed:
                _fail(f"priority 幻觉名即 fail: {nm!r} 不在{'ratings' if name == 'upgrades' else 'grouping candidates'}内")
            if name == "shop" and nm in ban_names:
                _fail(f"priority ban 件禁入 TopN: {nm!r} (拿 quote 说话也不许进)")
            qs = e.get("quotes")
            if not isinstance(qs, list) or not qs or any(not isinstance(q, str) for q in qs):
                _fail(f"priority {nm} 空证据即 fail (quotes 须非空)")
            if len(qs) != len(set(qs)):
                _fail(f"priority {nm} quotes 须去重")
            for q in qs:
                if q not in sent_texts:
                    _fail(f"priority {nm} 编 quote 即 fail: {q[:60]!r} 不在整句内 (逐字)")
            why = e.get("why")
            how = e.get("how_to_get")
            ana = e.get("analysis")
            if not isinstance(why, str) or len(why.strip()) < 4:
                _fail(f"priority {nm} why 缺件即 fail")
            if len(why) > 300:
                _fail(f"priority {nm} why 过长 (须≤300), got {len(why)}")
            if not isinstance(how, str) or len(how.strip()) < 2:
                _fail(f"priority {nm} how_to_get 缺件即 fail")
            if not isinstance(ana, str) or len(ana.strip()) < 4:
                _fail(f"priority {nm} analysis 缺件即 fail")
            _fail_short(f"priority {nm}", why, [q for q in qs if isinstance(q, str)])
            out_arr.append({"name": nm, "kind": kind, "why": str(why).strip(),
                            "how_to_get": str(how).strip(),
                            "quotes": list(qs), "analysis": str(ana).strip()})
    return {"upgrades": out_ups, "shop": out_shop}


def _safe_term(name_en: str) -> str:
    return re.sub(r"[^A-Za-z0-9]+", "_", name_en).strip("_")


def _extract_json(text: str, who: str) -> dict:
    t = text.strip()
    if "```" in t:
        m = re.search(r"```(?:json)?\s*(\{.*?\})\s*```", t, re.DOTALL)
        if m:
            t = m.group(1).strip()
    if not t.startswith("{"):
        i = t.find("{")
        j = t.rfind("}")
        if i >= 0 and j > i:
            t = t[i:j + 1]
    try:
        data = json.loads(t)
    except Exception as e:
        _fail(f"{who} 输出非 JSON 即 fail: {e}; head={text[:120]!r}")
        raise  # pragma: no cover
    if not isinstance(data, dict):
        _fail(f"{who} 输出须为对象")
    return data  # type: ignore[return-value]


def _spawn_agent_once(workdir: Path, prompt_text: str, output_rel: str,
                      log_path: Path, timeout: float = 1800.0,
                      model=None, thinking: str = "medium") -> Path:
    import queue
    import threading
    import shutil as _sh

    def build_agent_cmd() -> list[str]:
        base = ["--mode", "rpc", "--no-session",
                "--no-skills", "--no-extensions", "--no-prompt-templates",
                "--no-context-files", "--tools", "read,write,bash",
                "--thinking", thinking]
        if model:
            base += ["--model", model]
        found = _sh.which("pi")
        if found:
            return [found, *base]
        for cand in ("F:/Pi/CLI/pi.cmd", "F:/Pi/CLI/pi", "pi.cmd"):
            if Path(cand).exists():
                return [cand, *base]
        return ["pi", *base]

    def _sha1(s: str) -> str:
        return hashlib.sha1(s.encode("utf-8")).hexdigest()

    start_wall = time.time()
    out_path = workdir / output_rel
    cmd = build_agent_cmd()
    log_path.parent.mkdir(parents=True, exist_ok=True)
    with open(log_path, "a", encoding="utf-8") as lg:
        lg.write(f"[{time.time():.3f}] spawn cwd={workdir} cmd={' '.join(cmd)}\n")
        lg.write(f"prompt_len={len(prompt_text)} prompt_sha={_sha1(prompt_text)}\n")
    try:
        proc = subprocess.Popen(
            cmd, cwd=str(workdir), stdin=subprocess.PIPE, stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT, text=True, encoding="utf-8", errors="replace", bufsize=1)
    except Exception as e:
        raise RuntimeError(f"transient: spawn failed: {e!r}")
    q: queue.Queue[str | None] = queue.Queue()
    raw_lines: list[str] = []

    def _reader() -> None:
        try:
            assert proc.stdout is not None
            for line in proc.stdout:
                raw_lines.append(line)
                q.put(line)
        except Exception:
            pass
        finally:
            q.put(None)

    rt = threading.Thread(target=_reader, daemon=True)
    rt.start()
    try:
        assert proc.stdin is not None
        req = {"id": "step0307-1", "type": "prompt", "message": prompt_text}
        try:
            proc.stdin.write(json.dumps(req, ensure_ascii=False) + "\n")
            proc.stdin.flush()
        except Exception as e:
            raise RuntimeError(f"transient: stdin write failed: {e!r}")
        settled = False
        deadline = start_wall + timeout
        import queue as _qq
        while time.time() < deadline:
            try:
                line = q.get(timeout=max(1.0, deadline - time.time()))
            except _qq.Empty:
                continue
            if line is None:
                break
            buf = line.strip()
            if not buf:
                continue
            try:
                evt = json.loads(buf)
            except Exception as e:
                raise RuntimeError(f"transient: JSONL parse failed: {e!r}")
            if isinstance(evt, dict) and evt.get("type") == "agent_settled":
                settled = True
                break
        if not settled:
            raise RuntimeError(f"transient: liveness timeout {timeout:.0f}s")
    finally:
        try:
            with open(str(log_path) + ".jsonl", "a", encoding="utf-8") as jf:
                for ln in raw_lines:
                    jf.write(ln if ln.endswith("\n") else ln + "\n")
        except Exception:
            pass
        try:
            try:
                if proc.stdin is not None:
                    proc.stdin.close()
            except Exception:
                pass
            proc.terminate()
            try:
                proc.wait(timeout=10)
            except Exception:
                try:
                    proc.kill()
                except Exception:
                    pass
        except Exception:
            pass
    for _ in range(50):
        if out_path.exists():
            break
        time.sleep(0.1)
    if not out_path.exists():
        raise RuntimeError(f"missing: {output_rel} after agent_settled (缺件, 不补空)")
    return out_path


def _run_single_with_retry(workdir: Path, prompt: str, output_rel: str,
                           log_path: Path, parse_validate,
                           timeout: float, model, thinking: str,
                           per_path: Path, agent_fn=None):
    transient_left = 2
    format_left = 1
    backoff = (5.0, 15.0)
    bi = 0
    while True:
        try:
            if agent_fn is not None:
                try:
                    data = agent_fn(prompt)
                except SystemExit:
                    raise
                except Exception as e:
                    _fail(f"agent_fn fail: {e!r}")
                parsed = parse_validate(data)
                per_path.write_text(json.dumps(parsed, ensure_ascii=False, indent=2) + "\n",
                                    encoding="utf-8")
                return parsed
            _spawn_agent_once(workdir, prompt, output_rel, log_path,
                              timeout=timeout, model=model, thinking=thinking)
        except RuntimeError as e:
            msg = str(e)
            if msg.startswith("transient:"):
                if transient_left <= 0:
                    _fail(f"transient top: {msg}")
                wait = backoff[bi] if bi < len(backoff) else 15.0
                bi += 1
                transient_left -= 1
                time.sleep(wait)
                continue
            else:
                if format_left <= 0:
                    _fail(f"missing top: {msg}")
                format_left -= 1
                continue
        try:
            txt = per_path.read_text(encoding="utf-8")
            cand = _extract_json(txt, output_rel)
            parsed = parse_validate(cand)
            per_path.write_text(json.dumps(parsed, ensure_ascii=False, indent=2) + "\n",
                                encoding="utf-8")
            return parsed
        except SystemExit:
            if format_left <= 0:
                raise
            format_left -= 1
            try:
                if per_path.exists():
                    per_path.unlink()
            except Exception:
                pass
            continue


def run_step03_loop(workdir, sentences, agent_fn=None, timeout: float = 1800.0,
                    force: bool = False, max_workers: int = 4, stagger: float = 5.0,
                    model=None, thinking: str = "medium"):
    """03 三段调度: discovery(串行) → evidence×N(并行) → grouping-ranking(串行).

    agent_fn: 测试注入. 为 None 时走真 RPC spawn.
      - discovery: agent_fn("discovery", None, prompt) -> dict
      - evidence: agent_fn("evidence", name_en, prompt) -> dict
      - grouping-ranking: agent_fn("grouping-ranking", None, prompt) -> dict
    """
    vocab = load_item_vocab()
    fewshot = load_fewshot03()
    outdir = workdir / "steps" / "03-grouping"
    per_dir = outdir / "per_item"
    outdir.mkdir(parents=True, exist_ok=True)
    per_dir.mkdir(parents=True, exist_ok=True)
    # fewshot 运行快照进工作区 (审计只读工作区约定路径; 快照与 repo FROZEN 文件逐字节一致, check 验相等)
    (outdir / "fewshot.md").write_text(fewshot, encoding="utf-8", newline="\n")

    # ---- discovery 打勾 (分片并行, 逐个 verdict, 缺件即 fail) ----
    # 词汇表动态分片 (40/批, 片数=ceil(n/40)); 每片独立 agent 逐个打勾收/丢;
    # 合并验全表覆盖 (收+丢==vocab). evidence 只对收跑.
    disc_path = outdir / "candidates.json"
    chunks = chunk_vocab(vocab)

    def _do_disc(i: int, ch: list[str]):
        safe_i = f"chunk-{i}"
        per_path = outdir / f"discovery-{safe_i}.json"
        prompt = build_discovery_prompt(sentences, ch, i, len(chunks), fewshot)

        def _parse(d):
            return validate_discovery_chunk(d, ch, sentences)

        if per_path.exists() and not force:
            try:
                return _parse(json.loads(per_path.read_text(encoding="utf-8")))
            except SystemExit:
                raise
            except Exception:
                pass
        full_prompt = (prompt
                       + f"\n\n只写相对路径 `steps/03-grouping/discovery-{safe_i}.json`，"
                         f"禁 `..` 与绝对盘符。文件落盘为必须（不写文件即缺件 fail）；"
                         f"“只输出一件 JSON”指文件内容格式，写完文件后再输出同一 JSON。\n")
        if agent_fn is not None:
            try:
                raw_d = agent_fn("discovery", i, prompt)
            except TypeError:
                _fail("agent_fn 须为三参 (kind, name_en, prompt)")
            except SystemExit:
                raise
            except Exception as e:
                _fail(f"discovery chunk{i} agent_fn fail: {e!r}")
            parsed = _parse(raw_d)
            per_path.write_text(json.dumps(parsed, ensure_ascii=False, indent=2) + "\n",
                                encoding="utf-8")
            return parsed
        log_path = outdir / f"agent-discovery-{safe_i}.log"
        out_rel = f"steps/03-grouping/discovery-{safe_i}.json"
        if per_path.exists() and force:
            try:
                per_path.unlink()
            except Exception:
                pass
        return _run_single_with_retry(workdir, full_prompt, out_rel, log_path,
                                      _parse, timeout, model, thinking, per_path)

    disc_chunks: list[dict] = []
    if agent_fn is not None:
        for _i, _ch in enumerate(chunks):
            disc_chunks.append(_do_disc(_i, _ch))
    else:
        with concurrent.futures.ThreadPoolExecutor(max_workers=max_workers) as ex:
            dfuts = {ex.submit(_do_disc, _i, _ch): _i for _i, _ch in enumerate(chunks)}
            by_i: dict[int, dict] = {}
            for dfut in concurrent.futures.as_completed(dfuts):
                by_i[dfuts[dfut]] = dfut.result()
            disc_chunks = [by_i[_i] for _i in range(len(chunks))]
            time.sleep(0)

    # 合并: 收 union → candidates; 全表覆盖机检 (收+丢==vocab, 缺件即 fail)
    seen_got: dict[str, list[str]] = {}
    seen_drop: set[str] = set()
    for dc in disc_chunks:
        for c in dc.get("收", []):
            if c["name_en"] in seen_got:
                _fail(f"discovery 跨片重复: {c['name_en']!r}")
            seen_got[c["name_en"]] = list(c["quotes"])
        for n in dc.get("丢", []):
            if n in seen_got or n in seen_drop:
                _fail(f"discovery 跨片重复: {n!r}")
            seen_drop.add(n)
    if set(seen_got) | seen_drop != set(vocab):
        _fail(f"discovery 收+丢须==全表 (缺件即 fail): 缺 {sorted(set(vocab) - set(seen_got) - seen_drop)}")
    disc_validated = [{"name_en": n, "quotes": seen_got[n]} for n in sorted(seen_got)]
    (outdir / "discovery.json").write_text(
        json.dumps({"chunk_size": DISCOVERY_CHUNK_SIZE,
                    "chunks": [list(ch) for ch in chunks],
                    "收": sorted(seen_got), "丢": sorted(seen_drop)},
                   ensure_ascii=False, indent=2) + "\n", encoding="utf-8")

    # discovery 回填 candidates.json (code: count=len(quotes) + quote_details)
    qlookup = _quote_lookup(sentences)
    candidates: list[dict] = []
    for c in disc_validated:
        qs: list[str] = []
        for q in c.get("quotes", []):
            if q not in qs:
                qs.append(q)
        details = []
        for q in qs:
            hits = qlookup.get(q, [])
            h = hits[0] if hits else {"start": None, "end": None, "t": None,
                                      "context": q[:300]}
            if h.get("start") is not None and not isinstance(h.get("t"), int):
                _fail(f"discovery {c.get('name_en')} quote_details t 非法: {q[:40]!r}")
            details.append({"quote": q, "start": h["start"], "end": h["end"],
                            "t": h["t"], "context": h["context"]})
        candidates.append({"name_en": c["name_en"], "count": len(qs),
                           "quotes": qs, "quote_details": details})
    candidates = sorted(candidates, key=lambda x: x["name_en"])
    disc_path.write_text(json.dumps(candidates, ensure_ascii=False, indent=2) + "\n",
                         encoding="utf-8")
    candidate_names = [c["name_en"] for c in candidates]

    # ---- evidence×N (并行) ----
    def _do_one(name_en: str):
        safe = _safe_term(name_en)
        per_path = per_dir / f"{safe}.json"
        ev_prompt = build_evidence_prompt(name_en, sentences, fewshot_text=fewshot)

        def _parse_ev(d):
            return validate_evidence(d, name_en, sentences)

        if per_path.exists() and not force:
            try:
                cand = json.loads(per_path.read_text(encoding="utf-8"))
                return _parse_ev(cand)
            except SystemExit:
                raise
            except Exception:
                pass
        full_prompt = (ev_prompt
                       + f"\n\n只写相对路径 `steps/03-grouping/per_item/{safe}.json`，"
                         f"禁 `..` 与绝对盘符。\n")
        if agent_fn is not None:
            try:
                raw_e = agent_fn("evidence", name_en, ev_prompt)
            except SystemExit:
                raise
            except Exception as e:
                _fail(f"evidence {name_en} agent_fn fail: {e!r}")
            parsed = _parse_ev(raw_e)
            per_path.write_text(json.dumps(parsed, ensure_ascii=False, indent=2) + "\n",
                                encoding="utf-8")
            return parsed
        log_path = outdir / f"agent-evidence-{safe}.log"
        out_rel = f"steps/03-grouping/per_item/{safe}.json"
        if per_path.exists() and force:
            try:
                per_path.unlink()
            except Exception:
                pass
        return _run_single_with_retry(workdir, full_prompt, out_rel, log_path,
                                      _parse_ev, timeout, model, thinking, per_path)

    evidences: list[dict] = []
    if agent_fn is not None:
        for n in candidate_names:
            evidences.append(_do_one(n))
    else:
        with concurrent.futures.ThreadPoolExecutor(max_workers=max_workers) as ex:
            futs = {}
            for n in candidate_names:
                futs[ex.submit(_do_one, n)] = n
                time.sleep(stagger)
            by_name: dict[str, dict] = {}
            for fut in concurrent.futures.as_completed(futs):
                n = futs[fut]
                by_name[n] = fut.result()
            evidences = [by_name[n] for n in candidate_names]

    # ---- grouping-ranking (串行) ----
    rank_prompt = build_grouping_ranking_prompt(sentences, evidences, fewshot)
    rank_path = outdir / "ranking.json"
    rank_log = outdir / "agent-ranking.log"
    rank_rel = "steps/03-grouping/ranking.json"

    def _parse_rank(d):
        return validate_grouping_ranking(d, candidate_names, evidences)

    if rank_path.exists() and not force:
        try:
            cand = json.loads(rank_path.read_text(encoding="utf-8"))
            ranking = _parse_rank(cand)
        except SystemExit:
            raise
        except Exception:
            ranking = None  # type: ignore
    else:
        ranking = None  # type: ignore

    if ranking is None:
        full_rank_prompt = (rank_prompt
                            + f"\n\n只写相对路径 `{rank_rel}`，禁 `..` 与绝对盘符。\n")
        if agent_fn is not None:
            try:
                raw_r = agent_fn("grouping-ranking", None, rank_prompt)
            except SystemExit:
                raise
            except Exception as e:
                _fail(f"grouping-ranking agent_fn fail: {e!r}")
            ranking = _parse_rank(raw_r)
            rank_path.write_text(json.dumps(ranking, ensure_ascii=False, indent=2) + "\n",
                                 encoding="utf-8")
        else:
            if rank_path.exists() and force:
                try:
                    rank_path.unlink()
                except Exception:
                    pass
            ranking = _run_single_with_retry(workdir, full_rank_prompt, rank_rel,
                                             rank_log, _parse_rank,
                                             timeout, model, thinking, rank_path)

    # ---- 合并落盘 (code only) ----
    ev_by = {e["name_en"]: e for e in evidences}
    ql = _quote_lookup(sentences)
    rank_by: dict[str, tuple[str, str]] = {}
    for grp in VALID_GROUPS:
        for r in ranking.get(grp, []):
            rank_by[r["name_en"]] = (grp, r.get("note", ""))
    if set(rank_by.keys()) != set(candidate_names):
        _fail(f"合并自洽 fail: ranking 六组须==candidates: 期望 {sorted(candidate_names)}, 实得 {sorted(rank_by.keys())}")
    grouping: list[dict] = []
    for name in sorted(candidate_names):
        grp, note = rank_by[name]
        ev = ev_by.get(name)
        if ev is None:
            _fail(f"合并缺 evidence: {name!r} (缺件即 fail)")
        qs: list[str] = []
        for q in ev.get("quotes", []):
            if q not in qs:
                qs.append(q)
        details = []
        for q in qs:
            hits = ql.get(q, [])
            h = hits[0] if hits else {"start": None, "end": None, "t": None,
                                      "context": q[:300]}
            if h.get("start") is not None and not isinstance(h.get("t"), int):
                _fail(f"{name} quote_details t 非法: {q[:40]!r}")
            details.append({"quote": q, "start": h["start"], "end": h["end"],
                            "t": h["t"], "context": h["context"]})
        grouping.append({"name_en": name, "count": len(qs), "group": grp,
                         "quotes": qs, "analysis": str(ev.get("analysis", "")).strip(),
                         "note": str(note).strip(), "quote_details": details})
    grouping = sorted(grouping, key=lambda x: x["name_en"])
    (outdir / "grouping.json").write_text(
        json.dumps(grouping, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    (workdir / "outputs").mkdir(parents=True, exist_ok=True)
    (workdir / "outputs" / "groups.json").write_text(
        json.dumps(grouping, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    return grouping


def run_step07_loop(workdir, sentences, grouping, ratings, weapons, phases,
                    agent_fn=None, timeout: float = 1800.0, force: bool = False,
                    model=None, thinking: str = "medium"):
    """07 单 ranking agent: 通览 grouping+ratings+weapons+phases+全量整句 → upgrades/shop TopN.

    agent_fn: 测试注入. 为 None 时走真 RPC spawn.
      - agent_fn("priority-ranking", None, prompt) -> dict
    """
    fewshot = load_fewshot07()
    outdir = workdir / "steps" / "07-priorities"
    outdir.mkdir(parents=True, exist_ok=True)
    (outdir / "fewshot.md").write_text(fewshot, encoding="utf-8", newline="\n")

    prompt = build_priority_ranking_prompt(sentences, grouping, ratings, weapons or {},
                                           phases or [], fewshot)
    rank_path = outdir / "ranking.json"
    rank_log = outdir / "agent-ranking.log"
    rank_rel = "steps/07-priorities/ranking.json"

    def _parse(d):
        return validate_priority(d, sentences, grouping, ratings)

    if rank_path.exists() and not force:
        try:
            cand = json.loads(rank_path.read_text(encoding="utf-8"))
            ranking = _parse(cand)
        except SystemExit:
            raise
        except Exception:
            ranking = None  # type: ignore
    else:
        ranking = None  # type: ignore

    if ranking is None:
        full_prompt = (prompt + f"\n\n只写相对路径 `{rank_rel}`，禁 `..` 与绝对盘符。\n")
        if agent_fn is not None:
            try:
                raw_r = agent_fn("priority-ranking", None, prompt)
            except TypeError:
                _fail("agent_fn 须为三参 (kind, name_en, prompt)")
            except SystemExit:
                raise
            except Exception as e:
                _fail(f"priority-ranking agent_fn fail: {e!r}")
            ranking = _parse(raw_r)
            rank_path.write_text(json.dumps(ranking, ensure_ascii=False, indent=2) + "\n",
                                 encoding="utf-8")
        else:
            if rank_path.exists() and force:
                try:
                    rank_path.unlink()
                except Exception:
                    pass
            ranking = _run_single_with_retry(workdir, full_prompt, rank_rel,
                                             rank_log, _parse,
                                             timeout, model, thinking, rank_path)

    # 合并落盘 (code only: quote_details 重建)
    ql = _quote_lookup(sentences)
    priorities: dict[str, list[dict]] = {"upgrades": [], "shop": []}
    for key in ("upgrades", "shop"):
        for ent in ranking.get(key, []):
            qs: list[str] = []
            for q in ent.get("quotes", []):
                if q not in qs:
                    qs.append(q)
            details = []
            for q in qs:
                hits = ql.get(q, [])
                h = hits[0] if hits else {"start": None, "end": None, "t": None,
                                          "context": q[:300]}
                if h.get("start") is not None and not isinstance(h.get("t"), int):
                    _fail(f"priority {ent.get('name')} quote_details t 非法: {q[:40]!r}")
                details.append({"quote": q, "start": h["start"], "end": h["end"],
                                "t": h["t"], "context": h["context"]})
            priorities[key].append({"name": ent.get("name"),
                                    "kind": "upgrade" if key == "upgrades" else "shop",
                                    "why": str(ent.get("why", "")).strip(),
                                    "how_to_get": str(ent.get("how_to_get", "")).strip(),
                                    "quotes": qs,
                                    "analysis": str(ent.get("analysis", "")).strip(),
                                    "quote_details": details})
    (outdir / "priorities.json").write_text(
        json.dumps(priorities, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    (workdir / "outputs").mkdir(parents=True, exist_ok=True)
    (workdir / "outputs" / "priorities.json").write_text(
        json.dumps(priorities, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    return priorities
