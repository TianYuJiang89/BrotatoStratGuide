# TASK_EVIDENCE（FROZEN 2026-10-21 v2：只判 TASK_WEAPON 这一把，其它一律不判）

输出一件 JSON，不输出其它文字：
{"name_en": "<与 TASK_WEAPON 一字不差>", "tier": "T1/T2（建议）", "quotes": ["逐字，去重，非空"], "analysis": "来源→机制→分档", "note": "≤120字人话+短引"}

T1=carry/主力：整局扛伤害或体系入口，没它构筑不存在；证据须机制挂钩句+把数/波次后果句。
T2=过渡/备选：前中期过渡、有 T1 即换、不升满；证据须过渡位人话+短引。
note ≤120 字：一句人话+一句短引（把数/波次数字须出自本条 quotes 逐字）。
空证据即 fail（无“-”档）。幻觉名/编 quote 即 fail。你不填 count。

## NOTE 例（4，把数/波次数字逐字）

- `主力连发，见第二把直接拿，原话“take a second minigun”。`（second 出自 quotes）
- `工程转后全靠它，四把成型原话“four screwdrivers”。`（four 出自 quotes）
- `horde 波专用清场，打 elite 还是 minigun，原话“for the horde wave”。`（horde wave 出自 quotes）
- `决赛战报：minigun 70,000 对 nuke 18k，主力无悬念原话“70,000 damage”。`（70,000 出自 quotes）
