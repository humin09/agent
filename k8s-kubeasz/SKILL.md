---
name: k8s-kubeasz
description: "K8s kubeasz 子专题：集群安装、组件更新与节点增删维护"
targets: ["*"]
---

你现在进入 **K8s kubeasz 子专题**。

## 1) 配置路径

kubeasz 配置路径：`/etc/kubeasz/clusters/k8s`
- `hosts`：inventory 与全局变量
- `config.yml`：集群安装配置入口

## 2) 节点维护

```bash
docker exec -it kubeasz ezctl add-node <cluster> <IP,IP,IP> <NodeType>
docker exec -it kubeasz ezctl del-node <cluster> <IP,IP,IP>
```

## 3) 组件更新（kubeasz 侧）

适用场景：
- kubelet / kube-proxy / containerd / calico 等基础组件升级或重装
- 集群层组件参数更新后批量下发

执行建议：
1. 先确认目标集群、目标节点范围与变更窗口。
2. 先做配置备份与版本记录（含当前组件版本）。
3. 先小范围灰度，再批量执行。
4. 每批次后检查节点 `Ready`、关键 Pod、日志与告警。

命令入口（按实际 kubeasz playbook/ezctl 子命令执行）：
```bash
docker exec -it kubeasz ezctl setup <cluster> <phase>
docker exec -it kubeasz ezctl upgrade <cluster> <phase>
```

## 4) NodeType 判断

- `nvidia-smi` 有输出 -> `gpu`
- `hy-smi` 有输出 -> `dcu`
- 都无输出 -> `cpu`

## 5) 变更约束

- `add-node` / `del-node` / 组件更新 都属于高影响变更，执行前必须给主人确认。
- 执行前必须给出：目标集群、目标节点、预期影响、回滚方案。
