---
name: k8s-grafana
description: "K8s Grafana 运维子专题：Dashboard 定位、面板修改、回滚"
targets: ["*"]
---

你现在进入 **K8s Grafana 子专题**。



## 执行规则
1. 改动前必须备份 Dashboard JSON（同目录生成 `*.bak.<timestamp>.json`）。
2. 优先按 `dashboard uid` 定位，再用 folder/title 辅助。
3. 涉及指标语义变更时，联动 Thanos 校验。
4. 不在 Skill 中保存明文口令。

## AI 面板索引更新（必须产出）
每次改动后，更新一份面板索引文档（Markdown）：
- 文件名建议：`ai-panels-index.md`（或 `ai-<dashboard_uid>-panel-index.md`）
- 至少包含字段：`dashboard_uid`、`folder`、`title`、`panel_id`、`panel_title`、`panel_type`、`gridPos(x,y,w,h)`
- 索引只收录 `ai` 文件夹下的面板

建议表头：
`| panel_id | title | type | pos |`

## 标准流程
定位（uid + folder=ai） -> 判断 CM/API-only -> 备份 -> 修改 -> 更新索引 -> 回归验证

协作：指标核验加载 `/Users/humin/agent/k8s-thanos/SKILL.md`。
