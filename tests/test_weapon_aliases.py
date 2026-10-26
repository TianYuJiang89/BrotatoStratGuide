"""#75 05 discovery 别名归一: Gatling gun 未对上 Gatling Laser.

Seams (deterministic-first, no LLM in tests):
- alias table: data/weapon-aliases.json 显式维护, 代码内禁硬编码
- scan: 代码按词界扫原话只作 prompt 预告, 收/丢仍由 agent 定 (不自动收)
- prompt: 本批别名预告只进本批, 不串片, 缺件即 fail 口径不变 (收+丢==vocab)
"""
from __future__ import annotations

import importlib.util
import json
from pathlib import Path

import pytest

REPO = Path(__file__).resolve().parent.parent


def _load(name: str, rel: str):
    spec = importlib.util.spec_from_file_location(name, str(REPO / rel))
    assert spec is not None and spec.loader is not None
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


def _ranger_like_sentences():
    return [
        {"id": 161, "text": "I will buy Gatling gun.",
         "start": "00:10:00.000", "end": "00:10:05.000", "start_s": 600.0, "end_s": 605.0, "t": 600},
        {"id": 162, "text": "Of course, we're buying a lot of ranged damage, so the Gatling gun can just be a little bit of extra clear speed for us.",
         "start": "00:10:06.000", "end": "00:10:11.000", "start_s": 606.0, "end_s": 611.0, "t": 606},
        {"id": 404, "text": "100,000 damage from our Gatling guns.",
         "start": "00:40:00.000", "end": "00:40:05.000", "start_s": 2400.0, "end_s": 2405.0, "t": 2400},
        {"id": 5, "text": "The Ranger also tries to trick the player by starting you with a pistol, which is a pretty weak weapon.",
         "start": "00:00:05.000", "end": "00:00:10.000", "start_s": 5.0, "end_s": 10.0, "t": 5},
        {"id": 15, "text": "We're going to sell this pistol immediately so that guns don't show up in the pool.",
         "start": "00:00:15.000", "end": "00:00:20.000", "start_s": 15.0, "end_s": 20.0, "t": 15},
    ]


def test_alias_table_exists_and_maps_gatling():
    p = REPO / "data" / "weapon-aliases.json"
    assert p.exists(), "data/weapon-aliases.json must exist (#75 显式维护)"
    d = json.loads(p.read_text(encoding="utf-8"))
    assert isinstance(d, dict)
    assert "Gatling Laser" in d, "Gatling gun→Gatling Laser 须在映射表内 (#75)"
    got = [a.lower() for a in d["Gatling Laser"]]
    assert "gatling gun" in got
    # Nuclear Launcher 别名已在 fewshot DIS-06 教学, 同样须进表 (确定性归一不只靠例子)
    assert "Nuclear Launcher" in d
    assert "nuke launcher" in [a.lower() for a in d["Nuclear Launcher"]]
    # 注册表名须在武器词汇表内 (错名即 fail, 由代码 + check 双验)
    vocab = set(json.loads((REPO / "data" / "wiki-cache.json").read_text(encoding="utf-8"))["weapons"].keys())
    for k in d:
        if k.startswith("_"):
            continue
        assert k in vocab, f"alias registry name must be in vocab: {k!r}"
        assert isinstance(d[k], list) and d[k] and all(isinstance(a, str) and a.strip() for a in d[k])


def test_load_aliases_skips_meta_and_lowercases():
    m = _load("step05_loop_alias", "scripts/step05_loop.py")
    aliases = m.load_weapon_aliases()
    assert "_comment" not in aliases
    assert "Gatling Laser" in aliases
    assert "gatling gun" in aliases["Gatling Laser"]


def test_scan_alias_hits_finds_gatling_but_not_pistol_alias():
    m = _load("step05_loop_scan", "scripts/step05_loop.py")
    aliases = m.load_weapon_aliases()
    sents = _ranger_like_sentences()
    hits = m.scan_alias_hits(sents, aliases)
    assert "Gatling Laser" in hits
    assert hits["Gatling Laser"]["hits"] == 3, f"3 句 Gatling gun/guns 须命中, got {hits['Gatling Laser']}"
    # Pistol 无别名表项, 不应出现 (trick 即卖仍由 agent 判丢, 代码不预告)
    assert "Pistol" not in hits
    # 复数 Gatling guns 须被 gatling stem 命中 (s? 宽容)
    assert "gatling" in [a.lower() for a in hits["Gatling Laser"]["matched"]] or \
           "gatling gun" in [a.lower() for a in hits["Gatling Laser"]["matched"]]


def test_scan_alias_hits_empty_when_no_alias_spoken():
    m = _load("step05_loop_scan2", "scripts/step05_loop.py")
    aliases = m.load_weapon_aliases()
    sents = [{"id": 1, "text": "We'll buy a slingshot.", "start": None, "end": None}]
    assert m.scan_alias_hits(sents, aliases) == {}


def test_discovery_prompt_injects_alias_hints_per_chunk_only():
    m = _load("step05_loop_prompt", "scripts/step05_loop.py")
    fewshot_d = (REPO / "prompts" / "step05-discovery-fewshot.md").read_text(encoding="utf-8")
    sents = _ranger_like_sentences()
    aliases = m.load_weapon_aliases()
    hits = m.scan_alias_hits(sents, aliases)
    chunk_with = ["Gatling Laser", "Pistol"]
    chunk_without = ["Minigun", "Screwdriver"]
    p1 = m.build_discovery_prompt(sents, chunk_with, 0, 2, fewshot_d,
                                  aliases=aliases, alias_hits=hits)
    assert "Gatling Laser" in p1
    assert "gatling gun" in p1.lower(), "本批别名预告须出现俗称 (#75)"
    assert "原话命中 3 句" in p1
    # 不串片: 不含本批的别名名不进 prompt
    p2 = m.build_discovery_prompt(sents, chunk_without, 1, 2, fewshot_d,
                                  aliases=aliases, alias_hits=hits)
    assert "别名归一预告" not in p2, "无别名名的分片不应有预告块 (不串片)"
    assert "- Gatling Laser" not in p2
    # 向后兼容: 老 5 参调用仍可用 (无别名即无预告块)
    p0 = m.build_discovery_prompt(sents, chunk_without, 1, 2, fewshot_d)
    assert "TASK_DISCOVERY" in p0


def test_fewshot_stays_v4_alias_lives_in_code():
    """#75 修法只动代码不碰 frozen：fewshot 保持 v4（其余四单快照不动），别名预告由代码注入。"""
    txt = (REPO / "prompts" / "step05-discovery-fewshot.md").read_text(encoding="utf-8")
    assert "FROZEN 2026-10-21 v4" in txt
    assert "DIS-11" not in txt, "别名例不进 frozen（code-side 预告已覆盖，免全局重跑）"


def test_ranking_prompt_injects_alias_hints():
    """ranking 切分须全量：一把不丢，别名名须在候选名单处对上原话俗称。"""
    m = _load("step05_loop_ranking", "scripts/step05_loop.py")
    fewshot_r = (REPO / "prompts" / "step05-ranking-fewshot.md").read_text(encoding="utf-8")
    sents = _ranger_like_sentences()
    aliases = m.load_weapon_aliases()
    hits = m.scan_alias_hits(sents, aliases)
    evs = [
        {"name_en": "Gatling Laser", "tier": "T1",
         "quotes": [s["text"] for s in sents if "gatling" in s["text"].lower()],
         "analysis": "a", "note": "n", "copies": "x", "copies_quote": ""},
        {"name_en": "Slingshot", "tier": "T1", "quotes": ["We'll buy a slingshot."],
         "analysis": "a", "note": "n", "copies": "x", "copies_quote": ""},
    ]
    p = m.build_ranking_prompt(sents, evs, fewshot_r, aliases=aliases, alias_hits=hits)
    assert "别名归一预告" in p
    assert "Gatling Laser" in p and "gatling gun" in p.lower()
    assert "一把不丢" in p
    # 向后兼容: 老 3 参调用仍可用
    p0 = m.build_ranking_prompt(sents, evs, fewshot_r)
    assert "TASK_RANKING" in p0


def test_run_loop_writes_alias_snapshot_and_flows_gatling(tmp_path):
    """Fake三段: Gatling gun 3 句 → discovery 收 Gatling Laser → candidates/provenance 落盘."""
    m = _load("step05_loop_e2e", "scripts/step05_loop.py")
    sents = _ranger_like_sentences() + [
        {"id": 6, "text": "We'll buy a slingshot.",
         "start": None, "end": None},
    ]
    workdir = tmp_path / "ranger" / "ultimate"
    (workdir / "steps" / "05-weapons" / "per_weapon").mkdir(parents=True, exist_ok=True)
    (workdir / "outputs").mkdir(parents=True, exist_ok=True)
    vocab = ["Gatling Laser", "Pistol", "Slingshot", "Nuclear Launcher"]
    quotes_by = {
        "Gatling Laser": [s["text"] for s in sents if "gatling" in s["text"].lower()],
        "Slingshot": ["We'll buy a slingshot."],
    }
    assert len(quotes_by["Gatling Laser"]) == 3

    def fake_agent(kind, name_en, prompt):
        if kind == "discovery":
            chunks = m.chunk_vocab(sorted(vocab))
            ch = chunks[name_en]
            if "Gatling Laser" in ch:
                assert "gatling gun" in prompt.lower(), "含别名名的分片 prompt 须带预告 (#75)"
            return {"收": [{"name_en": n, "quotes": quotes_by[n]} for n in ch if n in quotes_by],
                    "丢": [n for n in ch if n not in quotes_by]}
        if kind == "evidence":
            return {"name_en": name_en, "tier": "T1", "quotes": quotes_by[name_en],
                    "analysis": f"{name_en}来源→机制。", "note": f"{name_en}人话原话\"{quotes_by[name_en][0][:12]}\"。",
                    "copies": "未提及", "copies_quote": ""}
        if kind == "ranking":
            names = sorted(quotes_by.keys())
            return {"t1": [{"name_en": n, "note": f"主力原话\"{quotes_by[n][0][:12]}\"。",
                            "copies": "未提及", "copies_quote": ""} for n in names], "t2": []}
        raise AssertionError(kind)

    orig_vocab, orig_alias = m.load_weapon_vocab, m.load_weapon_aliases
    m.load_weapon_vocab = lambda: sorted(set(vocab))
    try:
        weapons = m.run_step05_loop(workdir, sents, agent_fn=fake_agent, force=True)
    finally:
        m.load_weapon_vocab = orig_vocab
    # Gatling 进候选 (#75 回归线)
    cands = json.loads((workdir / "steps" / "05-weapons" / "candidates.json").read_text(encoding="utf-8"))
    assert sorted(c["name_en"] for c in cands) == ["Gatling Laser", "Slingshot"]
    got = sorted([w["name_en"] for w in weapons["t1"] + weapons["t2"]])
    assert "Gatling Laser" in got
    # provenance: aliases.json 快照与 repo 一致 (归一化排序后逐字节)
    snap = json.loads((workdir / "steps" / "05-weapons" / "aliases.json").read_text(encoding="utf-8"))
    repo = {k: v for k, v in json.loads((REPO / "data" / "weapon-aliases.json").read_text(encoding="utf-8")).items()
            if not k.startswith("_")}
    assert snap == repo
    disc = json.loads((workdir / "steps" / "05-weapons" / "discovery.json").read_text(encoding="utf-8"))
    assert disc["aliases"] == repo
    assert disc["alias_hits"]["Gatling Laser"]["hits"] == 3
