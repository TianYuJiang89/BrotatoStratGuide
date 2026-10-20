# #32 赛博格推导链 (drafter 自清, 送 reviewer + 人三问)

Top3 见 `top3.json` (全频道同角色检索, 1主+2补, 主=candidates[0]).
取证 §4 只做 1+2: 单视频元数据 + 自动字幕每变体独立存
(256K/290K/274K, 与 #27/#29/#31 同字节 fresh 一致);
chapters 早中晚分段已取; 未做 Whisper/帧/Data API/第三方转写.
双标注: Ultimate Steam 1.1.15.1 (2026-07-08);
Nightmare Steam 1.1.15.1 (2026-09-25);
Danger5 Steam 1.1.14.0 beta 9 (2026-01-18, 版本较老待重审).

交叉表 §5: `build_mentions --slug cyborg` 全变体独立,
`check_mentions` 185 WARN (只 warn 不 fail; 184 与 #31 同 +1 注册表扩张).
真口径已清零入库, 残留为低频路过词 (<8次且非T1/核心相关) 与通用词误报,
计数只活 mentions JSON 与本交单, 不进 note/页面.

高频 (≥8次) 未入库批量交代 (issue 交单, 不单列):
- Ultimate: Acid 12 (lock acid 顺手锁, 非体系, 未追);
  Bag 9 / Focus 12 / Jelly 12 / Mutation 9 (roll 路过, 未拿);
  Ice Cube 8 ( elemental 提及, 体系外);
  Peacock 15 / Tyler 9 / Tree 10 (商店路过/跑树, 非必拿).
- Nightmare: Bait 13 / Book 12 / Crystal 15 / Mouse 12 / Wisdom 12
  (roll/ban 路过, 未拿); Landmines 54 实为螺丝刀自带地雷描述
  (screwdriver has the landmines), 未另追地雷件, 与 Ultimate 提过未拿口径一致,
  Nightmare 未单列, 在此批量交代; Jerky 9 / Lemonade 9 / Lure 9 /
  Penguin 9 / Pile of Books 9 / Spicy Sauce 10 (商店锁/roll 路过).
- Danger5: Bag 12 / Bait 12 / Coupon 9 / Feather 9 / Ratzilla 15 /
  Scar 12 (lock/roll 路过, 未拿); Catling Gun 12 (想拿的 synergy, 未到手);
  Obliterator 14 (提及未拿, 未追).

填表 §7 分步表 8 步: 主17→次级22→武器 (把数/波次/总数不丢,
同名多把写总数, 如 4 螺丝刀) →道具 (先扫拿取/拒绝动词建清单再分组,
必拿分档核心/顺手/妥协, 提过未拿说原因, ban 说依据) →
开局/中期/后期 (W1-5/W6-12/W13-20 + 转向点) →升级 Top3 (先属性 Top3,
每项怎么拿直购/转化/roll, 升级在前) →商店 Top3 (同两层) →
避坑 1-3 (通用致命) /高难 (仅 Nightmare/Ultimate 变招).
每条 rating 有出处 (字幕原句短引或标题/描述/chapters 注明);
note 为观点小结 (拿几次/何时拿/真搭配/真取舍 + 关键原句短引),
无则不写; “冲突”仅作者明确二选一才写; 无计数泄漏 (已机检 0 泄漏).

机器链 §8: build --slug/--all exit 0,
check/check_updates/check_resources OK
(仅待校对 + Ult/D5 日期待重审 WARN, 可发布);
pytest 79 passed, mypy 5 文件 clean.

Reviewer 按 reviewer-checklist 六查逐块过 (10段×3变体):
①命中清零 ②rating 出处 ③观点小结非充数/模具/计数泄漏
④无无出处 rating ⑤数量/获取方式 ⑥头部拿取动作 + 腰部抽查.
drafter 不审己稿, 输出意见清单改完再送人三问
(选片对不对/转述忠不忠实/评级违不违手感).
