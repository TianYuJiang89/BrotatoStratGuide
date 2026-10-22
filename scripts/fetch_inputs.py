#!/usr/bin/env python3
"""Step00 取证 (#44, #61 slice 退役): video URL -> G work inputs/ 三件 (固定代码, 无 agent 判断).

输入 (人/agent 只给这两样 + 必要时 cookies):
  video URL + --slug/--variant [+ --cookies youtube.com cookies.txt]

固定动作 (yt-dlp, 确定性):
  --dump-json 抓 title/duration/upload_date/description/chapters
  有人工字幕用人工, 否则自动 (--write-subs / --write-auto-subs, --sub-langs en)
  直写 G work inputs/ 三件: source.vtt/meta.json/manifest.json
  记 subs_source=auto/manual + sha1 + URL.

fail loud (禁静默):
  无字幕 / 被风控 / 抓不到 meta 即报错退出 (exit 1).
  不猜测, 不重转写, 不回落其它来源.
  cookie 协作沿旧 SOP: 人出 youtube.com cookies.txt, agent 用,
  失效提示重出 (见报错文案).

用法:
  python scripts/fetch_inputs.py --url <youtube-url> --slug cyborg --variant ultimate
  python scripts/fetch_inputs.py --url <youtube-url> --slug cyborg --variant ultimate --cookies cookies.txt
  python scripts/fetch_inputs.py --url <youtube-url> --slug engineer --variant ultimate --work-root G:/brotato-work
"""

from __future__ import annotations

import argparse
import hashlib
import json
import re
import shutil
import subprocess
import sys
import tempfile
from datetime import datetime
from pathlib import Path
from typing import NoReturn

REPO = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(REPO / "scripts"))

from build_mentions import (  # noqa: E402
    detect_subs_source,
)


def _fail(msg: str) -> NoReturn:
    print(f"FAIL: {msg}", file=sys.stderr)
    raise SystemExit(1)


def normalize_published(upload_date: str) -> str:
    """upload_date YYYYMMDD -> YYYY-MM-DD (已是横线格式则直通, 空即报错)."""
    s = (upload_date or "").strip()
    if re.fullmatch(r"\d{4}-\d{2}-\d{2}", s):
        return s
    if re.fullmatch(r"\d{8}", s):
        return f"{s[:4]}-{s[4:6]}-{s[6:8]}"
    _fail(f"bad upload_date (meta 抓不到 published): {upload_date!r}")


def default_difficulty(variant: str) -> str:
    """variant -> Difficulty 显示名 (单变体默认, 多段需显式 --difficulty)."""
    v = (variant or "").strip()
    if not v:
        _fail("empty variant")
    return v.replace("-", " ").title()


def default_covers(variant: str, difficulty: str) -> list[str]:
    """单变体默认单 cover (多难度合一需显式 --covers, 不猜)."""
    _ = variant
    return [difficulty]


def _has_en(entry: object) -> bool:
    if isinstance(entry, dict):
        for k in entry.keys():
            if isinstance(k, str) and (k == "en" or k.startswith("en-") or k.startswith("en.")):
                v = entry[k]
                if isinstance(v, list) and len(v) > 0:
                    return True
    return False


def pick_subs(dump: dict) -> tuple[str, str, bool]:
    """选字幕: 有人工用人工, 否则自动; 均无即报错 (无字幕 fail loud).

    返回 (lang, subs_source, use_manual).
    """
    subs = dump.get("subtitles") or {}
    autos = dump.get("automatic_captions") or {}
    if _has_en(subs):
        return ("en", "manual", True)
    if _has_en(autos):
        return ("en", "auto", False)
    _fail("no en subtitles (manual/auto 均无, 不猜测不重转写); "
          "若视频确有字幕, 检查 --sub-langs 或确认视频公开状态")


def build_meta(dump: dict, difficulty: str, subs_source: str) -> dict:
    title = str(dump.get("title") or "").strip()
    video_id = str(dump.get("id") or "").strip()
    if not title or not video_id:
        _fail("meta 抓不到 title/video_id")
    duration = str(dump.get("duration_string") or dump.get("duration") or "").strip()
    if not duration:
        _fail("meta 抓不到 duration")
    published = normalize_published(str(dump.get("upload_date") or ""))
    description = str(dump.get("description") or "")
    chapters_raw = dump.get("chapters") or []
    if not isinstance(chapters_raw, list):
        _fail("meta chapters 非数组 (yt-dlp 原值异常)")
    # #67 章节门拆除: 无章节不再 fail（#63 segmentation 已退役章节分桶，空数组照发，下游不读章节）。
    chapters: list[dict] = []
    for c in chapters_raw:
        if not isinstance(c, dict):
            _fail(f"meta chapters 非对象 (yt-dlp 原值异常): {c!r}"[:200])
        ctitle = str(c.get("title") or "").strip()
        start = c.get("start_time")
        end = c.get("end_time")
        if not ctitle:
            _fail("meta chapters 缺 title (yt-dlp 原值异常)")
        if not isinstance(start, (int, float)) or not isinstance(end, (int, float)):
            _fail(f"meta chapters 缺 start_time/end_time (秒, yt-dlp 原值): {ctitle[:60]}")
        chapters.append({"title": ctitle, "start": start, "end": end})
    url = str(dump.get("webpage_url") or f"https://www.youtube.com/watch?v={video_id}")
    return {
        "title": title,
        "description": description,
        "published": published,
        "duration": duration,
        "chapters": chapters,
        "video_id": video_id,
        "url": url,
        "difficulty": difficulty,
        "subs_source": subs_source,
    }


def build_manifest(slug: str, variant: str, covers: list[str],
                   meta: dict, sha1: str, sop_version: str, issue: int) -> dict:
    return {
        "slug": slug,
        "variant": variant,
        "covers": covers,
        "sop_version": sop_version,
        "issue": issue,
        "subs_source": meta.get("subs_source", ""),
        "sources": [
            {
                "difficulty": meta.get("difficulty", ""),
                "title": meta.get("title", ""),
                "url": meta.get("url", ""),
                "sha1": sha1,
                "vtt": "inputs/source.vtt",
                "duration": meta.get("duration", ""),
                "published": meta.get("published", ""),
                "video_id": meta.get("video_id", ""),
            }
        ],
    }


# #61 退役: build_registry_slice 已删 (scan 子串 scope 作废, completeness 归 discovery agent).


def backup_variant_dir(workdir: Path) -> Path | None:
    """换片自动清场 (#69): 既有变体目录整搬备份, 返回备份路径; 不存在返回 None (只搬不删)."""
    if not workdir.exists():
        return None
    stamp = datetime.now().strftime("%Y%m%d-%H%M%S")
    dest = workdir.parent / f"{workdir.name}.bak.{stamp}"
    n = 1
    while dest.exists():
        n += 1
        dest = workdir.parent / f"{workdir.name}.bak.{stamp}-{n}"
    shutil.move(str(workdir), str(dest))
    return dest


def _sop_version() -> str:
    try:
        p = subprocess.run(
            ["git", "log", "-1", "--format=%H", "--",
             "docs/sop/new-character-guide.md"],
            cwd=str(REPO), capture_output=True, text=True)
        return p.stdout.strip()
    except Exception:
        return ""


def _valid_slug(s: str) -> bool:
    return bool(re.fullmatch(r"[a-z0-9]+(?:-[a-z0-9]+)*", s))


def fetch_dump_json(url: str, cookies: str | None) -> dict:
    cmd = ["yt-dlp", "--skip-download", "--dump-json", "--no-progress"]
    if cookies:
        cmd += ["--cookies", cookies]
    cmd += [url]
    try:
        p = subprocess.run(cmd, capture_output=True, text=True)
    except FileNotFoundError:
        _fail("yt-dlp 未安装或不在 PATH")
    if p.returncode != 0:
        err = (p.stderr or p.stdout or "")[-2000:]
        hint = ""
        low = err.lower()
        if any(k in low for k in ("sign in", "log in", "403", "private", "cookies")):
            hint = ("疑被风控/需登录: 人重出 youtube.com cookies.txt, "
                    "agent 用 --cookies 重跑")
        _fail(f"yt-dlp meta 抓取失败{(';' + hint) if hint else ''}: {err[:500]}")
    try:
        return json.loads(p.stdout)
    except Exception:
        _fail(f"yt-dlp meta 解析失败 (非 JSON): {(p.stdout or '')[:300]}")


def download_vtt(url: str, use_manual: bool, cookies: str | None,
                 tmpdir: Path, video_id: str) -> Path:
    flag = "--write-subs" if use_manual else "--write-auto-subs"
    out_tmpl = str(tmpdir / "%(id)s.%(ext)s")
    cmd = ["yt-dlp", "--skip-download", flag,
           "--sub-langs", "en", "--sub-format", "vtt",
           "--convert-subs", "vtt", "--no-progress",
           "-o", out_tmpl]
    if cookies:
        cmd += ["--cookies", cookies]
    cmd += [url]
    try:
        p = subprocess.run(cmd, capture_output=True, text=True)
    except FileNotFoundError:
        _fail("yt-dlp 未安装或不在 PATH")
    if p.returncode != 0:
        err = (p.stderr or p.stdout or "")[-2000:]
        hint = ""
        low = err.lower()
        if any(k in low for k in ("sign in", "log in", "403", "private", "cookies")):
            hint = ("疑被风控/需登录: 人重出 youtube.com cookies.txt, "
                    "agent 用 --cookies 重跑")
        _fail(f"yt-dlp 字幕下载失败{(';' + hint) if hint else ''}: {err[:500]}")
    cands = sorted(tmpdir.glob("*.vtt"))
    if not cands:
        _fail("字幕下载后无 VTT 落盘 (无字幕即报错, 不猜测)")
    # 首选 <id>.en.vtt, 否则首个
    want = tmpdir / f"{video_id}.en.vtt"
    if want.exists():
        return want
    for c in cands:
        if c.name.endswith(".en.vtt"):
            return c
    return cands[0]


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description="Step00 取证 (#44)")
    ap.add_argument("--url", required=True)
    ap.add_argument("--slug", required=True)
    ap.add_argument("--variant", required=True)
    ap.add_argument("--work-root", default="G:/brotato-work")
    ap.add_argument("--cookies", default="")
    ap.add_argument("--difficulty", default="")
    ap.add_argument("--covers", default="")
    ap.add_argument("--issue", type=int, default=44)
    args = ap.parse_args(argv)

    url = args.url.strip()
    slug = args.slug.strip()
    variant = args.variant.strip()
    if "youtube.com" not in url and "youtu.be" not in url:
        _fail(f"bad url (只认 youtube): {url[:80]}")
    if not _valid_slug(slug):
        _fail(f"bad slug: {slug!r}")
    if not _valid_slug(variant):
        _fail(f"bad variant: {variant!r}")

    cookies = (args.cookies or "").strip() or None
    if cookies and not Path(cookies).exists():
        _fail(f"cookies 文件不存在: {cookies} (人出 youtube.com cookies.txt)")

    difficulty = (args.difficulty or "").strip() or default_difficulty(variant)
    if (args.covers or "").strip():
        covers = [c.strip() for c in str(args.covers).split(",") if c.strip()]
        if not covers:
            _fail("bad --covers (空)")
    else:
        covers = default_covers(variant, difficulty)

    dump = fetch_dump_json(url, cookies)
    _lang, _expected_source, use_manual = pick_subs(dump)

    with tempfile.TemporaryDirectory(prefix="fetch_inputs_") as td:
        tmpdir = Path(td)
        video_id = str(dump.get("id") or "").strip()
        if not video_id:
            _fail("meta 抓不到 video_id")
        vtt_path = download_vtt(url, use_manual, cookies, tmpdir, video_id)
        try:
            raw = vtt_path.read_bytes()
        except Exception:
            _fail(f"VTT 读失败: {vtt_path}")
        try:
            vtt_text = raw.decode("utf-8")
        except Exception:
            _fail("VTT 非 utf-8 (无字幕即报错)")
        if not vtt_text.strip():
            _fail("VTT 为空 (无字幕即报错)")

    subs_source = detect_subs_source(vtt_text)
    sha1 = hashlib.sha1(raw).hexdigest()
    meta = build_meta(dump, difficulty, subs_source)
    manifest = build_manifest(slug, variant, covers, meta,
                              sha1, _sop_version(), args.issue)

    workdir = Path(args.work_root) / slug / variant
    # #69 换片自动清场: 既有取证且 video_id 不同 -> 整目录备份后重建 (不清则新旧混跑, 见 #68).
    # 同 id 原地覆盖 (幂等); 无既有直写. 只搬不删.
    _old_id = ""
    try:
        _old_manifest = json.loads((workdir / "inputs" / "manifest.json").read_text(encoding="utf-8"))
        _old_srcs = _old_manifest.get("sources") or []
        _old_id = str((_old_srcs[0].get("video_id") if _old_srcs else "") or "")
    except Exception:
        _old_id = ""
    if _old_id and _old_id != video_id:
        _bak = backup_variant_dir(workdir)
        print(f"video changed ({_old_id} -> {video_id}): backup {workdir} -> {_bak}")
    inputs = workdir / "inputs"
    inputs.mkdir(parents=True, exist_ok=True)
    (inputs / "source.vtt").write_bytes(raw)
    (inputs / "meta.json").write_text(
        json.dumps(meta, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    # #61 退役: 旧 registry-slice.json 若残留即删 (fetch 停产)
    _stale = inputs / "registry-slice.json"
    if _stale.exists():
        try:
            _stale.unlink()
        except Exception:
            pass
    (inputs / "manifest.json").write_text(
        json.dumps(manifest, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(f"OK: step00 inputs 三件 -> {inputs} "
          f"(subs_source={subs_source} sha={sha1[:8]} issue={args.issue})")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
