# 自验（FROZEN v1 共享文案：落盘后机械自验自修）

> 共享 frozen 文案（#72 试点 05 ranking，挣了再铺开；改此文件须另开票修 prompt，噪音变信号）。

- 落盘后必须用 bash 跑检验脚本（只读不写），读 exit code + 机器可读报错（JSON errors）。
- 跑检验→exit 非零读报错→只改报错项→重跑检验；禁自评式“看起来没问题”（必须以检验 exit 0 为准，不许口头自认无问题）。
- 自修上限 2 次，计数落盘（写 ranking.selfcheck.json：attempts/last_exit）；超限原样停，交 orchestrator 外闸（代码校验 + max-1 cap，不重试不补空）。
