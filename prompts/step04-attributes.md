# Step 04 — RETIRED (#60, 2026-10-20)

本文件锚规则已全删退役（动词闭集/同句窗/over/负面词表/count上下半，不查动词、不查 over、不设 S/A 数量帽）。

现行唯一基准：`prompts/step04-ratings-fewshot.md`（FROZEN 30-shot，5职业×6档，引文全机验）。
调度见 `scripts/step04_loop.py`（for-loop 单属性 agent×39，每次只塞 基准fewshot + 全量整句 + 一个属性名）。
输出 `{term_en, rating, quotes, analysis, summary, quote_details}`（count 由代码回填，agent 不填）。
校验见 `scripts/check_segment1.py` check_04（只卡形状）。
CONTEXT ratings 段以 fewshot 文件为准（#47/#50 作废）。

旧锚规则正文已删除，不作 few-shot，不进 prompt，不作输入。
