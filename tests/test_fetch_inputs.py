"""Step00 取证 (#44): fetch_inputs 单元测试 (TDD, 无网络, mock yt-dlp).

约定:
- 不碰网络: yt-dlp 调用全部 mock (subprocess.run 替身).
- 不读 data/work | data/subs | data/mentions | data/builds (新链隔离).
- 只读全局 data/terms.csv + data/wiki-cache.json (注册表唯一 URL 源).
"""
from __future__ import annotations

import hashlib
import json
from pathlib import Path

import pytest

REPO = Path(__file__).resolve().parent.parent


def _load_fetch():
    import importlib.util
    spec = importlib.util.spec_from_file_location(
        "fetch_inputs", str(REPO / "scripts" / "fetch_inputs.py"))
    assert spec is not None and spec.loader is not None
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


def test_module_exists_and_no_old_chain_reads() -> None:
    """Step00 为固定代码: 模块存在, 且源码不含 data/work|subs|mentions|builds 读取."""
    p = REPO / "scripts" / "fetch_inputs.py"
    assert p.exists(), "missing scripts/fetch_inputs.py (Step00)"
    src = p.read_text(encoding="utf-8")
    for banned in ("data/work", "data/subs", "data/mentions", "data/builds"):
        assert banned not in src, f"fetch_inputs must not read {banned} (新链隔离)"


def test_normalize_published() -> None:
    m = _load_fetch()
    assert m.normalize_published("20260708") == "2026-07-08"
    assert m.normalize_published("2026-07-08") == "2026-07-08"
    with pytest.raises(SystemExit):
        m.normalize_published("")


def test_default_difficulty_and_covers() -> None:
    m = _load_fetch()
    assert m.default_difficulty("ultimate") == "Ultimate"
    assert m.default_difficulty("danger-5") == "Danger 5"
    # 单变体默认单 cover; 多段变体需显式 --covers, 默认按单体走不猜
    assert m.default_covers("ultimate", "Ultimate") == ["Ultimate"]
    assert m.default_covers("danger-5", "Danger 5") == ["Danger 5"]


def test_pick_subs_prefers_manual() -> None:
    m = _load_fetch()
    meta_both = {"subtitles": {"en": [{"ext": "vtt"}]},
                 "automatic_captions": {"en": [{"ext": "json3"}]}}
    lang, source, manual = m.pick_subs(meta_both)
    assert lang == "en" and source == "manual" and manual is True
    meta_auto_only = {"subtitles": {}, "automatic_captions": {"en": [{"ext": "json3"}]}}
    lang, source, manual = m.pick_subs(meta_auto_only)
    assert lang == "en" and source == "auto" and manual is False
    with pytest.raises(SystemExit):
        m.pick_subs({"subtitles": {}, "automatic_captions": {}})


def test_build_meta_and_manifest_shape(tmp_path: Path) -> None:
    m = _load_fetch()
    dump = {
        "id": "yEY-RoLWjfM",
        "title": "TERMINATE - Cyborg - Brotato Ultimate Nightmares Guide",
        "duration_string": "33:23",
        "upload_date": "20260708",
        "description": "Trying out the new, brutal stuff!",
        "chapters": [{"title": "Character overview", "start_time": 0, "end_time": 105},
                       {"title": "Strategy and early game", "start_time": 105, "end_time": 322}],
        "webpage_url": "https://www.youtube.com/watch?v=yEY-RoLWjfM",
    }
    meta = m.build_meta(dump, difficulty="Ultimate", subs_source="auto")
    assert meta["title"].startswith("TERMINATE")
    assert meta["video_id"] == "yEY-RoLWjfM"
    assert meta["published"] == "2026-07-08"
    assert meta["duration"] == "33:23"
    assert meta["chapters"] == [{"title": "Character overview", "start": 0, "end": 105},
                                   {"title": "Strategy and early game", "start": 105, "end": 322}]
    assert meta["subs_source"] == "auto"
    assert "youtube.com/watch?v=yEY-RoLWjfM" in meta["url"]
    mf = m.build_manifest("cyborg", "ultimate", ["Ultimate"], meta,
                          sha1="abc123", sop_version="", issue=44)
    assert mf["slug"] == "cyborg" and mf["variant"] == "ultimate"
    assert mf["issue"] == 44 and mf["subs_source"] == "auto"
    assert mf["sources"][0]["sha1"] == "abc123"
    assert mf["sources"][0]["vtt"] == "inputs/source.vtt"


def test_registry_slice_retired_no_dynamic(tmp_path: Path) -> None:
    """#61 slice 退役: fetch 不再产 slice，scan 子串口径作废，completeness 归 discovery。"""
    m = _load_fetch()
    assert not hasattr(m, "build_registry_slice"), \
        "fetch_inputs.build_registry_slice must be retired (#61)"
    src = (REPO / "scripts" / "fetch_inputs.py").read_text(encoding="utf-8")
    assert "registry-slice.json" in src, "退役说明须提及旧文件删 (fetch 停产+旧文件删)"
    # 实现不得再动态推导 slice (scan_cues 口径作废)
    assert "scan_cues" not in src, "fetch_inputs must not scan_cues (子串 scope 作废)"


def test_fail_loud_no_whisper_no_mock() -> None:
    """源码禁 Whisper/回落/mock 字眼 (确定性优先 + 禁静默 fallback)."""
    src = (REPO / "scripts" / "fetch_inputs.py").read_text(encoding="utf-8").lower()
    for banned in ("whisper", "fallback", "mock"):
        assert banned not in src, f"fetch_inputs must not contain {banned}"


def test_end_to_end_with_mocked_ytdlp(tmp_path: Path, monkeypatch) -> None:
    """端到端 (mock yt-dlp): URL -> inputs 四件, sha/subs_source/URL 落盘."""
    m = _load_fetch()
    vtt_text = (REPO / "data" / "subs" / "cyborg__ultimate.en-orig.vtt").read_text(encoding="utf-8")
    dump = {
        "id": "yEY-RoLWjfM",
        "title": "TERMINATE - Cyborg - Brotato Ultimate Nightmares Guide",
        "duration_string": "33:23",
        "upload_date": "20260708",
        "description": "Trying out the new, brutal stuff!",
        "chapters": [{"title": "Character overview", "start_time": 0, "end_time": 105}],
        "webpage_url": "https://www.youtube.com/watch?v=yEY-RoLWjfM",
        "subtitles": {},
        "automatic_captions": {"en": [{"ext": "json3"}]},
    }

    import subprocess as sp

    def fake_run(cmd, **kw):
        # metadata 调用: 返回 dump json
        if "--dump-json" in cmd or "-j" in cmd or "-J" in cmd:
            return sp.CompletedProcess(cmd, 0, stdout=json.dumps(dump), stderr="")
        # 字幕下载调用: 在 --output 模板处落一个 VTT
        out = None
        for i, tok in enumerate(cmd):
            if tok == "-o" and i + 1 < len(cmd):
                out = cmd[i + 1]
        assert out is not None
        # 模板含 %(id)s -> 替换为真实 id
        dest = out.replace("%(id)s", dump["id"]).replace("%(ext)s", "vtt")
        # yt-dlp 实际落盘为 <id>.en.vtt (sub-langs 后缀); 测试替身同口径
        if not dest.endswith(".en.vtt"):
            dest = dest.replace(".vtt", ".en.vtt")
        Path(dest).parent.mkdir(parents=True, exist_ok=True)
        Path(dest).write_text(vtt_text, encoding="utf-8")
        return sp.CompletedProcess(cmd, 0, stdout="", stderr="")

    monkeypatch.setattr("subprocess.run", fake_run)
    # 预置旧 slice，验 fetch 停产+旧文件删
    _pre = tmp_path / "cyborg" / "ultimate" / "inputs"
    _pre.mkdir(parents=True, exist_ok=True)
    (_pre / "registry-slice.json").write_text('{"weapons": [], "items": []}', encoding="utf-8")
    rc = m.main(["--url", "https://www.youtube.com/watch?v=yEY-RoLWjfM",
                 "--slug", "cyborg", "--variant", "ultimate",
                 "--work-root", str(tmp_path)])
    assert rc == 0
    inputs = tmp_path / "cyborg" / "ultimate" / "inputs"
    for f in ("source.vtt", "meta.json", "manifest.json"):
        assert (inputs / f).exists(), f"missing {f}"
    # #61 退役: 不再产 slice，旧文件若有须删
    assert not (inputs / "registry-slice.json").exists(), \
        "fetch_inputs must not produce registry-slice.json (#61)"
    assert (inputs / "source.vtt").read_text(encoding="utf-8") == vtt_text
    sha = hashlib.sha1((inputs / "source.vtt").read_bytes()).hexdigest()
    mf = json.loads((inputs / "manifest.json").read_text(encoding="utf-8"))
    assert mf["sources"][0]["sha1"] == sha
    assert mf["subs_source"] == "auto"
    meta = json.loads((inputs / "meta.json").read_text(encoding="utf-8"))
    assert meta["subs_source"] == "auto"
    assert "youtube.com" in meta["url"]


def test_end_to_end_missing_subs_fails_loud(tmp_path: Path, monkeypatch) -> None:
    m = _load_fetch()
    dump = {"id": "xxx", "title": "T", "duration_string": "1:00",
            "upload_date": "20260708", "description": "d",
            "chapters": [{"title": "C", "start_time": 0, "end_time": 60}],
            "webpage_url": "https://www.youtube.com/watch?v=xxx",
            "subtitles": {}, "automatic_captions": {}}
    import subprocess as sp
    monkeypatch.setattr("subprocess.run",
                        lambda *a, **k: sp.CompletedProcess(a[0], 0,
                                                           stdout=json.dumps(dump), stderr=""))
    with pytest.raises(SystemExit):
        m.main(["--url", "https://www.youtube.com/watch?v=xxx",
                "--slug", "cyborg", "--variant", "ultimate",
                "--work-root", str(tmp_path)])
