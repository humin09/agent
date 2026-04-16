---
name: k8s-calico
description: "K8s Calico 运维子专题：网络连通性、策略与数据平面排障"
targets: ["*"]
---

你现在进入 **K8s Calico 子专题**。

排障主线：
1. 控制面：calico/node 与 calico/kube-controllers 状态。
2. 数据面：路由/BGP/iptables。
3. 策略面：NetworkPolicy 与命名空间选择器。
4. 业务面：Pod -> Service -> Pod 分段验证。

常用命令：
- `kubectl --context=<别名> -n kube-system get po -o wide | grep calico`
- `kubectl --context=<别名> -n <namespace> get networkpolicy`
- `kubectl --context=<别名> -n <namespace> get svc,ep`
