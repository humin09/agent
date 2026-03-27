---
name: k8s-ex-lb
description: "K8s Ex-LB 子专题：外部负载均衡链路排障与配置维护"
targets: ["*"]
---

你现在进入 **K8s Ex-LB 子专题**。

## 1) 适用范围

- 外部 HTTP 访问异常排查
- ex-lb 节点与服务状态核查
- ex-lb 配置检查与变更

## 2) 链路与定位

默认访问链路：`nginx (ex-lb) -> ingress -> service/endpoints -> pod`

先按链路分段排查：
1. ex-lb 层
2. ingress 层
3. service/endpoints 层
4. pod 层

## 3) 节点与服务信息

- ex-lb 节点标签：`ex-lb=true`
- 配置目录：`/etc/ex-lb/conf`
- 服务管理：`systemctl`（`status` / `reload`）

常用命令：
```bash
kubectl --context=<别名> get node -l ex-lb=true -o wide
kubectl node-shell --context=<别名> <ex-lb节点IP>
systemctl status ex-lb
ls /etc/ex-lb/conf/
```

## 4) 变更约束

以下操作属于变更，必须先给主人确认：
- 修改 ex-lb 配置文件
- `systemctl reload ex-lb`

执行前必须给出：
- 目标集群与目标节点
- 变更文件与变更点
- 影响范围与回滚方式
