# 子 agent 调用方式调研（wayfinder #35）

Map: [Agentic workflow 重构：SOP 执行链拆细](https://github.com/TianYuJiang89/BrotatoStratGuide/issues/33)
Ticket: [子 agent 调用方式调研：SDK 起 session 与 cwd 锁定](https://github.com/TianYuJiang89/BrotatoStratGuide/issues/35)

## 结论（推荐）

Python 主脚本不要直调 TS SDK，用 **RPC 子进程一步一起**：每步 `spawn pi.cmd --mode rpc --no-session`，
spawn 时 `cwd=G:/brotato-work/<slug>/<variant>/`，`--tools` 最小集，`--system-prompt` 只喂本步 SOP。
TS SDK 只在需要同进程嵌入时用，模式等价（`createAgentSession({cwd, SessionManager.inMemory(cwd)})`）。

## 1. Python 如何起一步一 session

- **没有 Python SDK**。SDK 只有 TS 包 `@earendil-works/pi-coding-agent`（本机 `0.85.1`），入口 `createAgentSession()`（[sdk.md](file:///F:/Pi/CLI/node_modules/@earendil-works/pi-coding-agent/docs/sdk.md) Quick Start / Core Concepts）。
- **Python 官方推荐路径是 RPC**："RPC mode is preferred when you're integrating from another language / need process isolation"（[rpc.md](file:///F:/Pi/CLI/node_modules/@earendil-works/pi-coding-agent/docs/rpc.md) RPC Mode Alternative）。协议是 stdin/stdout JSONL，一行一命令，`{"type":"prompt"}` / `{"type":"bash"}` / `{"type":"get_state"}` 等，`--no-session` 即 ephemeral。
- **一步一 session = 一步一子进程**：主脚本每步 `Popen([pi.cmd, --mode rpc, --no-session, ...], cwd=stepWorkdir)`，跑完 `terminate/wait` 即销毁，无残留 session 文件。等价 TS 写法是每步 `createAgentSession({sessionManager: SessionManager.inMemory(cwd)})` + 用完 `session.dispose()`（[sdk.md](file:///F:/Pi/CLI/node_modules/@earendil-works/pi-coding-agent/docs/sdk.md) Session Management，[11-sessions.ts](file:///F:/Pi/CLI/node_modules/@earendil-works/pi-coding-agent/examples/sdk/11-sessions.ts)）。不要用 `AgentSessionRuntime.newSession()` 常驻复用——那是给 TUI/print/RPC 内置模式做 resume/fork 的（[sdk.md](file:///F:/Pi/CLI/node_modules/@earendil-works/pi-coding-agent/docs/sdk.md) createAgentSessionRuntime），与“真隔离、一步一进程”的 Notes 方向相反。
- **备选（不推荐）**：Python 调 `node run-step.mjs` 薄包装一层 TS SDK（`createAgentSession` + `session.prompt()` + `dispose()`），见 [01-minimal.ts](file:///F:/Pi/CLI/node_modules/@earendil-works/pi-coding-agent/examples/sdk/01-minimal.ts)。多一层 node/python 桥，只在需要同进程取 `session.agent.state` 时才考虑。

验证：`pi.cmd --mode rpc --no-session` + `{"type":"get_state"}` 在 `D:/notebook/BrotatoStratGuide` 下实测返回 `success:true`（model `muse-spark-1.3-contributor`，`isStreaming:false`）；`--mode print --no-session` 实测可跑通并退出码 0。

## 2. cwd 如何锁死干净目录

- TS SDK：`createAgentSession({cwd})` 会“builds selected built-in tools for that cwd”（[sdk.md](file:///F:/Pi/CLI/node_modules/@earendil-works/pi-coding-agent/docs/sdk.md) Tools with Custom cwd），示例见 [05-tools.ts](file:///F:/Pi/CLI/node_modules/@earendil-works/pi-coding-agent/examples/sdk/05-tools.ts) `createAgentSession({cwd: customCwd, sessionManager: SessionManager.inMemory(customCwd)})`。`cwd` 同时控制 `DefaultResourceLoader` 的 discovery（project extensions/skills/prompts/AGENTS.md 从 cwd 向上找，见 [sdk.md](file:///F:/Pi/CLI/node_modules/@earendil-works/pi-coding-agent/docs/sdk.md) Directories）。
- RPC/CLI：**session cwd = 子进程 spawn cwd**，无 `--cwd` 参数（`pi --help` 无 cwd 选项，只能靠进程 cwd）。实测：spawn `cwd=/tmp/pi-research-test2` 后 `{"type":"bash","command":"pwd && ls -la"}` 返回 `/d/tmp/pi-research-test2`；`cd /tmp/pi-research-proof && pi --mode print ... "Write ... to proof.txt"` 实测 `proof.txt` 落在 spawn cwd，内容 `PROOF-OK`（对照组：不 cd 时落在 repo 根，已清理）。
- **不是硬沙箱**：SDK/CLI 均未禁绝对路径，`read G:/...` / `bash cd ..` 在 prompt 层面仍可达。真隔离靠三件套：(a) 主脚本锁 spawn cwd 到 `G:/brotato-work/<slug>/<variant>/`（试点唯一写区，沿 #34）；(b) `--tools` 最小集（下节）；(c) prompt 明令“只读写相对路径，禁 `..` 与绝对盘符”。这与 Notes“真隔离靠主脚本锁 cwd + 只拷必要文件”一致。

## 3. 只拷哪些必要文件

主脚本在 spawn 前用 `shutil.copy2` 把本步输入摆进工作区，不整仓拷贝：

| 步骤 | 拷入工作区 | 落盘到 |
|---|---|---|
| 01-sentences | `inputs/{source.vtt,meta.json,registry-slice.json,manifest.json}`（#34 四件） | `steps/01-sentences/sentences.json` |
| 02-verbs | 上 + `steps/01-sentences/sentences.json` | `steps/02-verbs/verbs.json` |
| 03-grouping | 上 + `steps/02-verbs/verbs.json` | `steps/03-grouping/grouping.json`（= `outputs/groups.json` 草稿 + `reason`，沿 #34） |

- 不拷：repo 根、`data/work/`、`data/subs/`（#34 已定冻结只读对照）、`.pi/`、`AGENTS.md`、skills、cookies。`top3.json` 留 repo 侧（沿 #34）。
- `manifest.json` 带 `sha1`，子 agent 落盘后主脚本重算 sha 即得幂等校验点（重试/成本上限仍在 map Fog，本票不展开）。

## 4. 子 prompt 如何只给本步 SOP

目标：子 agent 看不到旧 SOP 全文、看不到其他步骤，只看到本步契约。

- TS SDK（[03-custom-prompt.ts](file:///F:/Pi/CLI/node_modules/@earendil-works/pi-coding-agent/examples/sdk/03-custom-prompt.ts)、[04-skills.ts](file:///F:/Pi/CLI/node_modules/@earendil-works/pi-coding-agent/examples/sdk/04-skills.ts)、[07-context-files.ts](file:///F:/Pi/CLI/node_modules/@earendil-works/pi-coding-agent/examples/sdk/07-context-files.ts)）：

```ts
const loader = new DefaultResourceLoader({
  cwd: workdir, agentDir: getAgentDir(),
  systemPromptOverride: () => stepSopText,   // 本步 SOP 全文
  appendSystemPromptOverride: () => [],
  skillsOverride: (c) => ({ skills: [], diagnostics: c.diagnostics }),
  agentsFilesOverride: () => ({ agentsFiles: [] }),
  promptsOverride: (c) => ({ prompts: [], diagnostics: c.diagnostics }),
});
await loader.reload();
const { session } = await createAgentSession({
  cwd: workdir, resourceLoader: loader,
  tools: ["read", "bash", "write"],
  sessionManager: SessionManager.inMemory(workdir),
});
```

- RPC/CLI 等价（`pi --help` 实测均支持）：`--no-skills --no-extensions --no-prompt-templates --no-context-files --system-prompt "$(cat prompts/step01.md)" --tools read,bash,write --thinking off`。`--system-prompt` 替换整系统提示（[sdk.md](file:///F:/Pi/CLI/node_modules/@earendil-works/pi-coding-agent/docs/sdk.md) 原话：`systemPromptOverride` replaces default；CLI 侧 `--system-prompt <text>` 同义）。
- 每步 SOP 文件建议：`prompts/step01-sentences.md`、`prompts/step02-verbs.md`、`prompts/step03-grouping.md`，内容只含本步输入/输出 schema（沿 #34 sentence/verb/groups 记录定义）+ 验收行，不引用旧 SOP。

## 5. 最小可运行示例

### A. Python + RPC（推荐，主脚本直接用，已跑通）

```python
import json, subprocess, threading
PICMD = "F:/Pi/CLI/pi.cmd"
workdir = "G:/brotato-work/cyborg/ultimate"  # spawn cwd 即 session cwd
proc = subprocess.Popen(
    [PICMD, "--mode", "rpc", "--no-session",
     "--no-skills", "--no-extensions", "--no-context-files",
     "--tools", "read,bash,write"],
    cwd=workdir, stdin=subprocess.PIPE, stdout=subprocess.PIPE,
    stderr=subprocess.STDOUT, text=True, bufsize=1)
def send(o): proc.stdin.write(json.dumps(o)+"\n"); proc.stdin.flush()
lines = []
def reader():
    for line in proc.stdout:
        print(line[:300])
        lines.append(json.loads(line))
t = threading.Thread(target=reader, daemon=True); t.start()
send({"id": "1", "type": "bash", "command": "pwd && ls inputs/"})
send({"id": "2", "type": "prompt", "message": open("prompts/step01-sentences.md", encoding="utf-8").read()})
# 等 agent_settled 后取落盘：主脚本校验 steps/01-sentences/sentences.json 存在即关
```

实测要点：`get_state`/`bash` 往返正常；`--tools read,bash` 下 `pwd` 返回 spawn cwd；`--mode print` 下 `write proof.txt` 落盘成功（内容 `PROOF-OK`）。

### B. TS SDK 同义（备选，需 node）

```ts
import { createAgentSession, DefaultResourceLoader, SessionManager } from "@earendil-works/pi-coding-agent";
const workdir = "G:/brotato-work/cyborg/ultimate";
const loader = new DefaultResourceLoader({
  cwd: workdir, systemPromptOverride: () => "你是 sentences 抽取器。只读 inputs/，只写 steps/01-sentences/sentences.json。",
  appendSystemPromptOverride: () => [], skillsOverride: (c) => ({ skills: [], diagnostics: c.diagnostics }),
  agentsFilesOverride: () => ({ agentsFiles: [] }),
});
await loader.reload();
const { session } = await createAgentSession({ cwd: workdir, resourceLoader: loader, tools: ["read","bash","write"], sessionManager: SessionManager.inMemory(workdir) });
session.subscribe((e) => { if (e.type === "message_update" && e.assistantMessageEvent.type === "text_delta") process.stdout.write(e.assistantMessageEvent.delta); });
await session.prompt("按 SOP 抽取 sentences 并落盘。"); session.dispose();
```

### C. CLI 一行空转+落盘（已跑通，零改代码验证隔离用）

```bash
cd "G:/brotato-work/cyborg/ultimate" && "F:/Pi/CLI/pi.cmd" --mode print --no-session \
  --no-skills --no-extensions --no-context-files --tools read,bash,write --thinking off \
  "Write the exact text PROOF-OK to proof.txt in the current directory, nothing else."
```

## 给 #36/#37 的输入

- #36（试点步骤契约）可直接按 §3 表写死每步输入输出，把本票 §4 的三份 `prompts/step0*.md` 当契约载体。
- #37（审计 HTML）不受本票影响：HTML 只读约定路径，不经过 agent（沿 #34）。
- 未决仍在 Fog：失败重试/幂等/成本上限（本票只给出 `sha1` 校验点与 `--no-session`  ephemeral 事实，策略未定）。
