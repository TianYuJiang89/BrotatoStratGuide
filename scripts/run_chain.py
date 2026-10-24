#!/usr/bin/env python3
"""真链路 orchestrator (#55): 主脚本自动调真子 agent 跑通 06/08 wordings.

Deterministic-first + No silent fallback:
- Step00 取证 (固定代码, scripts/fetch_inputs.py) -> 01-05 确定性 (scripts/run_segment1.py)
  -> 06 (buckets 代码 -> 真 agent 写 wordings -> merge 代码)
  -> 08 (recall 代码 -> 真 agent 写 wordings -> merge 代码)
  -> 07 确定性 -> 09 聚合 -> 双 check -> 审计常设视图只读校验.
- 缺件/红灯即 fail loud, 不回落、不补空、不编数字.
- 沿用已定口径 (#52-Q1-Q4, #54 后仍有效; 成本熔断已全取消, 主脚本不做记账与熔断, 不加帽):
  - 重试: RPC transient (spawn 失败/JSONL 断流/timeout) max 2 (退避 5s->15s);
    缺件/格式错 max 1 (同 cwd 覆盖立即重跑一次); check 红灯永不重试 (重修唯一正路).
  - 复用: 已绿步骤跳过不跑 (存在 + schema 绿即 SKIP 打 log); --force-step 才覆盖.
  - 幂等: 同 cwd 覆盖不开新目录; manifest sha == source.vtt 实算 sha;
    每步落盘存在 + JSON 可解析 + schema 最小键齐; 跨步 sha 链 (09 guide.sha == manifest sha).
  - 重修: check 红灯必须修 prompt/代码后再跑, 不直接重试本步.
- 子 agent 调用 (沿 #35 SDK 调研结论):
  - Python 起 RPC 子进程一步一起 (--no-session), spawn cwd 锁到 G:/brotato-work/<slug>/<variant>/,
    最小工具集 (read,write,bash), 只喂本步子 prompt 全文 (prompts/step06-phases-fewshot.md /
    prompts/step08-pitfalls-fewshot.md), 不喂旧 SOP 全文、不跨步.
  - 主脚本只做 cwd 锁 + 必要文件已在位校验 + sha 校验 + 重试计数 + fail loud;
    子 prompt 只写本步 SOP + 只读写相对路径, 不给重试/预算语.
- 验收: cyborg/ultimate 用新 orchestrator 从零重跑一次 (旧 G 目录先备份再清),
  06/08 wordings 须为真子进程产物 (附进程日志/落盘时间证明非手写), 双 check 全绿,
  审计同目录可读, sha 对上.

约束: 不改锚规则与 schema (换筐已收敛, 只接线不重议); 不选片 (只吃 URL+slug+variant, 来源写 manifest).

用法:
  python scripts/run_chain.py --slug cyborg --variant ultimate
  python scripts/run_chain.py --slug cyborg --variant ultimate --url <youtube-url>
  python scripts/run_chain.py --slug cyborg --variant ultimate --force-step 06-wordings,08-wordings
  python scripts/run_chain.py --slug cyborg --variant ultimate --force-step all
"""

from __future__ import annotations

import argparse
import hashlib
import json
import queue
import re
import shutil
import subprocess
import sys
import threading
import time
from datetime import datetime, timezone
from pathlib import Path

REPO = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(REPO / "scripts"))

# 复用确定性代码 (不改锚规则与 schema, 只接线):
# - run_segment1: ensure_inputs + step01..step05
# - run_segment2: step06 (segmentation/wording #63) + step08 (discovery/wording #64) + step07/step09
# - fetch_inputs: Step00 取证
# - check_segment1/check_segment2: 双 check


class TransientError(RuntimeError):
    """RPC transient: spawn 失败/JSONL 断流/timeout (可重试, max 2, 退避 5s->15s)."""


class MissingError(RuntimeError):
    """落盘缺件: agent settled 后无 wordings 落盘 (可重试, max 1, 立即)."""


class FormatError(RuntimeError):
    """agent 输出格式错: wordings schema 校验失败 (可重试, max 1, 立即)."""


TRANSIENT_BACKOFF = (5.0, 15.0)  # Q2: transient max 2, 退避 5s->15s
LIVENESS_TIMEOUT = 1800.0  # 子进程 liveness 超时 (防 hung, 非成本帽; 沿 #54 不做熔断记账)


def _pi_cmd() -> str:
    found = shutil.which("pi")
    if found:
        return found
    for cand in ("F:/Pi/CLI/pi.cmd", "F:/Pi/CLI/pi", "pi.cmd"):
        if Path(cand).exists():
            return cand
    return "pi"


def build_agent_cmd() -> list[str]:
    """RPC 子进程命令 (沿 #35: --no-session + 最小工具集 + 隔离旗)."""
    return [
        _pi_cmd(), "--mode", "rpc", "--no-session",
        "--no-skills", "--no-extensions", "--no-prompt-templates", "--no-context-files",
        "--tools", "read,write,bash", "--thinking", "off",
    ]


def _sha1_text(s: str) -> str:
    return hashlib.sha1(s.encode("utf-8")).hexdigest()


def parse_force_steps(s: str) -> set[str]:
    """--force-step 解析: 逗号分隔, 支持 all/06/08 简写. 返回规范键集合."""
    raw = [p.strip() for p in (s or "").split(",") if p.strip()]
    out: set[str] = set()
    for p in raw:
        if p == "all":
            return {"all"}
        out.add(p)
    return out


def should_force(key: str, force: set[str]) -> bool:
    """复用/幂等 Q4: 默认复用已绿, --force-step 才覆盖."""
    if not force or "all" in force:
        return "all" in force
    if key in force:
        return True
    # 简写: 06 -> 06-buckets/06-wordings/06-merge 全覆; 08 -> 08-recall/08-wordings 全覆.
    if key.startswith("06-") and "06" in force:
        return True
    if key.startswith("08-") and "08" in force:
        return True
    return False


def _load_json(path: Path):
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except Exception:
        return None


def _reuse_ok_sentences(path: Path) -> bool:
    d = _load_json(path)
    return isinstance(d, list) and len(d) > 0


def _reuse_ok_grouping(path: Path) -> bool:
    # #62 新 schema + #74 六组 {name_en,count,group,quotes,analysis,note,quote_details}, 旧件退役
    # #74 披露也进复用门: wishlist 须没拿到/未拿到, taken 须无下文, 否则不复用 (须重跑)
    d = _load_json(path)
    if not (isinstance(d, list) and len(d) > 0):
        return False
    try:
        for r in d:
            if not isinstance(r, dict):
                return False
            for k in ("name_en", "count", "group", "quotes", "analysis", "note", "quote_details"):
                if k not in r:
                    return False
            if r.get("group") not in ("must_take", "wishlist", "taken", "mentioned_not_taken", "ban", "casual_mention"):
                return False
            if r.get("group") == "wishlist" and ("没拿到" not in str(r.get("note", "")) and "未拿到" not in str(r.get("note", ""))):
                return False
            if r.get("group") == "taken" and "无下文" not in str(r.get("note", "")):
                return False
            for _old in ("tier", "confidence", "inferred", "has_verb", "verb",
                          "verb_type", "mapped_to", "reason"):
                if _old in r:
                    return False
        return True
    except Exception:
        return False


def _reuse_ok_ratings(path: Path) -> bool:
    # #60: 新 schema {term_en,term_zh,type,count,rating,quotes,analysis,summary,quote_details}, 旧四件退役
    d = _load_json(path)
    if not (isinstance(d, list) and len(d) == 39):
        return False
    try:
        for r in d:
            if not isinstance(r, dict):
                return False
            for k in ("term_en", "count", "rating", "quotes", "analysis", "summary", "quote_details"):
                if k not in r:
                    return False
            for _old in ("anchors", "confidence", "kind", "inferred", "reason"):
                if _old in r:
                    return False
        return True
    except Exception:
        return False


def _reuse_ok_weapons(path: Path) -> bool:
    # #61: 新 schema {name_en,count,tier,quotes,analysis,note,quote_details}, 旧六件退役
    d = _load_json(path)
    if not (isinstance(d, dict) and isinstance(d.get("t1"), list) and isinstance(d.get("t2"), list)):
        return False
    try:
        for w in (d.get("t1", []) + d.get("t2", [])):
            if not isinstance(w, dict):
                return False
            for k in ("name_en", "count", "tier", "quotes", "analysis", "note", "quote_details"):
                if k not in w:
                    return False
            for _old in ("anchors", "confidence", "kind", "inferred", "score", "reason"):
                if _old in w:
                    return False
        return True
    except Exception:
        return False


def _url_video_id(url: str) -> str:
    """从 URL 解析 video id (#69, 无网络): watch?v=/youtu.be/shorts/live/embed; 解析失败返回 ''."""
    from urllib.parse import urlparse, parse_qs
    try:
        u = (url or "").strip()
        if not u:
            return ""
        p = urlparse(u if "://" in u else "https://" + u)
        host = (p.hostname or "").lower()
        if "youtu.be" in host:
            seg = (p.path or "").strip("/").split("/")
            return seg[0] if seg and re.fullmatch(r"[A-Za-z0-9_-]{6,}", seg[0]) else ""
        qs = parse_qs(p.query or "")
        for v in (qs.get("v") or []):
            if re.fullmatch(r"[A-Za-z0-9_-]{6,}", v):
                return v
        m = re.search(r"/(?:shorts|live|embed)/([A-Za-z0-9_-]{6,})", p.path or "")
        return m.group(1) if m else ""
    except Exception:
        return ""


def ensure_step00(slug: str, vid: str, workdir: Path, url: str = "", cookies: str = "") -> dict:
    """Step00 取证 (固定代码): 只吃 URL+slug+variant, 来源写 manifest. 缺件即 fail loud.

    - inputs 三件已在 -> 直接校验 (沿 run_segment1.ensure_inputs: sha 对上, #67 章节不验, #61 slice 已退役).
    - 显式 --url 且三件齐 -> 先比 video_id: 同片跳过 (幂等不重下), 换片才重取 (fetch 内整目录备份, #69).
    - inputs 缺件 + --url 已给 -> 调 fetch_inputs 取证后校验.
    - inputs 缺件 + 无 --url -> fail loud (指引先给 URL 取证, 不猜测不回落).
    """
    from run_segment1 import ensure_inputs as _ensure
    inputs = workdir / "inputs"
    need = ["source.vtt", "meta.json", "manifest.json"]
    missing = [f for f in need if not (inputs / f).exists()]
    if (url or "").strip():
        if not missing:
            _want = _url_video_id(url)
            _have = ""
            try:
                _m = json.loads((inputs / "manifest.json").read_text(encoding="utf-8"))
                _srcs = _m.get("sources") or []
                _have = str((_srcs[0].get("video_id") if _srcs else "") or "")
            except Exception:
                _have = ""
            if _want and _have and _want == _have:
                return _ensure(slug, vid, workdir)
        from fetch_inputs import main as _fetch_main
        argv = ["--url", url.strip(), "--slug", slug, "--variant", vid,
                "--work-root", str(workdir.parent.parent), "--issue", "55"]
        if (cookies or "").strip():
            argv += ["--cookies", cookies.strip()]
        print(f"[chain] Step00 取证: fetch_inputs {' '.join(argv)}")
        rc = _fetch_main(argv)
        if rc != 0:
            raise SystemExit(f"FAIL: Step00 fetch_inputs exit {rc} (取证失败即 fail loud)")
    elif missing:
        raise SystemExit(
            f"FAIL: missing inputs/{missing[0]} for {slug}/{vid}: "
            f"先跑 scripts/fetch_inputs.py --url <youtube-url> --slug {slug} --variant {vid} 取证 "
            f"(或本脚本加 --url 同跑; 不猜测不回落)")
    return _ensure(slug, vid, workdir)


def _spawn_once(workdir: Path, prompt_text: str, output_rel: str,
                log_path: Path, jsonl_path: Path, timeout: float) -> Path:
    """单次 RPC spawn (无重试): 发本步 prompt 全文, 等 agent_settled, 校验落盘 + mtime 证明.

    返回 output 路径. transient (spawn/JSONL/timeout) 抛 TransientError;
    settled 后无落盘抛 MissingError (调用方按缺件口径重试 max 1).
    全程写进程日志 (log_path 人读 + jsonl_path 原始 JSONL), 落盘 mtime 须 > spawn 起始.
    """
    start_wall = time.time()
    start_iso = datetime.now(timezone.utc).isoformat()
    out_path = workdir / output_rel
    pre_mtime = out_path.stat().st_mtime if out_path.exists() else 0.0
    cmd = build_agent_cmd()
    log_path.parent.mkdir(parents=True, exist_ok=True)
    jsonl_path.parent.mkdir(parents=True, exist_ok=True)
    with open(log_path, "a", encoding="utf-8") as lg:
        lg.write(f"[{start_iso}] spawn cwd={workdir} cmd={' '.join(cmd)}\n")
        lg.write(f"prompt_len={len(prompt_text)} prompt_sha={_sha1_text(prompt_text)}\n")
        lg.write(f"output={output_rel} pre_mtime={pre_mtime:.3f} timeout={timeout:.0f}s\n")
        lg.flush()
    try:
        proc = subprocess.Popen(
            cmd, cwd=str(workdir), stdin=subprocess.PIPE, stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT, text=True, encoding="utf-8", errors="replace", bufsize=1)
    except Exception as e:
        with open(log_path, "a", encoding="utf-8") as lg:
            lg.write(f"SPAWN FAIL: {e!r}\n")
        raise TransientError(f"spawn failed: {e!r}")

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

    def _log(msg: str) -> None:
        iso = datetime.now(timezone.utc).isoformat()
        with open(log_path, "a", encoding="utf-8") as lg:
            lg.write(f"[{iso}] {msg}\n")

    try:
        assert proc.stdin is not None
        req = {"id": "chain-1", "type": "prompt", "message": prompt_text}
        try:
            proc.stdin.write(json.dumps(req, ensure_ascii=False) + "\n")
            proc.stdin.flush()
        except Exception as e:
            raise TransientError(f"stdin write failed (JSONL 断流): {e!r}")
        settled = False
        deadline = start_wall + timeout
        buf = ""
        while time.time() < deadline:
            try:
                line = q.get(timeout=max(1.0, deadline - time.time()))
            except queue.Empty:
                continue
            if line is None:
                break
            buf = line.strip()
            if not buf:
                continue
            try:
                evt = json.loads(buf)
            except Exception as e:
                raise TransientError(f"JSONL parse failed (断流): {e!r} :: {buf[:200]}")
            if isinstance(evt, dict) and evt.get("type") == "agent_settled":
                settled = True
                break
        if not settled:
            raise TransientError(f"liveness timeout {timeout:.0f}s (agent 未 settled, 防 hung 非成本帽)")
    finally:
        # 落盘原始 JSONL (进程日志证明非手写) + 优雅关闭子进程 (一步一 session, 跑完即销毁).
        try:
            with open(jsonl_path, "a", encoding="utf-8") as jf:
                for ln in raw_lines:
                    jf.write(ln if ln.endswith("\n") else ln + "\n")
        except Exception:
            pass
        try:
            if proc.stdin is not None:
                try:
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
    # settled 后给落盘 5s 宽限, 仍无文件即缺件 (MissingError, 调用方 max 1 立即重跑).
    for _ in range(50):
        if out_path.exists():
            break
        time.sleep(0.1)
    if not out_path.exists():
        _log(f"missing output after settled: {output_rel} (缺件即 fail/retry, 不补空)")
        raise MissingError(f"missing {output_rel} after agent_settled (缺件, 不补空不编数字)")
    mtime = out_path.stat().st_mtime
    end_iso = datetime.now(timezone.utc).isoformat()
    _log(f"output mtime={mtime:.3f} start_wall={start_wall:.3f} "
         f"newer={mtime > start_wall} (落盘时间证明非手写)")
    with open(log_path, "a", encoding="utf-8") as lg:
        lg.write(f"[{end_iso}] done output={output_rel} mtime={mtime:.3f}\n")
    if not (mtime > start_wall or (pre_mtime and mtime >= pre_mtime)):
        # 从零重跑 pre_mtime==0, 须 mtime > start; 复用强制覆盖 pre_mtime>0, 须有更新.
        _log("WARN: mtime 未更新 (疑非本进程落盘, 继续校验 schema, 由调用方判定)")
    return out_path


def spawn_step_agent(workdir: Path, prompt_rel: str, output_rel: str,
                     log_rel: str, timeout: float = LIVENESS_TIMEOUT,
                     validator=None) -> Path:
    """真子 agent 调起 (重试/复用口径 Q1-Q2):

    - transient (spawn/JSONL/timeout): max 2, 退避 5s->15s.
    - 缺件/格式错: max 1, 同 cwd 覆盖立即重跑一次.
    - validator: 落盘后 schema 校验回调 (抛 SystemExit/Exception 即格式错).
    - 全程 fail loud: 到顶保留现场 (inputs/steps 原样 + 进程日志), 不回落不补空.
    """
    prompt_path = REPO / prompt_rel
    if not prompt_path.exists():
        raise SystemExit(f"FAIL: missing prompt {prompt_rel} (子 prompt 只喂本步全文, 缺件即 fail)")
    prompt_text = prompt_path.read_text(encoding="utf-8")
    log_path = workdir / log_rel
    jsonl_path = log_path.with_suffix(".jsonl")
    # 缺件/格式错计数 (max 1); transient 计数 (max 2, 退避 5s->15s).
    missing_or_format_retries = 0
    transient_retries = 0
    attempt = 0
    while True:
        attempt += 1
        try:
            out = _spawn_once(workdir, prompt_text, output_rel, log_path, jsonl_path, timeout)
        except TransientError as e:
            if transient_retries >= 2:
                raise SystemExit(f"FAIL: agent transient 到顶 (max 2) for {output_rel}: {e} "
                                 f"(现场保留 + 进程日志见 {log_rel}, 不回落)")
            wait = TRANSIENT_BACKOFF[transient_retries] if transient_retries < len(TRANSIENT_BACKOFF) else 15.0
            iso = datetime.now(timezone.utc).isoformat()
            with open(log_path, "a", encoding="utf-8") as lg:
                lg.write(f"[{iso}] transient retry {transient_retries + 1}/2 after {wait:.0f}s: {e}\n")
            time.sleep(wait)
            transient_retries += 1
            continue
        except MissingError as e:
            if missing_or_format_retries >= 1:
                raise SystemExit(f"FAIL: agent 缺件到顶 (max 1) for {output_rel}: {e} "
                                 f"(现场保留 + 进程日志见 {log_rel}, 不补空)")
            missing_or_format_retries += 1
            iso = datetime.now(timezone.utc).isoformat()
            with open(log_path, "a", encoding="utf-8") as lg:
                lg.write(f"[{iso}] missing retry 1/1 immediate: {e}\n")
            continue
        # 落盘后 schema 校验 (格式错 max 1 立即重跑).
        if validator is not None:
            try:
                validator()
            except SystemExit as e:
                if missing_or_format_retries >= 1:
                    raise SystemExit(f"FAIL: agent 格式错到顶 (max 1) for {output_rel}: {e} "
                                     f"(现场保留 + 进程日志见 {log_rel}, 不编数字)")
                missing_or_format_retries += 1
                iso = datetime.now(timezone.utc).isoformat()
                with open(log_path, "a", encoding="utf-8") as lg:
                    lg.write(f"[{iso}] format retry 1/1 immediate: {e}\n")
                continue
            except Exception as e:
                if missing_or_format_retries >= 1:
                    raise SystemExit(f"FAIL: agent 格式错到顶 (max 1) for {output_rel}: {e!r}")
                missing_or_format_retries += 1
                continue
        return out


def run_01_05(workdir: Path, force: set[str]) -> tuple[list[dict], list[dict], list[dict], dict]:
    """01/03/04/05 确定性 (复用已绿 SKIP, 否则跑代码; 幂等: 同输入同代码必同文件; #66 02 已退役)."""
    from run_segment1 import step01, step03, step04, step05
    # 01-sentences
    s_path = workdir / "steps" / "01-sentences" / "sentences.json"
    if not should_force("01", force) and _reuse_ok_sentences(s_path):
        print("[chain] 01-sentences SKIP (复用已绿)")
        sentences = _load_json(s_path)
    else:
        sentences = step01(workdir)
        print(f"[chain] 01-sentences DONE: {len(sentences)} 句 -> steps/01-sentences/sentences.json")
    assert isinstance(sentences, list) and sentences
    if not (300 <= len(sentences) <= 600):
        raise SystemExit(f"FAIL: sentences count {len(sentences)} 越界 300-600 (折叠后; 偏差即 fail)")
    # #66 02-verbs 已退役: 01 直达 03/04/05, 不经 02, verbs.json 停产.
    # 03-grouping
    g_path = workdir / "steps" / "03-grouping" / "grouping.json"
    if not should_force("03", force) and _reuse_ok_grouping(g_path):
        print("[chain] 03-grouping SKIP (复用已绿)")
        grouping = _load_json(g_path)
    else:
        grouping = step03(workdir, sentences, force=should_force("03", force))
        print(f"[chain] 03-grouping DONE: {len(grouping)} 件")
    # 04-attributes
    r_path = workdir / "steps" / "04-attributes" / "ratings.json"
    if not should_force("04", force) and _reuse_ok_ratings(r_path):
        print("[chain] 04-attributes SKIP (复用已绿)")
        ratings = _load_json(r_path)
    else:
        ratings = step04(workdir, sentences, force=should_force("04", force))
        print(f"[chain] 04-attributes DONE: {len(ratings)} terms")
    # 05-weapons
    w_path = workdir / "steps" / "05-weapons" / "weapons.json"
    if not should_force("05", force) and _reuse_ok_weapons(w_path):
        print("[chain] 05-weapons SKIP (复用已绿)")
        weapons = _load_json(w_path)
    else:
        weapons = step05(workdir, sentences, force=should_force("05", force))
        print(f"[chain] 05-weapons DONE: T1={len(weapons['t1'])} T2={len(weapons['t2'])}")
    return sentences, grouping, ratings, weapons


def run_06(workdir: Path, sentences: list[dict], force: set[str],
           timeout: float = LIVENESS_TIMEOUT) -> list[dict]:
    """06-phases (#63: frozen fewshot + segmentation/wording 两段 agent)."""
    from run_segment2 import step06 as _step06
    force06 = should_force("06", force) or should_force("06-wordings", force) or should_force("06-buckets", force) or should_force("06-merge", force)
    # 复用: buckets+wordings+phases+fewshot 存在即 SKIP (schema 绿由 check 验, 此处只验存在)
    b_ok = (workdir / "steps" / "06-phases" / "buckets.json").exists()
    w_ok = (workdir / "steps" / "06-phases" / "wordings.json").exists()
    p_ok = (workdir / "steps" / "06-phases" / "phases.json").exists()
    f_ok = (workdir / "steps" / "06-phases" / "fewshot.md").exists()
    if not force06 and b_ok and w_ok and p_ok and f_ok:
        print("[chain] 06-phases SKIP (复用已绿)")
        return _load_json(workdir / "steps" / "06-phases" / "phases.json")
    phases = _step06(workdir, sentences, force=force06, timeout=timeout, thinking="medium")
    print(f"[chain] 06-phases DONE: N={len(phases)} -> steps/06-phases/phases.json (segmentation 自定义波次)")
    return phases


def run_08(workdir: Path, sentences: list[dict], grouping, force: set[str],
           timeout: float = LIVENESS_TIMEOUT) -> list[dict]:
    """08-pitfalls (#64: frozen fewshot + discovery/wording 两段 agent; 码召回已退役)."""
    from run_segment2 import step08 as _step08
    force08 = should_force("08", force) or should_force("08-wordings", force) or should_force("08-recall", force)
    p_ok = (workdir / "steps" / "08-pitfalls" / "pitfalls.json").exists()
    c_ok = (workdir / "steps" / "08-pitfalls" / "candidates.json").exists()
    w_ok = (workdir / "steps" / "08-pitfalls" / "wordings.json").exists()
    f_ok = (workdir / "steps" / "08-pitfalls" / "fewshot.md").exists()
    if not force08 and p_ok and c_ok and w_ok and f_ok:
        print("[chain] 08-pitfalls SKIP (复用已绿)")
        return _load_json(workdir / "steps" / "08-pitfalls" / "pitfalls.json")
    pitfalls = _step08(workdir, sentences, grouping, force=force08, timeout=timeout, thinking="medium")
    print(f"[chain] 08-pitfalls DONE: {len(pitfalls)} 条 (discovery+wording) -> steps/08-pitfalls/pitfalls.json")
    return pitfalls


def run_07_09(workdir: Path, sentences: list[dict], grouping, ratings, weapons,
              phases, pitfalls, force: set[str]):
    """07 确定性 + 09 聚合 (复用已绿 SKIP)."""
    from run_segment2 import step07, step09
    pri_path = workdir / "steps" / "07-priorities" / "priorities.json"
    if not should_force("07", force) and _load_json(pri_path):
        print("[chain] 07-priorities SKIP (复用已绿)")
        priorities = _load_json(pri_path)
    else:
        priorities = step07(workdir, sentences, ratings, grouping, phases, force=should_force("07", force))
        print(f"[chain] 07-priorities DONE: upgrades={len(priorities['upgrades'])} "
              f"shop={len(priorities['shop'])}")
    g_path = workdir / "steps" / "09-assemble" / "guide.json"
    if not should_force("09", force) and _load_json(g_path):
        print("[chain] 09-assemble SKIP (复用已绿)")
        guide = _load_json(g_path)
    else:
        guide = step09(workdir, grouping, ratings, weapons, phases, priorities, pitfalls)
        print(f"[chain] 09-assemble DONE: guide sha={guide.get('sha', '')[:8]}")
    return priorities, guide


def run_checks(slug: str, vid: str, work_root: str) -> None:
    """双 check 全绿 (check 红灯永不重试, 重修唯一正路)."""
    from check_segment1 import main as _ck1
    from check_segment2 import main as _ck2
    print("[chain] check_segment1 ...")
    rc1 = _ck1(["--slug", slug, "--variant", vid, "--work-root", work_root])
    if rc1 != 0:
        raise SystemExit(f"FAIL: check_segment1 红灯 for {slug}/{vid} (永不直接重试, 须重修 prompt/代码)")
    print("[chain] check_segment2 ...")
    rc2 = _ck2(["--slug", slug, "--variant", vid, "--work-root", work_root])
    if rc2 != 0:
        raise SystemExit(f"FAIL: check_segment2 红灯 for {slug}/{vid} (永不直接重试, 须重修 prompt/代码)")
    print("[chain] 双 check 全绿")


def validate_audit(workdir: Path) -> None:
    """审计常设视图只读校验 (不由 agent 生成, 测试读 G 盘、正式随产物发布).

    - templates/audit.html 须含 06-09 对应节 + 输入标注 + 实节渲染 (与 check 一一对应).
    - 同目录可读: steps/outputs 关键文件须存在 (audit ?base=<slug>/<variant> 同目录).
    - 只读: 本函数不写任何 HTML, 缺节即 fail.
    """
    audit_html = (REPO / "templates" / "audit.html").read_text(encoding="utf-8")
    for marker in ("audit-06-phases", "audit-07-priorities", "audit-08-pitfalls", "audit-09-assemble",
                   "steps/06-phases", "steps/07-priorities", "steps/08-pitfalls", "steps/09-assemble",
                   "steps/06-phases/wordings.json", "steps/06-phases/phases.json",
                   "steps/07-priorities/selection.json", "steps/07-priorities/priorities.json",
                   "steps/08-pitfalls/wordings.json", "steps/08-pitfalls/pitfalls.json",
                   "steps/08-pitfalls/candidates.json", "steps/09-assemble/guide.json"):
        if marker not in audit_html:
            raise SystemExit(f"FAIL: audit.html 缺对应节 (只读校验, 一一对应): {marker}")
    for marker in ("appData.phases", "appData.priorities", "appData.pitfalls",
                   "appData.assemble", "appData.candidates08"):
        if marker not in audit_html:
            raise SystemExit(f"FAIL: audit.html 缺 06-09 实节渲染 (只读校验): {marker}")
    need = [
        workdir / "steps" / "06-phases" / "phases.json",
        workdir / "outputs" / "phases.json",
        workdir / "steps" / "07-priorities" / "priorities.json",
        workdir / "steps" / "08-pitfalls" / "pitfalls.json",
        workdir / "steps" / "09-assemble" / "guide.json",
        workdir / "outputs" / "guide.json",
    ]
    for p in need:
        if not p.exists():
            raise SystemExit(f"FAIL: 审计同目录不可读 (缺件即 fail): {p}")
    print("[chain] 审计常设视图只读校验通过 (同目录可读, sha 见双 check)")


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description="真链路 orchestrator (#55)")
    ap.add_argument("--slug", default="cyborg")
    ap.add_argument("--variant", default="ultimate")
    ap.add_argument("--work-root", default="G:/brotato-work")
    ap.add_argument("--url", default="", help="Step00 取证 URL (缺 inputs 时必填, 只吃 URL+slug+variant)")
    ap.add_argument("--cookies", default="", help="yt-dlp cookies 文件 (被风控时人出)")
    ap.add_argument("--force-step", default="",
                    help="逗号分隔强制覆盖 (01,03,04,05,06,06-wordings,07,08,08-wordings,09,all); 缺省复用已绿 SKIP (#66 02 已退役)")
    ap.add_argument("--timeout", type=float, default=LIVENESS_TIMEOUT,
                    help="子进程 liveness 超时秒 (防 hung, 非成本帽; 缺省 1800)")
    ap.add_argument("--print-agent-cmd", action="store_true",
                    help="只打印 RPC 子进程命令与子 prompt 路径, 不执行 (测试/演练用, 非回落)")
    args = ap.parse_args(argv)
    slug, vid = args.slug, args.variant
    workdir = Path(args.work_root) / slug / vid
    force = parse_force_steps(args.force_step)

    if args.print_agent_cmd:
        print(f'cd "{workdir}" && {" ".join(build_agent_cmd())}')
        print("子 prompt (只喂本步全文, 不喂旧 SOP、不跨步):")
        print("  prompts/step06-phases-fewshot.md (FROZEN, segmentation/wording #63) -> steps/06-phases/phases.json")
        print("  prompts/step08-pitfalls-fewshot.md (FROZEN, discovery/wording #64) -> steps/08-pitfalls/pitfalls.json")
        return 0

    print(f"[chain] workdir={workdir} (spawn cwd 锁定, 只读写相对路径)")
    print(f"[chain] force-step={sorted(force) if force else 'none (复用已绿 SKIP)'} "
          f"timeout={args.timeout:.0f}s (liveness, 非成本帽)")
    ensure_step00(slug, vid, workdir, url=args.url, cookies=args.cookies)
    print("[chain] Step00 取证通过 (inputs 四件 + sha 对上, 只认 inputs)")
    sentences, grouping, ratings, weapons = run_01_05(workdir, force)
    phases = run_06(workdir, sentences, force, timeout=args.timeout)
    pitfalls = run_08(workdir, sentences, grouping, force, timeout=args.timeout)
    priorities, guide = run_07_09(workdir, sentences, grouping, ratings, weapons,
                                  phases, pitfalls, force)
    _ = (priorities, guide)
    run_checks(slug, vid, args.work_root)
    validate_audit(workdir)
    print(f"[chain] done. 产物见 {workdir}/steps + outputs; "
          f"06/08 真子进程日志见 steps/06-phases/agent-segmentation.log.jsonl + agent-wording-*.log.jsonl + steps/08-pitfalls/agent-discovery.log.jsonl + agent-wording-*.log.jsonl")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
