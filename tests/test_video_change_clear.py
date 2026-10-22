"""换片自动清场 (#69): 取证发现视频变化时备份整目录. 无网络测试."""
from __future__ import annotations

import hashlib
import importlib.util
import json
import sys
import types
from pathlib import Path

REPO = Path(__file__).resolve().parent.parent


def _load(name: str, rel: str):
    spec = importlib.util.spec_from_file_location(name, str(REPO / rel))
    assert spec is not None and spec.loader is not None
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


def test_backup_variant_dir_missing_returns_none(tmp_path: Path) -> None:
    m = _load("fetch_inputs_69", "scripts/fetch_inputs.py")
    assert m.backup_variant_dir(tmp_path / "nope") is None


def test_backup_variant_dir_moves_whole_dir(tmp_path: Path) -> None:
    m = _load("fetch_inputs_69b", "scripts/fetch_inputs.py")
    workdir = tmp_path / "ultimate"
    (workdir / "inputs").mkdir(parents=True)
    (workdir / "inputs" / "manifest.json").write_text("{}", encoding="utf-8")
    (workdir / "steps" / "04-attributes").mkdir(parents=True)
    bak = m.backup_variant_dir(workdir)
    assert bak is not None and bak.exists()
    assert bak.parent == tmp_path and bak.name.startswith("ultimate.bak.")
    assert not workdir.exists()
    assert (bak / "inputs" / "manifest.json").exists()
    assert (bak / "steps" / "04-attributes").exists()


def test_backup_variant_dir_collision_suffix(tmp_path: Path) -> None:
    m = _load("fetch_inputs_69c", "scripts/fetch_inputs.py")
    workdir = tmp_path / "ultimate"
    (workdir / "inputs").mkdir(parents=True)
    bak1 = m.backup_variant_dir(workdir)
    assert bak1 is not None
    (workdir / "inputs").mkdir(parents=True)
    bak2 = m.backup_variant_dir(workdir)
    assert bak2 is not None and bak2 != bak1 and bak2.exists() and bak1.exists()


def test_url_video_id_forms() -> None:
    m = _load("run_chain_69", "scripts/run_chain.py")
    assert m._url_video_id("https://www.youtube.com/watch?v=Wge0_hd9Rt8") == "Wge0_hd9Rt8"
    assert m._url_video_id("https://www.youtube.com/watch?v=Wge0_hd9Rt8&t=42s") == "Wge0_hd9Rt8"
    assert m._url_video_id("https://youtu.be/rctxc3DIyy0") == "rctxc3DIyy0"
    assert m._url_video_id("https://www.youtube.com/shorts/abc123XYZ-_") == "abc123XYZ-_"
    assert m._url_video_id("https://www.youtube.com/live/abc123XYZ-_") == "abc123XYZ-_"
    assert m._url_video_id("https://www.youtube.com/embed/abc123XYZ-_") == "abc123XYZ-_"
    assert m._url_video_id("not a url") == ""
    assert m._url_video_id("") == ""


def _write_inputs(workdir: Path, video_id: str) -> dict:
    vtt = b"WEBVTT\n\n00:00:00.000 --> 00:00:01.000\nhello\n"
    sha1 = hashlib.sha1(vtt).hexdigest()
    inputs = workdir / "inputs"
    inputs.mkdir(parents=True, exist_ok=True)
    (inputs / "source.vtt").write_bytes(vtt)
    (inputs / "meta.json").write_text(
        json.dumps({"chapters": [], "title": "t"}, ensure_ascii=False), encoding="utf-8")
    (inputs / "manifest.json").write_text(
        json.dumps({"sources": [{"video_id": video_id, "sha1": sha1}]}, ensure_ascii=False),
        encoding="utf-8")
    return {"sha1": sha1}


def test_ensure_step00_same_video_skips_fetch(tmp_path: Path, monkeypatch) -> None:
    """同片 --url 不重下: fetch_inputs.main 若被调用即测试失败."""
    m = _load("run_chain_69b", "scripts/run_chain.py")
    workdir = tmp_path / "slug" / "variant"
    _write_inputs(workdir, "Wge0_hd9Rt8")

    def _boom(*a, **k):
        raise AssertionError("same video must skip fetch (幂等不重下)")

    stub = types.ModuleType("fetch_inputs")
    stub.main = _boom  # type: ignore[attr-defined]
    monkeypatch.setitem(sys.modules, "fetch_inputs", stub)
    out = m.ensure_step00("slug", "variant", workdir,
                          url="https://www.youtube.com/watch?v=Wge0_hd9Rt8", cookies="")
    assert (out.get("sources") or [{}])[0].get("video_id") == "Wge0_hd9Rt8"


def test_ensure_step00_changed_video_triggers_fetch(tmp_path: Path, monkeypatch) -> None:
    """换片 --url 走 fetch: stub 落盘新三件后 ensure 通过."""
    m = _load("run_chain_69c", "scripts/run_chain.py")
    workdir = tmp_path / "slug" / "variant"
    _write_inputs(workdir, "OLD_old_old1")

    calls: list = []

    def _fake_fetch(argv):
        calls.append(argv)
        _write_inputs(workdir, "Wge0_hd9Rt8")
        return 0

    stub = types.ModuleType("fetch_inputs")
    stub.main = _fake_fetch  # type: ignore[attr-defined]
    monkeypatch.setitem(sys.modules, "fetch_inputs", stub)
    out = m.ensure_step00("slug", "variant", workdir,
                          url="https://www.youtube.com/watch?v=Wge0_hd9Rt8", cookies="")
    assert calls, "changed video must trigger fetch (换片重取)"
    assert (out.get("sources") or [{}])[0].get("video_id") == "Wge0_hd9Rt8"
