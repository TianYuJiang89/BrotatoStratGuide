"""#95 共享 prompt 契约句（代码侧 TASK 后缀，frozen fewshot 不动）。

一调用一 builder，一条契约只写这里一份，禁各 loop 各抄一遍（防口径漂移）。
本模块只放**已被 validator 强制**的契约句，不新立判法、不放宽校验。
"""

from __future__ import annotations

# quotes 逐字校验的消歧句 (#95 fisherman: agent 把句首 And/So 当语气词切掉,
# 其余逐字 → 撞「编 quote」闸). 只挂到输出整句 quotes 的 builder 上。
QUOTE_WHOLE_SENTENCE = (
    "- quote 须整句逐字：从该条 text 的第一个词抄到句末标点，"
    "开头词（And/So/Now/Yeah 等）与原始大小写一个都不许省；禁截片段、禁改写；截断即 fail。\n"
)
