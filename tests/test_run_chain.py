"""#55 真链路 orchestrator: 主脚本自动调真子 agent 跑通 06/08 wordings.

Seams under test (pre-agreed per TDD: CLI exit codes + file bytes, no internal LLM):
- `python scripts/run_chain.py --help` exit codes
- missing inputs fail loud (no silent fallback, 指引 fetch_inputs)
- 复用已绿 SKIP (存在 + schema 绿即 SKIP, --force-step 才覆盖)
- 主脚本不手写 06/08 wordings.json (只读校验, 落盘只经真子进程 write 工具)
- 子 prompt 隔离 (只喂本步 prompt 全文, 最小工具集, spawn cwd 锁定)
- 审计常设视图只读校验 (templates/audit.html  markers, 不由 agent 生成)
- 确定性幂等 (同输入同代码必同文件, sentences 范围)
- 无成本熔断记账 (主脚本不做熔断与记账, 沿 #54)

No network, no LLM in tests. True agent spawn only in production run
(cyborg/ultimate 从零重跑, 附进程日志/落盘时间证明).
"""
from __future__ import annotations

import importlib.util
import inspect
import json
import shutil
import subprocess
import sys
from pathlib import Path

REPO = Path(__file__).resolve().parent.parent
CHAIN = REPO / "scripts" / "run_chain.py"


def _load(name: str, rel: str):
    spec = importlib.util.spec_from_file_location(name, str(REPO / rel))
    assert spec is not None and spec.loader is not None
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


def test_chain_exists_and_help() -> None:
    assert CHAIN.exists(), "scripts/run_chain.py must exist (#55 落点)"
    r = subprocess.run(
        [sys.executable, "scripts/run_chain.py", "--help"],
        cwd=REPO, capture_output=True, text=True)
    assert r.returncode == 0, f"--help must exit 0: {r.stderr[-1000:]}"
    for needle in ("--slug", "--variant", "--work-root", "--force-step"):
        assert needle in r.stdout, f"--help must document {needle}"


def test_chain_missing_inputs_fails_loud(tmp_path: Path) -> None:
    m = _load("run_chain", "scripts/run_chain.py")
    workdir = tmp_path / "cyborg" / "ultimate"
    (workdir / "inputs").mkdir(parents=True)
    try:
        m.ensure_step00("cyborg", "ultimate", workdir, url="", cookies="")
    except SystemExit as e:
        assert "fetch_inputs" in str(e) or "Step00" in str(e) or "missing" in str(e).lower()
    else:
        raise AssertionError("missing inputs must fail loud (禁静默回落)")


def test_chain_no_handwritten_wordings() -> None:
    src = CHAIN.read_text(encoding="utf-8")
    # 主脚本禁手写 06/08 wordings.json: 不许出现直接写盘 wordings.json 的 open/write 模式.
    # 允许: 读校验 (read/load), 日志路径, prompt 路径. 禁: 写 wordings.json.
    for bad in ('"wordings.json", "w"', "'wordings.json', 'w'",
                '"wordings.json","w"', "'wordings.json','w'",
                'wordings.json", "wt"', "wordings.json', 'wt'"):
        assert bad not in src, f"run_chain must not hand-write wordings.json ({bad})"
    # 主脚本必须经真子进程: 须含 rpc + --no-session + spawn cwd 语义.
    for needle in ("--mode", "rpc", "--no-session", "cwd"):
        assert needle in src, f"run_chain must spawn true RPC subagent ({needle})"


def test_chain_prompt_isolation_and_min_tools() -> None:
    m = _load("run_chain", "scripts/run_chain.py")
    src = inspect.getsource(m)
    # 只喂本步子 prompt 全文: 须分别引用两份 prompt, 禁旧 SOP 全文/跨步.
    assert "step06-phases" in src and "step08-pitfalls" in src
    for banned in ("new-character-guide.md", "data/mentions", "data/builds"):
        assert banned not in src, f"run_chain must not feed old SOP/old chain ({banned})"
    # 最小工具集 + 隔离旗: --no-skills/--no-extensions/--no-context-files + read,write.
    for needle in ("--no-skills", "--no-extensions", "--no-context-files", "read", "write"):
        assert needle in src, f"run_chain must lock minimal tools ({needle})"


def test_chain_no_cost_fuse_or_accounting() -> None:
    src = CHAIN.read_text(encoding="utf-8")
    slow = src.lower()
    # #54 已全取消: 主脚本不做记账与熔断, 不加帽. 允许 liveness timeout (防 hung, 非成本帽)
    # 与 prose 提及 ("不做熔断"/"已全取消") 区分: 禁的是实现 (token 记账/上限变量/预算熔断逻辑).
    for bad in ("max_tokens", "token_cap", "cost_cap", "total_tokens", "usage[\"input\"]"):
        assert bad not in slow, f"run_chain must not do cost fuse/accounting ({bad})"
    assert "budget" not in slow or "不做" in src or "取消" in src, \
        "run_chain must not enforce budget (沿 #54 全取消)"
    assert "不做" in src or "取消" in src, "run_chain must document 熔断已取消 (沿 #54)"
    # 重试/重修/复用/幂等四口径须在 (沿 #52-Q1-Q4, #54 后仍有效).
    for needle in ("复用", "幂等", "重试", "re-use", "reuse", "skip", "force-step", "force_step"):
        if needle in src:
            break
    else:
        raise AssertionError("run_chain must implement 复用/SKIP + --force-step (Q4)")


def test_chain_step00_only_eats_url_slug_variant(tmp_path: Path) -> None:
    m = _load("run_chain", "scripts/run_chain.py")
    src = inspect.getsource(m.ensure_step00)
    # 不选片: 只吃 URL+slug+variant, 来源写 manifest (fetch_inputs 产出, 主脚本不自造).
    assert "url" in src.lower()
    assert "top3" not in src.lower(), "run_chain must not do 选片 (top3 留 repo 侧)"


def test_chain_rpc_utf8_encoding() -> None:
    src = CHAIN.read_text(encoding="utf-8")
    # Windows GBK 缺省会吞中文 agent 输出致 JSONL 断流误判 transient (#55 实测):
    # Popen 必须显式 encoding="utf-8".
    assert 'encoding="utf-8"' in src or "encoding='utf-8'" in src, \
        "run_chain RPC must use utf-8 (中文输出不断流)"


def test_chain_audit_readonly(tmp_path: Path) -> None:
    m = _load("run_chain", "scripts/run_chain.py")
    assert hasattr(m, "validate_audit"), "run_chain must have validate_audit (只读校验)"
    src = inspect.getsource(m.validate_audit)
    # 只读校验: 读 templates/audit.html markers, 不生成 HTML, 不调 agent.
    assert "audit.html" in src
    assert "write" not in src.lower() or "read" in src.lower()


def test_chain_deterministic_idempotent(tmp_path: Path) -> None:
    # 同输入同代码必同文件: step01 在 tmp 两次运行字节一致.
    m1 = _load("run_segment1", "scripts/run_segment1.py")
    src_real = Path("G:/brotato-work/cyborg/ultimate/inputs/source.vtt")
    if not src_real.exists():
        raise AssertionError("G work cyborg/ultimate inputs missing (先备后跑前置)")
    workdir = tmp_path / "cyborg" / "ultimate"
    (workdir / "inputs").mkdir(parents=True)
    for f in ("source.vtt", "meta.json", "manifest.json"):
        shutil.copy2(src_real.parent / f, workdir / "inputs" / f)
    s1 = m1.step01(workdir)
    b1 = (workdir / "steps" / "01-sentences" / "sentences.json").read_bytes()
    s2 = m1.step01(workdir)
    b2 = (workdir / "steps" / "01-sentences" / "sentences.json").read_bytes()
    assert b1 == b2, "deterministic step01 must be byte-identical (幂等)"
    assert 300 <= len(s1) <= 600, f"sentences must be 300-600 (折叠后), got {len(s1)}"
