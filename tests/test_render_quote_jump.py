"""#98 攻略页逐句 `?t=` 点跳: 每条原话都能一键跳到视频那一秒.

Seams (deterministic, no LLM, no network):
- `render_jump_links`: 表格行紧凑形 (每句一个 `▶mm:ss` 链, 悬浮显原话)
- `render_quote_lines`: 卡片形 (原话可见 + 同一条 ⏱ 链)
- 跳链口径: `?t=<秒>s` (URL 已带 query 时用 `&`), `t` 取自 `quote_details[i].t`,
  与审计视图 `templates/audit.html` 的 `t=${it.t}s` 同口径
- 真件冒烟: G 盘 fisherman/ultimate 重渲染后, `yt-jump` 链数 == quote_details 总条数
"""
from __future__ import annotations

import importlib.util
import json
from pathlib import Path

import pytest

REPO = Path(__file__).resolve().parent.parent
G = Path("G:/brotato-work")


def _load(name: str, rel: str):
    spec = importlib.util.spec_from_file_location(name, str(REPO / rel))
    assert spec is not None and spec.loader is not None
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


R = _load("prototype_render_jump", "scripts/prototype_render.py")

QDS = [
    {"quote": "And I'm going to lock the small magazine.", "start": "28:14.880",
     "end": "28:20.830", "t": 1694, "context": "ctx"},
    {"quote": "Small magazine is is very good.", "start": "00:06:05.000",
     "end": "00:06:09.000", "t": 365, "context": "ctx2"},
]


def test_render_jump_links_emits_one_link_per_quote() -> None:
    """每句一个 ⏱ 链, 秒数取自 quote_details.t (与审计视图同口径)。"""
    html = R.render_jump_links("https://www.youtube.com/watch?v=GScaM2TeCOs", QDS)
    assert html.count("yt-jump") == 2
    assert "&amp;t=1694s" in html and "&amp;t=365s" in html  # HTML 转义后的 &t=
    assert "▶28:14" in html and "▶00:06:05" in html


def test_render_jump_links_uses_question_mark_when_url_has_no_query() -> None:
    """裸 URL 用 `?t=`, 已带 query 用 `&t=`。"""
    assert "?t=1694s" in R.render_jump_links("https://youtu.be/GScaM2TeCOs", QDS)


def test_render_jump_links_empty_and_escaping() -> None:
    """无 quote_details / 无 t 即空串; 引号里的 HTML 须转义。"""
    assert R.render_jump_links("https://www.youtube.com/watch?v=X", []) == ""
    assert R.render_jump_links("https://www.youtube.com/watch?v=X", [{"quote": "a", "t": None}]) == ""
    html = R.render_jump_links("https://www.youtube.com/watch?v=X",
                               [{"quote": '<b>"bad"</b>', "t": 5, "start": "00:00:05.000"}])
    assert "<b>" not in html and "&lt;b&gt;" in html


def test_render_quote_lines_shows_quote_text_and_jump() -> None:
    """卡片形: 原话可见 + 同一条 ⏱ 链。"""
    html = R.render_quote_lines("https://www.youtube.com/watch?v=X", QDS)
    assert html.count("yt-jump") == 2
    assert "And I&#x27;m going to lock the small magazine." in html or \
           "And I'm going to lock the small magazine." in html


def test_render_quote_lines_empty() -> None:
    assert R.render_quote_lines("https://www.youtube.com/watch?v=X", None) == ""
    assert R.render_quote_lines("https://www.youtube.com/watch?v=X", []) == ""


@pytest.mark.skipif(not (G / "fisherman" / "ultimate" / "outputs" / "guide.json").exists(),
                    reason="G 盘真件不在本机")
def test_real_guide_renders_every_quote_as_jump_link(tmp_path) -> None:
    """真件冒烟: 攻略页 yt-jump 链数 == 全部 quote_details 条数 (一句不漏)。"""
    guide_path = G / "fisherman" / "ultimate" / "outputs" / "guide.json"
    out = tmp_path / "guide.html"
    R.render_all(guide_path, REPO / "data" / "wiki-cache.json",
                 REPO / "data" / "terms.csv", REPO / "data" / "roster.json", out)
    html = out.read_text(encoding="utf-8")
    guide = json.loads(guide_path.read_text(encoding="utf-8"))
    total = 0
    for sec in (guide.get("ratings") or []):
        total += len(sec.get("quote_details") or [])
    for w in (guide.get("weapons") or {}).get("t1", []) + (guide.get("weapons") or {}).get("t2", []):
        total += len(w.get("quote_details") or [])
    for g in guide.get("groups") or []:
        total += len(g.get("quote_details") or [])
    for p in guide.get("phases") or []:
        total += len(p.get("quote_details") or [])
    pri = guide.get("priorities") or {}
    for p in pri.get("upgrades", []) + pri.get("shop", []):
        total += len(p.get("quote_details") or [])
    for pit in guide.get("pitfalls") or []:
        total += len(pit.get("quote_details") or [])
    # 变体 B (时间线) 只重复 phases/pitfalls, 故允许 A+B 同数; 只要求「A 段一句不漏」
    assert total > 0
    assert html.count('class="yt-jump"') >= total
