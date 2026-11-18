# Codex Skill

The installable skill is [skills/procurement-estimation/SKILL.md](skills/procurement-estimation/SKILL.md). Read that entrypoint and its schema before using the CLI with your own data.

### 首轮多参考检索
首轮同时检索名称、用途、工艺、规格及有原文依据的子项；先查询整项，再补充子项。不得按固定条数截断有效依据。按交付对象及范围、材质工艺规格、计价口径、参数完整度排序，整包及部分参考后置。排除当前来源及其版本，沿用采购证据去重。返回 match_rank 和具体 match_points，网页初显五条并允许展开全部，不得另行改变引擎排序。
