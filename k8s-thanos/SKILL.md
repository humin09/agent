---
name: k8s-thanos
description: "K8s Thanos 运维子专题：PromQL 校验、多集群指标诊断"
targets: ["*"]
---

你现在进入 **K8s Thanos 子专题**。

常用入口：`uv run ~/k8s/thanos.py -h`

诊断流程：
1. 明确时间窗口与集群标签。
2. 先查基础可用性（up/targets）。
3. 再查业务指标与标签完整性。
4. 输出可复现 PromQL 与结论。
