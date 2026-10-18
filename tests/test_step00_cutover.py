"""#44 切流: run_segment1/run_pilot 不再读旧链, 只认 inputs (Step00 产物)."""
from __future__ import annotations

import importlib.util
import inspect
import json
import shutil
from pathlib import Path

import pytest

REPO = Path(__file__).resolve().parent.parent


def _load(name: str, rel: str):
    spec = importlib.util.spec_from_file_location(name, str(REPO / rel))
    assert spec is not None and spec.loader is not None
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


def test_segment1_ensure_inputs_no_old_chain() -> None:
    m = _load("run_segment1", "scripts/run_segment1.py")
    src = inspect.getsource(m.ensure_inputs)
    for banned in ("data/work", "data/subs", "top3.json"):
        assert banned not in src, f"run_segment1.ensure_inputs must not read {banned}"


def test_pilot_ensure_inputs_no_old_chain() -> None:
    m = _load("run_pilot", "scripts/run_pilot.py")
    src = inspect.getsource(m.ensure_inputs)
    for banned in ("data/work", "data/subs", "top3.json", "data/mentions"):
        assert banned not in src, f"run_pilot.ensure_inputs must not read {banned}"


def _copy_inputs_to(tmp: Path) -> Path:
    src = Path("G:/brotato-work/cyborg/ultimate/inputs")
    dst = tmp / "cyborg" / "ultimate" / "inputs"
    dst.mkdir(parents=True, exist_ok=True)
    for f in ("source.vtt", "meta.json", "registry-slice.json", "manifest.json"):
        shutil.copy2(src / f, dst / f)
    return tmp / "cyborg" / "ultimate"


def test_segment1_ensure_inputs_missing_fails_loud(tmp_path: Path) -> None:
    m = _load("run_segment1", "scripts/run_segment1.py")
    workdir = tmp_path / "cyborg" / "ultimate"
    (workdir / "inputs").mkdir(parents=True)
    with pytest.raises(SystemExit) as e:
        m.ensure_inputs("cyborg", "ultimate", workdir)
    assert "fetch_inputs" in str(e.value)


def test_segment1_ensure_inputs_ok_with_step00_inputs(tmp_path: Path) -> None:
    m = _load("run_segment1", "scripts/run_segment1.py")
    workdir = _copy_inputs_to(tmp_path)
    mf = m.ensure_inputs("cyborg", "ultimate", workdir)
    assert mf["slug"] == "cyborg"
    cur = json.loads((workdir / "inputs" / "registry-slice.json").read_text(encoding="utf-8"))
    assert set(cur.keys()) == {"weapons", "items"} and len(cur["items"]) == 68


def test_pilot_ensure_inputs_ok_with_step00_inputs(tmp_path: Path) -> None:
    m = _load("run_pilot", "scripts/run_pilot.py")
    workdir = _copy_inputs_to(tmp_path)
    mf = m.ensure_inputs("cyborg", "ultimate", workdir)
    assert mf["slug"] == "cyborg"
