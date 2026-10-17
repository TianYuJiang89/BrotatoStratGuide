"""#13 E2E seam: 取材与巡检徽标 Top3 + 双标注检查.

Seams under test (pre-agreed per #8: E2E only):
- `python scripts/build.py --slug <slug>` exit codes + `docs/*.html` bytes
- `python scripts/check.py <html>` exit codes
- `python scripts/check_updates.py` exit codes (version drift -> 待重审)

No internal imports, no network. All assertions inspect CLI exit codes
and generated file bytes. Fixtures are isolated tmp copies.
"""

from __future__ import annotations

import json
import re
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path

REPO = Path(__file__).resolve().parent.parent
BUILD = [sys.executable, "scripts/build.py"]
CHECK = [sys.executable, "scripts/check.py"]
CHECK_UPDATES = [sys.executable, "scripts/check_updates.py"]

NEW_DATE = "2026-10-15"
OLD_DATE = "2025-01-01"


def make_workdir() -> tuple[Path, Path, Path, tempfile.TemporaryDirectory[str]]:
    tmp = tempfile.TemporaryDirectory()
    work = Path(tmp.name) / "work"
    shutil.copytree(REPO / "data", work / "data")
    shutil.copytree(REPO / "templates", work / "templates")
    out = Path(tmp.name) / "out"
    return (work / "data", work / "templates", out, tmp)


def build_fixture(data_dir: Path, templates_dir: Path, out: Path) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        [*BUILD, "--slug", "cyborg",
         "--data-dir", str(data_dir),
         "--templates-dir", str(templates_dir),
         "--out-dir", str(out)],
        cwd=REPO, capture_output=True, text=True,
    )


def read_source(data_dir: Path) -> dict:
    build_file = data_dir / "builds" / "cyborg.json"
    return json.loads(build_file.read_text(encoding="utf-8"))


def write_source(data_dir: Path, source: dict) -> None:
    build_file = data_dir / "builds" / "cyborg.json"
    data = json.loads(build_file.read_text(encoding="utf-8"))
    data["source"] = source
    build_file.write_text(json.dumps(data, ensure_ascii=False), encoding="utf-8")


def valid_source() -> dict:
    return {
        "title": "Cyborg Endless Build - Cyborg - Brotato Ultimate Nightmares Guide",
        "url": "https://www.youtube.com/watch?v=AbC123XyZ01",
        "video_id": "AbC123XyZ01",
        "published": NEW_DATE,
        "difficulty": "Ultimate",
        "game_version": f"Steam 1.1.6.2 ({NEW_DATE} + Steam)",
        "has_captions": True,
        "transcript": {"captions": "auto", "corrected": True},
        "candidates": [
            {
                "title": "Cyborg Endless Build - Cyborg - Brotato Ultimate Nightmares Guide",
                "url": "https://www.youtube.com/watch?v=AbC123XyZ01",
                "video_id": "AbC123XyZ01",
                "published": NEW_DATE,
                "difficulty": "Ultimate",
                "has_captions": True,
            },
            {
                "title": "SMG Rush - Cyborg - Brotato Nightmare Guide",
                "url": "https://www.youtube.com/watch?v=DeF456UvW02",
                "video_id": "DeF456UvW02",
                "published": NEW_DATE,
                "difficulty": "Nightmare",
                "has_captions": True,
            },
        ],
    }


def source_section(html: str) -> str:
    m = re.search(r'data-section="source".*?</section>', html, re.S)
    assert m is not None, "source section must exist"
    return m.group(0)


def test_top3_valid_renders_main_plus_supplements() -> None:
    """Top3 含链接加标识加日期加难度加字幕有无：主 + 补充同页可验。"""
    data_dir, templates_dir, out, tmp = make_workdir()
    try:
        write_source(data_dir, valid_source())
        r = build_fixture(data_dir, templates_dir, out)
        assert r.returncode == 0, f"valid Top3 must build: {r.stderr[-2000:]}"
        html = (out / "cyborg.html").read_text(encoding="utf-8")
        sec = source_section(html)
        # 主引用五元组：标题链接 + 标识 + 日期 + 难度 + 版本双标注。
        assert "AbC123XyZ01" in sec
        assert "https://www.youtube.com/watch?v=AbC123XyZ01" in sec
        assert NEW_DATE in sec
        assert "Ultimate" in sec
        # 字幕有无 + 教学局（Guide 后缀） + 双标注。
        assert "字幕" in sec
        assert "教学局" in sec
        assert "双标注" in sec
        # 补充引用（不超 2）同页。
        assert "DeF456UvW02" in sec
        assert "Nightmare" in sec
    finally:
        tmp.cleanup()


def test_top3_too_many_fails() -> None:
    """每角色 1 主加不超 2 补充：4 候选即 fail。"""
    data_dir, templates_dir, out, tmp = make_workdir()
    try:
        src = valid_source()
        cands = list(src["candidates"])
        cands.extend([
            {
                "title": "Extra - Cyborg - Brotato Nightmare Guide",
                "url": "https://www.youtube.com/watch?v=GhI789AbC03",
                "video_id": "GhI789AbC03",
                "published": NEW_DATE,
                "difficulty": "Nightmare",
                "has_captions": True,
            },
            {
                "title": "Fourth - Cyborg - Brotato Danger 5 Guide",
                "url": "https://www.youtube.com/watch?v=JkL012DeF04",
                "video_id": "JkL012DeF04",
                "published": NEW_DATE,
                "difficulty": "Danger 5",
                "has_captions": True,
            },
        ])
        src["candidates"] = cands
        write_source(data_dir, src)
        r = build_fixture(data_dir, templates_dir, out)
        assert r.returncode != 0, "4 candidates must fail (1 主 + 不超 2 补充)"
    finally:
        tmp.cleanup()


def test_entertainment_never_main_candidate() -> None:
    """娱乐局不进候选：Tier List / Challenge 作主引用即 fail。"""
    data_dir, templates_dir, out, tmp = make_workdir()
    try:
        src = valid_source()
        src["title"] = "Ranking All - Cyborg - Brotato Tier List"
        src["candidates"][0]["title"] = "Ranking All - Cyborg - Brotato Tier List"
        write_source(data_dir, src)
        r = build_fixture(data_dir, templates_dir, out)
        assert r.returncode != 0, "entertainment must never be main candidate"
        combined = (r.stdout + r.stderr).lower()
        assert "tier" in combined or "娱乐" in combined or "entertainment" in combined
    finally:
        tmp.cleanup()


def test_invalid_difficulty_fails() -> None:
    """难度只认三档：Danger 5 / Nightmare / Ultimate 之外即 fail。"""
    data_dir, templates_dir, out, tmp = make_workdir()
    try:
        src = valid_source()
        src["difficulty"] = "Danger 3"
        src["candidates"][0]["difficulty"] = "Danger 3"
        write_source(data_dir, src)
        r = build_fixture(data_dir, templates_dir, out)
        assert r.returncode != 0, "invalid difficulty must fail"
    finally:
        tmp.cleanup()


def test_empty_candidates_honest_warns_but_publishes() -> None:
    """零命中诚实告知：无符合宁可空缺待补，不降级引用娱乐局。"""
    data_dir, templates_dir, out, tmp = make_workdir()
    try:
        src = valid_source()
        src["candidates"] = []
        src["title"] = "待补：暂无可用主引用"
        src["url"] = "https://www.youtube.com/@Cephalopocalypse"
        src["video_id"] = "待补"
        src["published"] = NEW_DATE
        src["difficulty"] = "Nightmare"
        write_source(data_dir, src)
        r = build_fixture(data_dir, templates_dir, out)
        assert r.returncode == 0, f"honest empty must publish with warn: {r.stderr[-2000:]}"
        combined = r.stdout + r.stderr
        assert "WARN" in combined
        html = (out / "cyborg.html").read_text(encoding="utf-8")
        sec = source_section(html)
        assert "待补" in sec
        assert "暂无可用主引用" in sec or "待补口径" in html
    finally:
        tmp.cleanup()


def test_missing_captions_downgrades_but_publishes() -> None:
    """抽取只做两件：无字幕降级或待补，不猜测，仍可发布。"""
    data_dir, templates_dir, out, tmp = make_workdir()
    try:
        src = valid_source()
        src["has_captions"] = False
        src["transcript"] = {"captions": "none", "corrected": False}
        src["candidates"][0]["has_captions"] = False
        src["candidates"][1]["has_captions"] = False
        write_source(data_dir, src)
        r = build_fixture(data_dir, templates_dir, out)
        assert r.returncode == 0, f"missing captions must warn not fail: {r.stderr[-2000:]}"
        combined = r.stdout + r.stderr
        assert "WARN" in combined
        html = (out / "cyborg.html").read_text(encoding="utf-8")
        sec = source_section(html)
        assert "无字幕" in sec or "待补" in sec
    finally:
        tmp.cleanup()


def test_forbidden_extraction_fails() -> None:
    """禁重转写画面多模态：含 frames / multimodal 即 fail。"""
    data_dir, templates_dir, out, tmp = make_workdir()
    try:
        src = valid_source()
        src["transcript"] = {"captions": "auto", "corrected": True, "frames": ["f1"]}
        write_source(data_dir, src)
        r = build_fixture(data_dir, templates_dir, out)
        assert r.returncode != 0, "frames/multimodal extraction must fail"
    finally:
        tmp.cleanup()


def test_old_date_marks_recheck_but_publishes() -> None:
    """旧日期命中待重审：早于大更新即 warn 加徽标，可发布。"""
    data_dir, templates_dir, out, tmp = make_workdir()
    try:
        src = valid_source()
        src["published"] = OLD_DATE
        src["game_version"] = f"Steam 1.0.0 ({OLD_DATE} + Steam)"
        src["candidates"][0]["published"] = OLD_DATE
        write_source(data_dir, src)
        r = build_fixture(data_dir, templates_dir, out)
        assert r.returncode == 0, f"old date must warn not fail: {r.stderr[-2000:]}"
        combined = r.stdout + r.stderr
        assert "WARN" in combined
        assert "待重审" in combined or "重审" in combined
        html = (out / "cyborg.html").read_text(encoding="utf-8")
        assert "待重审" in html
    finally:
        tmp.cleanup()


def test_missing_dual_annotation_warns_but_publishes() -> None:
    """双标注齐全：缺游戏版本即 warn 加待补徽标，可发布。"""
    data_dir, templates_dir, out, tmp = make_workdir()
    try:
        src = valid_source()
        src["game_version"] = ""
        write_source(data_dir, src)
        r = build_fixture(data_dir, templates_dir, out)
        assert r.returncode == 0, f"missing game_version must warn not fail: {r.stderr[-2000:]}"
        combined = r.stdout + r.stderr
        assert "WARN" in combined
        html = (out / "cyborg.html").read_text(encoding="utf-8")
        assert "待补" in html
    finally:
        tmp.cleanup()


def test_live_run_without_guide_marks_recorded() -> None:
    """无后缀注明实况：标题无 Guide 即实况复盘非教学局。"""
    data_dir, templates_dir, out, tmp = make_workdir()
    try:
        src = valid_source()
        src["title"] = "Full Run - Cyborg - Brotato Nightmare"
        src["difficulty"] = "Nightmare"
        src["candidates"][0]["title"] = "Full Run - Cyborg - Brotato Nightmare"
        src["candidates"][0]["difficulty"] = "Nightmare"
        write_source(data_dir, src)
        r = build_fixture(data_dir, templates_dir, out)
        assert r.returncode == 0, f"live run must publish: {r.stderr[-2000:]}"
        html = (out / "cyborg.html").read_text(encoding="utf-8")
        sec = source_section(html)
        assert "实况" in sec
        assert "教学局" not in sec or "非教学局" in sec or "实况" in sec
    finally:
        tmp.cleanup()


def test_resource_flag_marks_badge_but_publishes() -> None:
    """资源失效命中资源待重审：flag 即 warn 加徽标，可发布。"""
    data_dir, templates_dir, out, tmp = make_workdir()
    try:
        src = valid_source()
        src["resource_review"] = True
        write_source(data_dir, src)
        r = build_fixture(data_dir, templates_dir, out)
        assert r.returncode == 0, f"resource flag must warn not fail: {r.stderr[-2000:]}"
        html = (out / "cyborg.html").read_text(encoding="utf-8")
        assert "资源待重审" in html
    finally:
        tmp.cleanup()


def test_check_py_gates_invalid_difficulty_and_entertainment() -> None:
    """check.py 门禁：改序外，难度错与娱乐局混入即 fail。"""
    data_dir, templates_dir, out, tmp = make_workdir()
    try:
        write_source(data_dir, valid_source())
        r = build_fixture(data_dir, templates_dir, out)
        assert r.returncode == 0, r.stderr[-2000:]
        good = (out / "cyborg.html").read_text(encoding="utf-8")
        r1 = subprocess.run([*CHECK, str(out / "cyborg.html")], cwd=REPO,
                            capture_output=True, text=True)
        assert r1.returncode == 0, f"check must pass valid Top3: {r1.stderr[-2000:]}"
        # 难度错：把产物难度改成 Danger 3，门禁必须挂。
        bad_diff = good.replace("难度：Ultimate", "难度：Danger 3")
        assert bad_diff != good
        probe = Path(tmp.name) / "bad_diff.html"
        probe.write_text(bad_diff, encoding="utf-8")
        r2 = subprocess.run([*CHECK, str(probe)], cwd=REPO, capture_output=True, text=True)
        assert r2.returncode != 0, "invalid difficulty in HTML must fail check"
        # 娱乐局：标题注入 Tier List，门禁必须挂。
        bad_tier = good.replace("Brotato Ultimate", "Brotato Tier List")
        probe2 = Path(tmp.name) / "bad_tier.html"
        probe2.write_text(bad_tier, encoding="utf-8")
        r3 = subprocess.run([*CHECK, str(probe2)], cwd=REPO, capture_output=True, text=True)
        assert r3.returncode != 0, "entertainment in source HTML must fail check"
    finally:
        tmp.cleanup()


def test_check_updates_reports_old_date_recheck() -> None:
    """check_updates 人工触发：旧取材日期命中待重审 warn。"""
    data_dir, templates_dir, out, tmp = make_workdir()
    try:
        src = valid_source()
        src["published"] = OLD_DATE
        src["candidates"][0]["published"] = OLD_DATE
        write_source(data_dir, src)
        r = subprocess.run(
            [*CHECK_UPDATES, "--data-dir", str(data_dir)],
            cwd=REPO, capture_output=True, text=True,
        )
        assert r.returncode == 0, f"version drift must warn not fail: {r.stderr[-2000:]}"
        combined = r.stdout + r.stderr
        assert "待重审" in combined or "重审" in combined
    finally:
        tmp.cleanup()
