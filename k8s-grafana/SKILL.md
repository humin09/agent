---
name: k8s-grafana
description: "K8s Grafana 运维子专题：Dashboard 定位、面板修改、回滚"
targets: ["*"]
---

你现在进入 **K8s Grafana 子专题**。

执行规则：
1. 改动前备份 Dashboard JSON。
2. 优先按 `dashboard uid` 定位，再用 folder/title 辅助。
3. 涉及指标语义变更时，联动 Thanos 校验。
4. 不在 Skill 中保存明文口令。

流程：定位 -> 判断 CM/API-only -> 备份 -> 修改 -> 回归验证。

协作：指标核验加载 `/Users/humin/agent/k8s-thanos/SKILL.md`。
