"""#17+#20 E2E seam: 字幕x术语交叉表机器 gate + check_mentions 只 warn (覆盖制每变体独立).

Seams under test (pre-agreed per #16 Notes: E2E only):
- `python scripts/build_mentions.py --slug <slug>` exit codes + `data/mentions/<slug>__<variant>.json` bytes
- `python scripts/check_mentions.py --slug <slug>` exit codes (只 warn 不 fail, 每变体独立)

No internal imports, no network. All assertions inspect CLI exit codes
and data file bytes. Fixtures are isolated tmp copies.
"""

from __future__ import annotations

import json
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path

REPO = Path(__file__).resolve().parent.parent
BUILD_MENTIONS = [sys.executable, "scripts/build_mentions.py"]
CHECK_MENTIONS = [sys.executable, "scripts/check_mentions.py"]

# #14 失败批注回归: 字幕明确提到但初版漏定级的 5 项.
# 9移速有点用 / 15幸运备选后放弃 / 9闪避可堆 / 线圈百分比伤害想拿 / 和平蜜蜂扣1近战.
REGRESSION_VTT = """WEBVTT

00:00.000 --> 00:02.000
I picked up 9 movement speed, it's kind of useful early

00:02.000 --> 00:04.000
I considered 15 luck but rolled armor instead

00:04.000 --> 00:06.000
I got 9 dodge, you can stack a bit of dodge here

00:06.000 --> 00:08.000
coil gives percent damage, I want that damage scaling

00:08.000 --> 00:10.000
peaceful bee gives minus 1 melee, I don't care about melee

00:10.000 --> 00:12.000
wrenches only, six wrenches with turrets and coffee
"""

EXPECTED_TERMS = 39


def make_workdir() -> tuple[Path, tempfile.TemporaryDirectory[str]]:
    tmp = tempfile.TemporaryDirectory()
    work = Path(tmp.name) / "work"
    shutil.copytree(REPO / "data", work / "data")
    # #23: repo已有真数据，隔离缝一律用夹具覆盖。
    _fx = REPO / "tests" / "fixtures" / "cyborg.json"
    _bf = work / "data" / "builds" / "cyborg.json"
    if _fx.exists():
        _bf.parent.mkdir(parents=True, exist_ok=True)
        _bf.write_text(_fx.read_text(encoding="utf-8"), encoding="utf-8")
    return (work / "data", tmp)


def write_vtt(data_dir: Path, slug: str, content: str, variant: str = "nightmare") -> Path:
    subs = data_dir / "subs"
    subs.mkdir(parents=True, exist_ok=True)
    # 覆盖制每变体独立存; 测试夹具单变体 nightmare.
    p = subs / f"{slug}__{variant}.en-orig.vtt"
    p.write_text(content, encoding="utf-8")
    return p


def mentions_path(data_dir: Path, slug: str = "cyborg", variant: str = "nightmare") -> Path:
    return data_dir / "mentions" / f"{slug}__{variant}.json"


def run_build_mentions(data_dir: Path, slug: str) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        [*BUILD_MENTIONS, "--slug", slug, "--data-dir", str(data_dir)],
        cwd=REPO, capture_output=True, text=True,
    )


def run_check_mentions(data_dir: Path, slug: str) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        [*CHECK_MENTIONS, "--slug", slug, "--data-dir", str(data_dir)],
        cwd=REPO, capture_output=True, text=True,
    )


def test_build_mentions_produces_cross_table_json() -> None:
    """交叉表格式: data/mentions/<slug>__<variant>.json 含 39 术语 + 武器/道具, 逐个计数附原句."""
    data_dir, tmp = make_workdir()
    try:
        write_vtt(data_dir, "cyborg", REGRESSION_VTT)
        r = run_build_mentions(data_dir, "cyborg")
        assert r.returncode == 0, f"build_mentions must exit 0: {r.stderr[-2000:]}"
        out = mentions_path(data_dir)
        assert out.exists(), "交叉表输出须落 data/mentions/<slug>__<variant>.json (覆盖制每变体)"
        payload = json.loads(out.read_text(encoding="utf-8"))
        assert payload.get("slug") == "cyborg"
        assert payload.get("variant") == "nightmare"
        terms = payload.get("terms")
        assert isinstance(terms, dict) and len(terms) == EXPECTED_TERMS, (
            f"terms 须 39 全量, got {len(terms) if isinstance(terms, dict) else type(terms)}"
        )
        for en, entry in terms.items():
            assert isinstance(entry, dict), f"{en} 须含 count+quotes"
            assert "count" in entry and "quotes" in entry
            assert isinstance(entry["count"], int) and isinstance(entry["quotes"], list)
        # 武器/道具名同样逐个计数附原句.
        for section in ("weapons", "items"):
            sec = payload.get(section)
            assert isinstance(sec, dict) and sec, f"{section} 须非空映射"
            for en, entry in sec.items():
                assert "count" in entry and "quotes" in entry
    finally:
        tmp.cleanup()


def test_regression_14_missed_ratings_are_caught() -> None:
    """#14 回归: Speed/Luck/Dodge/Damage/Melee 字幕有命中, 必须 count>0 附原句."""
    data_dir, tmp = make_workdir()
    try:
        write_vtt(data_dir, "cyborg", REGRESSION_VTT)
        r = run_build_mentions(data_dir, "cyborg")
        assert r.returncode == 0, r.stderr[-2000:]
        payload = json.loads(mentions_path(data_dir).read_text(encoding="utf-8"))
        terms = payload["terms"]
        for en in ("Speed", "Luck", "Dodge", "Damage", "Melee Damage"):
            assert terms[en]["count"] > 0, f"{en} 字幕明确提及, 交叉表必须命中 (否则重演 #14 漏定级)"
            assert terms[en]["quotes"], f"{en} 必须附原句"
        # 未提及项保持 0 (元素/远程经核实一次未提, 空出成立).
        assert terms["Elemental Damage"]["count"] == 0
        assert terms["Ranged Damage"]["count"] == 0
    finally:
        tmp.cleanup()


def test_check_mentions_mentioned_but_unrated_warns_not_fails() -> None:
    """机检: 字幕提到但未定级只 warn, 退出码仍 0, 不动 check.py 门禁."""
    data_dir, tmp = make_workdir()
    try:
        write_vtt(data_dir, "cyborg", REGRESSION_VTT)
        assert run_build_mentions(data_dir, "cyborg").returncode == 0
        # cyborg.json 默认 ratings 无 Speed/Luck/Dodge, 故意触发提到未定级.
        r = run_check_mentions(data_dir, "cyborg")
        assert r.returncode == 0, f"check_mentions 只 warn 不 fail, got {r.returncode}: {r.stderr[-2000:]}"
        combined = (r.stdout or "") + (r.stderr or "")
        assert "WARN" in combined, "提到未定级必须 WARN"
        assert "Speed" in combined or "Luck" in combined or "Dodge" in combined
    finally:
        tmp.cleanup()


def test_check_mentions_rated_without_hit_needs_source() -> None:
    """机检: 定了级但字幕无命中须挂名注明出处 (标题/描述/chapters), 否则疑为编 WARN."""
    data_dir, tmp = make_workdir()
    try:
        # 空字幕: 任何定级都无命中.
        write_vtt(data_dir, "cyborg", "WEBVTT\n\n00:00.000 --> 00:01.000\nhello world\n")
        assert run_build_mentions(data_dir, "cyborg").returncode == 0
        r = run_check_mentions(data_dir, "cyborg")
        assert r.returncode == 0, "只 warn 不 fail"
        combined = (r.stdout or "") + (r.stderr or "")
        # cyborg 默认有 Ranged Damage S 等定级, 空字幕下必须 WARN 挂名.
        assert "WARN" in combined
        assert "Ranged Damage" in combined or "Attack Speed" in combined
    finally:
        tmp.cleanup()


def test_attack_speed_does_not_pollute_speed() -> None:
    """精度: attack speed 不得算作 Speed (移动速度), 否则误报淹没真漏."""
    data_dir, tmp = make_workdir()
    try:
        write_vtt(
            data_dir, "cyborg",
            "WEBVTT\n\n00:00.000 --> 00:02.000\nattack speed is great, take clock\n",
        )
        assert run_build_mentions(data_dir, "cyborg").returncode == 0
        payload = json.loads(mentions_path(data_dir).read_text(encoding="utf-8"))
        assert payload["terms"]["Attack Speed"]["count"] > 0
        assert payload["terms"]["Speed"]["count"] == 0, "attack speed 不得污染 Speed"
    finally:
        tmp.cleanup()
